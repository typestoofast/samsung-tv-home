# Changelog

## [Unreleased]

### Added

- Real Q70T photo extracted from the owner's video, cropped and stripped of metadata for the upstream showcase.
- Agent setup workflow: discover HDMI sources and installed apps, resolve uncertain names, collect local logos, and stage a private home screen for that household.
- Read-only discovery script, offline setup-plan generator, and validation that blocks staging until missing identities and logos are resolved.
- One to eight generated shortcuts with actual input ports and installed app IDs, local logo attribution, and D-pad navigation across two rows when needed. Prepared as 0.3.0; not installed on the test TV.
- Optional bounded local startup tracing and a private staging tool. Normal staged builds omit the recorder.
- Local four-shortcut dashboard with D-pad navigation and access to Samsung Home.
- HDMI label matching and import of native source names during packaging.
- Bounded device requests with cancellation and stale-callback protection.
- Source-built Q70T Home companion, offline package builder, and full routing-snapshot comparison.
- Tested Samsung cleanup findings, recovery procedure, and explicit compatibility limits.

### Changed

- Record installation of 0.2.2, the owner's successful Home/navigation/Apple TV test, and one diagnostic run with clearly scoped app timings.
- Record that the physical Home route survived one long-Power restart; automatic startup failed in that trial.
- Show four destination logos without a greeting, numbered cards, or repeated captions.
- Identify the Nintendo console as Switch 2.
- Remove manual HDMI assignment from the TV interface.

### Fixed

- Reject ambiguous or contradictory live input names instead of opening a stale saved port. Follow a unique saved device name when it moves to another port.
- Keep source discovery independent of app launches and input handoffs. Queue an early HDMI selection until discovery completes, and cancel it on Back or when Four hides. Installed on the test Q70T; cancellation and the remaining destinations still need hardware checks.
- Reuse verified in-memory inputs on return while refreshing their state asynchronously.
- Replace Samsung's existing short-Home target instead of adding a parallel rule that also opens Samsung's bar. Physically confirmed on QN65Q70TAFXZC, T-NKMAKUC-2743.0.
- Skip a redundant source-change request when reopening the current HDMI input. Keep the normal switch path when the current source cannot be read.
