# Join output selection and stream routing

yxray reads the workflow's `Connections/Connection` edges to decide which
output actually feeds each downstream input. `MetaInfo connection="Left"`
describes an output schema; it is not evidence that the output is connected.
Likewise, `SelectConfiguration outputConnection="Join"` describes J's column
selection, not the downstream wiring.

Connected Join outputs have distinct names:

| XML source port | Generated frame | Behavior |
| --- | --- | --- |
| `Left` | `df_<id>_l` | Unmatched left rows; original left columns and dtypes |
| `Join` | `df_<id>_j` | All matching combinations; J's Select settings apply |
| `Right` | `df_<id>_r` | Unmatched right rows; original right columns and dtypes |

Only connected outputs are emitted. With no outgoing connection, the existing
J snippet remains as an isolated preview with an explicit warning that its
usage is unknown; the preview must not be interpreted as a resolved edge.
Missing Join inputs, missing/incomplete connection XML, unknown output ports,
and connected joins with unresolved keys emit a TODO and `NotImplementedError`
rather than silently selecting J. Unimplemented non-default ports of other
tools are guarded as well.

For example, if the right frame is empty, J is empty but L retains **all**
left rows. Replacing L with `how="inner"` would silently remove those rows.

The .py scaffold, .md blocks and per-node Copy Python snippets display the
parsed source/destination ports and the resolved frame name:

```python
# Connection: 20.Left -> 30.#1; input=df_20_l
```

Union consumes these edge-specific frame names. J and L from the same tool
therefore no longer become `pd.concat([df_20, df_20])`. A configured explicit
Union `OutputOrder` is honored; incomplete order mappings stop with a TODO.
The optional `Connection/@name` identifies each named input; a distinct
destination anchor can also identify it. Repeated unnamed `Input` anchors
cannot establish an explicit order and are diagnosed instead of guessed.
Without `SetOutputOrder=True`, scaffold retains connection-file order, which
does not establish Alteryx's runtime ordering for tied rows.

Filter uses the same routing mechanism: `True` goes to `df_<id>_t`, `False`
to `df_<id>_f`. The predicate is evaluated once and split by complementary
masks. Missing predicate results route to False; compare this policy against
Alteryx for nullable predicates. A connected Filter with an untranslatable or
missing predicate stops instead of passing through or guessing True.

## J output column selection

When a field-based Join has a `SelectConfiguration` for its `Join` output,
yxray emits a `join_selected()` call instead of a bare `pd.merge()`. The call
carries the input side, field selection, rename, target type, wildcard setting,
and `OrderChanged` setting from the XML. Other output configurations are ignored.
Joins without output selections retain the existing merge scaffold.

As with the Select helper, the definition is not embedded in the scaffold.
Copy `reference_impl/join_selected.py` and `reference_impl/select_edits.py` beside
the generated script, and add:

```python
from join_selected import join_selected, join_unmatched
```

The two helpers must be importable from the same target project. This is a
runtime dependency of the generated script, not of yxray itself.

## Behavior

- All join keys are used even if their output fields are deselected.
- Left and right fields have separate internal identities, including equal-name
  keys. Both key fields can be retained independently.
- Duplicate keys produce all matching row combinations; no deduplication occurs.
- Left fields retain their names. A right field overlapping the input schema
  receives a `Right_` prefix unless an explicit rename overrides it.
- Only the declared input prefix is removed from an XML field reference. An
  input name already containing `Right_` therefore remains intact.
- `*Unknown=False` retains only explicitly selected fields. True, or an omitted
  wildcard, retains unspecified fields as well.
- `OrderChanged=False` preserves input order (left, then right). True uses the
  configured field order, placing unspecified fields at the wildcard position
  or at the end when the wildcard is omitted.
- Selected target types use the existing `apply_select_edits()` implementation.
- Missing saved fields are warned about and skipped; inputs are not modified.

## Verification boundaries

Tests use invented names and values only. They exercise parsed synthetic XML
through generated code and the runtime helper. No private workflow or source
record is required or committed.

Compare output to Alteryx locally before treating this as full parity. In
particular, null-key matching follows pandas, numeric type conversions retain
the documented Select-helper approximations, and default naming for unusual
collisions or case-only differences has not been golden-verified. Output name
collisions raise an error rather than silently producing duplicate columns;
explicit renames can resolve them. Inputs require unique string column names.

Field-based L/J/R outputs are implemented. Join by record position and ambiguous
J Select input-side specifications emit an explicit TODO and raise
`NotImplementedError`. L/R are existence tests on the full key tuple: duplicate
keys on the opposite side do not multiply rows, and J's column selection is
never applied to L/R. The helper preserves the retained side's original row
order and index; Alteryx runtime order is not claimed as golden-verified.

Synthetic regression tests cover parser-to-scaffold port preservation,
empty-right L output, J/L/R Union, Filter T/F (including duplicate indexes),
composite/null keys, and distinct ports feeding the two inputs of another tool.
