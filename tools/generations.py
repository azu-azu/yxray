"""ワークフローの依存関係を世代（generation）ごとに整理する検証スクリプト。

yxray 本体の yxray.parser.parse_one() をそのまま使う（正規表現で XML を再パースしない）。
データフロー用のエッジと、Interface系（AlteryxGuiToolkit.* が絡む）エッジを分離する。
分離した Interface系エッジは Action/ControlParam の関係グラフとしても使える
（macro_interface モデル設計の補助資料を兼ねる）。

Usage:
    .venv/bin/python3 tools/generations.py input/sample-2.yxmc
    .venv/bin/python3 tools/generations.py input/sample-2.yxmc \
        --entry-scopes 1167 load_source_data 1179 build_spatial_output \
        --emit-clusters docs/internal/sample-2_manual_clusters.json

できること（機械的・グラフ構造のみ）:
    - 1ファイルの依存関係を世代（他ノードに依存しないものが世代0、以降は
      上流の最大世代+1）に分類する
    - 合流点(in_degree>=2)・分岐点(out_degree>=2)を検出する — 関数境界の候補
    - --entry-scopes で指定した2ノードの祖先集合(nx.ancestors)から関数スコープ
      を確定し、どちらにも属さないノードが無いか(uncovered)確認できる
      （指定しなければこのレポートはスキップされる — ファイル固有のToolIDを
      決め打ちしない）
    - 各ノードの config(Filter の式、Formula の代入先、File パス等)を要約する
    - --emit-clusters: --entry-scopes で確定したスコープを yxray.manual_clusters.py
      互換の JSON として書き出す。「判断層」の結果を fingerprint 付きで記録・固定
      する（計算 → 判断 → 記録の3層構成、詳細は design doc 参照）。
      ToolContainer 所属ノードはクラスタ化できない制約があるため、
      floating ノードだけに絞り込んで書き出す（--entry-scopes 必須）

できないこと（人間・AIの判断が必要）:
    - 関数の境界を決めることそのものはしない。合流点・分岐点のリストを
      出すだけで、「ここで切る」の判断は見る側がやる
    - 式の意味は理解しない。Alteryx の式文字列を出すだけで、業務的な
      解釈・命名は別工程
    - 2ファイルの比較機能は無い。単一ファイルしか見ない
      （別プロジェクトとの config 突き合わせは別の使い捨てスクリプトで実施した）
    - Python コードは生成しない。分析・レポート専用
    - [#N] を呼び出し元(別ファイル)のデータにバインドする解決はしない
    - どの2ノードをエントリポイントとみなすか（sample-2.yxmc なら 1167/1179）
      は人間が目視で決めるもので、このスクリプトは推測しない
      （--entry-scopes での明示指定が必須）
    - 独立した複数の部分グラフ(connected component)がある場合、それぞれ
      別々に世代0から始まるが、「別系統である」という明示はしない
"""

from __future__ import annotations

import sys
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from yxray.manual_clusters import workflow_fingerprint  # noqa: E402
from yxray.models.workflow import AlteryxNode, WorkflowDoc  # noqa: E402
from yxray.parser import parse_one  # noqa: E402

UI_PREFIX = "AlteryxGuiToolkit."


def is_interface_node(node: AlteryxNode) -> bool:
    """Action/ControlParam/Tab など、データを持たない Interface ツールか。

    アンカー名（Control/Action/Question 等、ツール種別によって揺れる）を
    決め打ちで列挙するより、tool_type の prefix で判定する方が頑健。
    filter_ui_tools が使っている判定基準と同じ。
    """
    return node.tool_type.startswith(UI_PREFIX)


def summarize_config(node: AlteryxNode) -> str:
    """世代ごとの一覧に添える、意味判断用の1行要約。"""
    cfg = node.config
    short_type = node.tool_type.rsplit(".", 1)[-1]

    if short_type == "Filter":
        expr = cfg.get("Expression", {})
        expr_text = expr.get("#text", expr) if isinstance(expr, dict) else expr
        return f"Expression={expr_text!r}"
    if short_type == "Formula":
        fields = cfg.get("FormulaFields")
        return f"FormulaFields={fields!r}"
    if short_type == "AlteryxSelect":
        return f"config_keys={list(cfg.keys())!r}"
    if short_type in ("DbFileInput", "DbFileOutput"):
        file_val = cfg.get("File", {})
        file_text = file_val.get("#text", file_val) if isinstance(file_val, dict) else file_val
        return f"File={file_text!r}"
    return f"config_keys={list(cfg.keys())!r}" if cfg else ""


