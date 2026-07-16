"""Find Replace tool → pandas translation for the scaffold generator.

The tool has four translated shapes, discriminated by FindMode ×
ReplaceMode (the XML can retain stale settings for the non-selected mode,
so ReplaceMode is always the primary discriminator):

* FindAny + Append   → simulate_find_any_append() helper call
* FindWhole + Append → deduplicated left join
* FindWhole + Replace → lookup-map .map().fillna()
* anything else      → explicit TODO passthrough

Much of what looks arbitrary here (which columns appear in the output,
duplicate-key resolution, ReplaceMultipleFound being ignored) is
golden-verified against real Alteryx output — see the inline comments
before "fixing" any of it.
"""

from __future__ import annotations

from typing import Any

from yxray.config_utils import (
    as_list,
    comment_safe,
    field_name,
    first_text,
    py_str,
)
from yxray.scaffold._common import anchor_src, frame_name


def _findreplace_any_append(
    tool_id: int,
    df_out: str,
    df_f: str,
    df_r: str,
    field_find: str,
    field_search: str,
    append_names: list[str],
    case_sensitive: bool,
) -> str:
    fields = ", ".join(py_str(n) for n in append_names)
    # The helper output is "original Targets columns + append_fields" only;
    # the search value (FieldSearch) is used to look up but never added to
    # the output — matching real Alteryx Append output (verified against
    # golden output, diff 0). So FieldFind == FieldSearch needs no special
    # handling: the key column is never duplicated.
    # ReplaceMultipleFound is NOT emitted: it has no effect on Append output
    # (golden-verified with both settings) and showing it would suggest it
    # matters. The helper still accepts the kwarg for callers that pass it.
    header = (
        "# Find Replace (FindAny) — substring lookup: each Source"
        " search value\n"
        "# is matched inside the Targets find field\n"
        "# NOTE: simulate_find_any_append() is not generated — copy"
        " it from\n"
        "# scripts/simulate_find_any_append.py\n"
    )
    return (
        header + f"{df_out} = simulate_find_any_append(\n"
        f"    {df_f},\n"
        f"    {df_r},\n"
        f"    find_field={py_str(field_find)},\n"
        f"    search_field={py_str(field_search)},\n"
        f"    append_fields=[{fields}],\n"
        f"    case_sensitive={case_sensitive},\n"
        f"    log_label={py_str(f'ToolID {tool_id}')},\n"
        f")"
    )


def _findreplace_whole_append(
    tool_id: int,
    df_out: str,
    df_f: str,
    df_r: str,
    field_find: str,
    field_search: str,
    append_names: list[str],
) -> str:
    cols = ", ".join(py_str(n) for n in (field_search, *append_names))
    # When find/search names differ, pd.merge keeps the right_on key column in
    # the output. That matches real Alteryx: FindWhole automatically carries
    # the search key column into the Append output even when it is not
    # selected as an append field (golden-verified) — asymmetric with FindAny,
    # where the search value column never appears. Do not "fix" this with a
    # drop(columns=[field_search]).
    key = (
        f"    on={py_str(field_find)},"
        if field_find == field_search
        else f"    left_on={py_str(field_find)},\n    right_on={py_str(field_search)},"
    )
    # Find Replace never grows the row count (1 target = 1 row), so the
    # lookup side must be deduplicated before a left join. The LAST duplicate
    # always wins, regardless of ReplaceMultipleFound — golden-verified with
    # BOTH RMF settings (3 duplicate keys with distinct values, identical
    # output). RMF has no observed effect in Append mode.
    lookup_var = f"_LOOKUP_{tool_id}"
    return (
        "# Find Replace (append fields on whole match) as a left join"
        " — review translation\n"
        "# lookup deduplicated so 1 target = 1 row; the last duplicate wins\n"
        "# regardless of ReplaceMultipleFound (golden-verified)\n"
        f"{lookup_var} = {df_r}[[{cols}]]"
        f'.drop_duplicates({py_str(field_search)}, keep="last")\n'
        f"{df_out} = pd.merge(\n"
        f"    {df_f},\n"
        f"    {lookup_var},\n"
        f"{key}\n"
        f'    how="left",\n'
        f")"
    )


