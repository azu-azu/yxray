# Join output selection

When a field-based Join has a `SelectConfiguration` for its `Join` output,
yxray emits a `join_selected()` call instead of a bare `pd.merge()`. The call
carries the input side, field selection, rename, target type, wildcard setting,
and `OrderChanged` setting from the XML. Other output configurations are ignored.
Joins without output selections retain the existing merge scaffold.

As with the Select helper, the definition is not embedded in the scaffold.
Copy `reference_impl/join_selected.py` and `reference_impl/select_edits.py` beside
the generated script, and add:

```python
from join_selected import join_selected
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

This change handles field-based inner joins and the J output only. Join by
record position and ambiguous input-side specifications emit an explicit TODO
and raise `NotImplementedError`. It does not implement the L/R output streams.