def build_graphs(
    nodes: list[AlteryxNode],
    connections: list,
    node_by_id: dict[int, AlteryxNode],
) -> tuple[nx.DiGraph, list]:
    """データフロー用の DiGraph と、Interface系エッジのリストを分けて返す。"""
    graph = nx.DiGraph()
    for n in nodes:
        if not is_interface_node(n):
            graph.add_node(n.tool_id)

    ui_edges = []
    skipped = 0
    for c in connections:
        src = node_by_id.get(c.src_tool)
        dst = node_by_id.get(c.dst_tool)
        if src is None or dst is None:
            # パース異常 or 想定外の構造。Questions の罠と同類の「静かに数が
            # 合わへん」事故の芽なので、件数を可視化して0以外なら気付けるようにする
            skipped += 1
            continue
        if is_interface_node(src) or is_interface_node(dst):
            ui_edges.append(c)
        else:
            graph.add_edge(c.src_tool, c.dst_tool)

    if skipped:
        print(f"⚠️ WARNING: {skipped}件の接続が node_by_id に無いノードを参照していてスキップされた")

    return graph, ui_edges


def compute_generations(graph: nx.DiGraph) -> dict[int, int]:
    """上流を持たないノードを世代0とし、以降は上流の最大世代+1とする。"""
    generations: dict[int, int] = {}
    for tool_id in nx.topological_sort(graph):
        preds = list(graph.predecessors(tool_id))
        generations[tool_id] = 0 if not preds else max(generations[p] for p in preds) + 1
    return generations


def report_junctions(graph: nx.DiGraph, node_by_id: dict[int, AlteryxNode]) -> None:
    """合流点（in_degree>=2）・分岐点（out_degree>=2）を報告する。

    世代が一本鎖に近い場合、関数境界の信号は世代の切れ目より
    合流点・分岐点の方が強い。
    """
    merges = sorted(n for n in graph if graph.in_degree(n) >= 2)
    splits = sorted(n for n in graph if graph.out_degree(n) >= 2)

    print(f"\n=== 合流点（in_degree>=2、{len(merges)}件） ===")
    for tid in merges:
        node = node_by_id[tid]
        short_type = node.tool_type.rsplit(".", 1)[-1]
        print(f"  ToolID {tid} ({short_type}) in={graph.in_degree(tid)}  {summarize_config(node)}")

    print(f"\n=== 分岐点（out_degree>=2、{len(splits)}件） ===")
    for tid in splits:
        node = node_by_id[tid]
        short_type = node.tool_type.rsplit(".", 1)[-1]
        print(f"  ToolID {tid} ({short_type}) out={graph.out_degree(tid)}  {summarize_config(node)}")


def report_entrypoint_scopes(
    graph: nx.DiGraph,
    entry_a: int,
    label_a: str,
    entry_b: int,
    label_b: str,
) -> dict[str, set[int]]:
    """label_a()/label_b() のスコープを、entry_a/entry_b の祖先集合で確定する。

    entry_a/entry_b は「この関数の最後のツールはどれか」という、人間が目視で
    決める境界（例: sample-2.yxmc なら Filter(1012)/DbFileOutput(1010,1195) の
    データ入力元である 1167/1179）。このスクリプトはどの2ノードが境界かを
    推測しない — 呼び出し側(CLIなら --entry-scopes)が明示する。
    """
    anc_a = nx.ancestors(graph, entry_a)
    anc_b = nx.ancestors(graph, entry_b)

    scope_a = anc_a | {entry_a}
    scope_b = (anc_b | {entry_b}) - scope_a

    print(f"\n=== {label_a}() スコープ（{entry_a}含む上流、{len(scope_a)}ノード） ===")
    print(f"  {sorted(scope_a)}")

    print(f"\n=== {label_b}() スコープ（{entry_b}側の差分、{len(scope_b)}ノード） ===")
    print(f"  {sorted(scope_b)}")

    uncovered = set(graph.nodes) - scope_a - scope_b
    print(f"\n=== どちらにも属さないノード（{len(uncovered)}件） ===")
    print(f"  {sorted(uncovered)}")

    return {label_a: scope_a, label_b: scope_b}