def _findreplace_whole_replace(
    df_out: str,
    df_f: str,
    df_r: str,
    field_find: str,
    field_search: str,
    replace_field: str,
    tool_id: int,
) -> str:
    map_var = f"_MAP_{tool_id}"
    return (
        "# Find Replace (whole match) via lookup map"
        " — review translation\n"
        f"{map_var} = dict(zip({df_r}[{py_str(field_search)}],"
        f" {df_r}[{py_str(replace_field)}]))\n"
        f"{df_out} = {df_f}.copy()\n"
        f"{df_out}[{py_str(field_find)}] = ("
        f"{df_out}[{py_str(field_find)}].map({map_var})"
        f".fillna({df_out}[{py_str(field_find)}]))"
    )


def _findreplace_todo(df_out: str, df_f: str, find_mode: str, replace_mode: str) -> str:
    # Name both axes so a reviewer can tell "cannot translate" apart from
    # "forgot to translate".
    return (
        f"# TODO: Find Replace — FindMode='{comment_safe(find_mode) or '?'}',"
        f" ReplaceMode='{comment_safe(replace_mode) or '?'}'\n"
        "# is not translated; input passed through unchanged\n"
        f"{df_out} = {df_f}"
    )


def gen_findreplace(
    tool_id: int,
    segment: str,
    config: dict[str, Any],
    preds: list[int],
    anchors: dict[str, int],
    names: dict[int, str],
) -> str:
    df_out = names[tool_id]
    # Alteryx FindReplace XML connection anchors: Targets = main stream (FieldFind),
    # Source = lookup table (FieldSearch). "F"/"R" are kept as fallbacks
    # for test fixtures.
    f_id = anchor_src(anchors, preds, ("Targets", "F", "Find", "Input"), 0)
    r_id = anchor_src(anchors, preds, ("Source", "R", "Replace"), 1)
    df_f = frame_name(names, f_id, "df_find")
    df_r = frame_name(names, r_id, "df_replace")

    field_find = first_text(config, "FieldFind")
    field_search = first_text(config, "FieldSearch")
    find_mode = first_text(config, "FindMode")
    replace_mode = first_text(config, "ReplaceMode")
    append_fields = config.get("ReplaceAppendFields", {})
    append_names: list[str] = []
    if isinstance(append_fields, dict):
        append_names = [
            field_name(f)
            for f in as_list(append_fields.get("Field"))
            if isinstance(f, dict) and field_name(f)
        ]
    # ReplaceMultipleFound は読まない: Append モードでは出力に影響しない
    # ことが golden 実測で確定しており（FindAny・FindWhole とも両設定で同一
    # 出力）、生成コードに出すと意味があるように見えてしまうため。
    nocase_raw = config.get("NoCase", {})
    case_sensitive = not (
        isinstance(nocase_raw, dict) and nocase_raw.get("@value", "").lower() == "true"
    )

    whole_match = find_mode == "FindWhole" and bool(field_find and field_search)
    any_match = find_mode == "FindAny" and bool(field_find and field_search)

    if any_match and replace_mode == "Append" and append_names:
        return _findreplace_any_append(
            tool_id,
            df_out,
            df_f,
            df_r,
            field_find,
            field_search,
            append_names,
            case_sensitive,
        )
    if whole_match and replace_mode == "Append" and append_names:
        return _findreplace_whole_append(
            tool_id,
            df_out,
            df_f,
            df_r,
            field_find,
            field_search,
            append_names,
        )
    # ReplaceMode is the primary discriminator: the XML can retain settings
    # for the non-selected mode (a stale ReplaceFoundField survives switching
    # the GUI to Append), so the tag's presence alone must never select the
    # Replace branch.
    replace_field = first_text(config, "ReplaceFoundField")
    if whole_match and replace_mode == "Replace" and replace_field:
        return _findreplace_whole_replace(
            df_out,
            df_f,
            df_r,
            field_find,
            field_search,
            replace_field,
            tool_id,
        )
    return _findreplace_todo(df_out, df_f, find_mode, replace_mode)
