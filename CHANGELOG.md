# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] — 2026-03-28

### Fixed

- Push all branches on new repo creation; fix ahead/behind fallback to `origin/<branch>`
- Fix ahead/behind counts always showing zero
- Detect deleted remote repos and show a clear error in the UI

### Changed

- Upgrade CI to Node 24 and suppress Node 20 deprecation warnings

## [1.2.0] — 2026-03-27

### Changed

- Complete HTML report redesign — CSS-variable theming system, no inline styles
- Rewrite `_GRAPH_FRAGMENT_TEMPLATE` with CSS variables for consistent graph theming

## [1.1.0] — 2026-03-22

### Added

- Dark/light theme toggle with sliding toggle component
- Split-view UI with synced before/after graphs and overlay toggle
- `--no-filter-ui-tools` CLI flag for `.yxwz` analytic app comparison
- Fullscreen graph view
- Draggable nodes in graph view
- Saturated color palette for graph nodes with adaptive dark mode

### Fixed

- Parse nodes inside `ToolContainer` / `ChildNodes` in workflows
- Graph layout — filter containers, shorten labels, increase scale
- Split-view rendering, fullscreen, and node click handlers

## [1.0.0] — 2026-03-07

### Added

- Initial public release
- XML parser for Alteryx workflow files (`.yxmd`, `.yxwz`, `.yxmc`, `.yxzp`, `.yxapp`)
- Structural diff engine with node, connection, and metadata comparison
- Interactive HTML diff report with graph visualization
- CLI entry point (`alteryx-diff`) with Typer
- ALCOA+ governance footer in HTML reports
- 12 CLI smoke tests

[1.2.1]: https://github.com/Laxmi884/alteryx-git-companion/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Laxmi884/alteryx-git-companion/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Laxmi884/alteryx-git-companion/compare/v1.0...v1.1.0
[1.0.0]: https://github.com/Laxmi884/alteryx-git-companion/releases/tag/v1.0
