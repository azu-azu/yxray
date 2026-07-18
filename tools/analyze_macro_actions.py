"""sample-2.yxmc の Action/ControlParam 対応表を機械的に生成する検証スクリプト（使い捨て）。

やること:
1. <Properties><RuntimeProperties><Actions>/*/Action を全件走査し、
   Expression から [#N] を正規表現抽出、Destination を ToolID/Field に分解する
2. <Questions> 配下の ControlParam を出現順に拾い、[#N] -> Description の対応表を作る
3. 1と2を突き合わせて一覧を出力する

これは docs/internal/2026-07-18_sample-2-python-project-design.md の
「補助スクリプト案（未実装）」を実際に動かす検証（Option A）。
再現できたら yxray 本体機能（Option B）に昇格させる。
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlParamRef:
    index: int  # [#N] の N
    tool_id: str
    description: str


@dataclass(frozen=True)
class ActionRewrite:
    tool_id: str
    expression: str
    destination_tool_id: str
    destination_field: str
    referenced_params: list[int]


PARAM_RE = re.compile(r"\[#(\d+)\]")


def parse_control_params(root: ET.Element) -> list[ControlParamRef]:
    """<BatchMacro><ControlParams> の出現順を [#N] のインデックス(1始まり)とみなす。

    <Questions> は Interface タブの設計情報で、Tab要素混在・ブロック重複により
    順序が信頼できない(実際に sample-2.yxmc では Questions ブロックが2個あり、
    ControlParam が4件ヒットするバグを誘発した)。
    <BatchMacro><ControlParams> はブロックが1個だけで、Alteryx が実際に
    [#N] の解決に使う正規の並びに対応する。
    """
    params: list[ControlParamRef] = []
    blocks = root.findall(".//BatchMacro/ControlParams")
    if len(blocks) != 1:
        raise ValueError(
            f"BatchMacro/ControlParams が {len(blocks)} 個見つかった（1個を想定）。"
            " 手動で確認すること。"
        )
    for i, cp in enumerate(blocks[0].findall("ControlParam"), start=1):
        name_el = cp.find("Name")
        desc_el = cp.find("Description")
        # Name は "コントロールパラメーター (951)" 形式 — 括弧内の ToolID を取り出す
        name = name_el.text if name_el is not None else ""
        m = re.search(r"\((\d+)\)", name)
        params.append(
            ControlParamRef(
                index=i,
                tool_id=m.group(1) if m else "?",
                description=desc_el.text if desc_el is not None else "?",
            )
        )
    return params


def parse_actions(root: ET.Element) -> list[ActionRewrite]:
    actions: list[ActionRewrite] = []
    for a in root.findall(".//Actions//Action"):
        tool_id_el = a.find("ToolId")
        expr_el = a.find("Expression")
        dest_el = a.find("Destination")
        if expr_el is None or expr_el.text is None or dest_el is None or dest_el.text is None:
            continue
        dest_tool_id, _, dest_field = dest_el.text.partition("/")
        actions.append(
            ActionRewrite(
                tool_id=tool_id_el.get("value") if tool_id_el is not None else "?",
                expression=expr_el.text,
                destination_tool_id=dest_tool_id,
                destination_field=dest_field,
                referenced_params=[int(n) for n in PARAM_RE.findall(expr_el.text)],
            )
        )
    return actions


def build_table(params: list[ControlParamRef], actions: list[ActionRewrite]) -> str:
    param_by_index = {p.index: p for p in params}

    lines = ["[#N] -> ControlParam(ToolID/Description) -> Action(ToolID) -> Destination(ToolID/Field)", "-" * 90]
    for action in actions:
        for n in action.referenced_params:
            p = param_by_index.get(n)
            label = f"{p.tool_id}/{p.description}" if p else "(不明: Questions側に対応する ControlParam が無い)"
            lines.append(
                f"[#{n}] -> {label} -> Action({action.tool_id}) "
                f"-> {action.destination_tool_id}/{action.destination_field}"
            )
        lines.append(f"    Expression: {action.expression}")
    return "\n".join(lines)


def main(path: str) -> None:
    root = ET.parse(path).getroot()
    params = parse_control_params(root)
    actions = parse_actions(root)

    print(f"=== ControlParam 一覧（{len(params)}件, 出現順） ===")
    for p in params:
        print(f"  [#{p.index}] ToolID={p.tool_id} Description={p.description!r}")

    print(f"\n=== Action 一覧（{len(actions)}件） ===")
    print(build_table(params, actions))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "input/sample-2.yxmc")
