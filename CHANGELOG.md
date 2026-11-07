# Changelog

## [Unreleased]

### Added

- Local four-shortcut dashboard with D-pad navigation and access to Samsung Home.
- HDMI label matching and import of native source names during packaging.
- Bounded device requests with cancellation and stale-callback protection.
- Source-built Q70T Home companion, offline package builder, and full routing-snapshot comparison.
- Tested Samsung cleanup findings, recovery procedure, and explicit compatibility limits.

### Changed

- Record that the physical Home route survived one long-Power restart; automatic startup failed in that trial.
- Show four destination logos without a greeting, numbered cards, or repeated captions.
- Identify the Nintendo console as Switch 2.
- Remove manual HDMI assignment from the TV interface.

### Fixed

- Replace Samsung's existing short-Home target instead of adding a parallel rule that also opens Samsung's bar. Physically confirmed on QN65Q70TAFXZC, T-NKMAKUC-2743.0.
- Skip a redundant source-change request when reopening the current HDMI input. Keep the normal switch path when the current source cannot be read.
