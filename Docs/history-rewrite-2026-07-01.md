# 履歴の作り直しについて(2026-07-01)

このリポジトリの git 履歴は **2026-07-01 に作り直されている**。現在の main の
ルートコミットは `0b23e28`("Add \"Copy Python\" button to inspect panel for
Select tools")で、それ以前の開発内容(2026-06-03〜06-24、約130コミット)は
このルートコミットにスナップショットとして焼き込まれており、コミット単位の
履歴としては残っていない。

## 古いクローンとの不一致は正常

作り直し前にクローンした作業コピーでは、ローカル main と origin/main が
**共通祖先を持たない**(`git merge-base` が空になる、`ahead/behind` が両方
大きく出る)。これは異常ではなく、この作り直しによるもの。旧履歴側の
コミットは件名・SHA ともに現履歴と一致しないが、内容は取り込み済み。

古いクローンを見つけた場合は、ローカル main を捨てて origin/main に
合わせてよい(`git checkout -B main origin/main`)。

## 作り直し時に意図的に落とした機能

以下は旧履歴には存在するが、現履歴には**意図的に含めていない**。
「消えた作業」ではないので復元不要。

- **SQL 変換モジュール** — `src/yxray/sql/`(builder / ir / renderer)、
  `tests/test_sql.py`、cluster-to-sql CLI、`yxray serve` コマンド。
  実験的機能として廃止(旧履歴内でも serve コマンドは revert 済み)。
- **companion タブ機能** — `_companion_window.py` による _report / _graph
  の別タブ連携。single-file 出力への回帰に伴い除去。

旧履歴で開発された UI・レポート系機能(minimap、Containers パネル、
Excel ダウンロード、diff split view など)はすべて現履歴に含まれている。
