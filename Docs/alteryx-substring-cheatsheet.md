# Substring — Alteryx → Python 早見表

```text
Alteryx                 → Python
Substring([f], 5, 2)    → df["f"].str[5:7]    # [start : start+length]
Substring([f], 3)       → df["f"].str[3:]
```

詳細(0-indexed の根拠、SQL との違い、エッジケース)は
[alteryx-pandas-differences.md §12](alteryx-pandas-differences.md) を参照。