def build_cluster_config(
    doc: WorkflowDoc,
    node_by_id: dict[int, AlteryxNode],
    groups: dict[str, set[int]],
) -> dict:
    """判断結果を manual_clusters.py 互換の JSON dict にする。

    manual_clusters.py の load_manual_cluster_config() は下記を要求する
    （2026-07-18 時点、コードレビューで確認済み）:
      - クラスタ内のノードは container_id が None であること
        （ToolContainer 所属ノードは対象外 — container 自体が既に
        レポート上で自前の枠線を持つため、二重にグルーピングしない）
      - 1クラスタにつき最低2ノード
      - 同じ ToolID が複数クラスタに重複しない

    そのため各グループを floating ノード（container_id is None）だけに
    絞り込む。絞り込んだ結果2ノード未満になったグループはスキップし、
    件数を報告する（サイレントに消さない）。
    """
    clusters = []
    for label, tool_ids in groups.items():
        floating = sorted(
            tid for tid in tool_ids if node_by_id[tid].container_id is None
        )
        excluded = len(tool_ids) - len(floating)
        if excluded:
            print(
                f"  [{label}] {excluded}件がコンテナ所属のため除外"
                f"（floating {len(floating)}件が残る）"
            )
        if len(floating) < 2:
            print(f"  ⚠️ [{label}] floating ノードが{len(floating)}件のみ、クラスタ化をスキップ")
            continue
        clusters.append({"label": label, "tool_ids": floating})

    return {
        "schema_version": 1,
        "workflow_fingerprint": workflow_fingerprint(doc),
        "manual_clusters": clusters,
    }


def main(
    path: str,
    *,
    emit_clusters: str | None = None,
    entry_scopes: tuple[int, str, int, str] | None = None,
) -> None:
    doc = parse_one(Path(path), filter_ui_tools=False)
    node_by_id = {n.tool_id: n for n in doc.nodes}

    graph, ui_edges = build_graphs(list(doc.nodes), list(doc.connections), node_by_id)
    generations = compute_generations(graph)

    by_gen: dict[int, list[int]] = {}
    for tid, gen in generations.items():
        by_gen.setdefault(gen, []).append(tid)

    print(f"総ノード数: {len(doc.nodes)} / データフローノード数: {len(graph.nodes)} / 世代数: {len(by_gen)}")

    for gen in sorted(by_gen):
        print(f"\n=== 世代 {gen}（{len(by_gen[gen])}ノード） ===")
        for tid in sorted(by_gen[gen]):
            node = node_by_id[tid]
            short_type = node.tool_type.rsplit(".", 1)[-1]
            summary = summarize_config(node)
            print(f"  ToolID {tid} ({short_type}) container={node.container_id}  {summary}")

    print(f"\n=== Interface系エッジ（Action/ControlParam 関係、{len(ui_edges)}件） ===")
    for c in ui_edges:
        src_type = node_by_id[c.src_tool].tool_type.rsplit(".", 1)[-1]
        dst_type = node_by_id[c.dst_tool].tool_type.rsplit(".", 1)[-1]
        print(f"  {c.src_tool}({src_type}, anchor={c.src_anchor}) -> {c.dst_tool}({dst_type}, anchor={c.dst_anchor})")

    report_junctions(graph, node_by_id)

    scopes: dict[str, set[int]] | None = None
    if entry_scopes:
        entry_a, label_a, entry_b, label_b = entry_scopes
        scopes = report_entrypoint_scopes(graph, entry_a, label_a, entry_b, label_b)
    else:
        print(
            "\n(スコープ集計はスキップ: --entry-scopes <id_a> <label_a> <id_b>"
            " <label_b> を指定すると実行される)"
        )

    if emit_clusters:
        import json

        if scopes is None:
            raise SystemExit("--emit-clusters には --entry-scopes の指定も必要です")

        print(f"\n=== クラスタ JSON 書き出し ({emit_clusters}) ===")
        # NOTE: fingerprint は acd i のデフォルト挙動（filter_ui_tools=True）に
        # 合わせて別途パースし直す。上のグラフ分析自体は filter_ui_tools=False
        # のまま（Interface系エッジの分析に必要）。
        # cli.py の --filter-ui-tools/--no-filter-ui-tools は 2026-07-18 まで
        # 単一名 "--no-filter-ui-tools" で登録されており click が反転しない
        # バグがあった（常に True 扱い）。commit で修正済み・回帰テスト追加済み。
        fingerprint_doc = parse_one(Path(path), filter_ui_tools=True)
        config = build_cluster_config(fingerprint_doc, node_by_id, scopes)
        Path(emit_clusters).write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  {len(config['manual_clusters'])}クラスタを書き出した")


if __name__ == "__main__":
    args = sys.argv[1:]
    emit_path = None
    if "--emit-clusters" in args:
        idx = args.index("--emit-clusters")
        emit_path = args[idx + 1]
        del args[idx : idx + 2]
    scopes_arg = None
    if "--entry-scopes" in args:
        idx = args.index("--entry-scopes")
        scopes_arg = (
            int(args[idx + 1]), args[idx + 2],
            int(args[idx + 3]), args[idx + 4],
        )
        del args[idx : idx + 5]
    main(
        args[0] if args else "input/sample-2.yxmc",
        emit_clusters=emit_path,
        entry_scopes=scopes_arg,
    )
