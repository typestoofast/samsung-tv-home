# Changelog

## [Unreleased]

### Added

- Optional bounded local startup tracing and a private staging tool. Normal staged builds omit the recorder.
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

- Keep source discovery independent of app launches and input handoffs. Queue an early HDMI selection until discovery completes, and cancel it on Back or when Four hides. Prepared for hardware testing.
- Reuse verified in-memory inputs on return while refreshing their state asynchronously.
- Replace Samsung's existing short-Home target instead of adding a parallel rule that also opens Samsung's bar. Physically confirmed on QN65Q70TAFXZC, T-NKMAKUC-2743.0.
- Skip a redundant source-change request when reopening the current HDMI input. Keep the normal switch path when the current source cannot be read.
