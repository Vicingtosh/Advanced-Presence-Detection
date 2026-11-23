## Advanced Presence Detection 0.9.6

Advanced Presence Detection 0.9.6 adds an event-based master reset for presence detection, updates the documentation for Marketplace, and expands diagnostics and compatibility testing.

### Added

- Added a **Master reset entity (optional)** setting to setup and helper options. When the selected entity turns off, presence turns off once and all timers and latches are cleared.
- Master-reset entities can be `binary_sensor`, `switch`, `input_boolean`, `fan`, `light`, `remote`, or `media_player`.
- Added `master_reset_entity` and `master_reset_state` attributes when **Show debug attributes** is enabled. The compact `state_reason` attribute shows `master_reset` after a reset, until normal source activity resumes.
- Extended circular-dependency checks, missing-source Repairs, and privacy-conscious diagnostics to include the master-reset entity.
- Added a changelog linked from the README, alongside links to the latest published release notes and the complete release history.

### Changed

The master reset responds to a turn-off event, not a continuing off state. It cancels cooldown confirmations, grace periods, and no-motion timers, and clears the current latch. Later motion or control events follow the normal presence rules, even while the master remains off. Turning it on does nothing.

An already-off state at startup or reload, off-to-off attribute updates, and recovery from unknown/unavailable do not trigger a reset. A missing or unavailable master does not affect presence detection or availability. Normal control and motion sources retain their configured unavailable-source behavior.

Master-reset labels and explanations are available in all 14 included languages.

Installation instructions, badges, and visible validation workflow names now use **Marketplace** terminology. Required technical filenames and action identifiers remain compatible with the catalog tooling.

Restored the traditional parenthesized exception-handler style for older Python tooling and configured the formatter to preserve it. Runtime behavior is unchanged.

Added code comments explaining the legacy configuration keys and the protection against an empty control group creating a latch.

### Validation

- Expanded automated tests for turn-off resets during grace periods, cooldowns, latches, no-motion timers, reloads, and source outages. Tests also verify normal detection while the master remains off and that startup, recovery, and attribute updates do not replay a reset.
- Added tests for master-reset setup, removal through options, self-reference and circular-dependency prevention, diagnostics redaction, and missing-source Repairs.
- Added regression tests for malformed numeric settings, value limits, and configurations without controls.
- Updated device-registration tests to avoid deprecated Home Assistant API calls.
- Added Home Assistant `2026.10.4` to the automated test matrix.
- All **63 tests pass** on Home Assistant `2026.3.1`, `2026.6.4`, `2026.7.2`, and `2026.10.4`, with approximately **93% code coverage**.
- All **63 tests also pass** against the actual Home Assistant `2026.11.2` runtime using a temporary adapter for the older test harness. A matching published test package is still needed before adding this version to the regular CI matrix.
- Code linting, formatting, JSON, workflow YAML, and translation consistency checks pass.

### Compatibility

Existing configurations remain compatible. No manual configuration changes are required.

The master-reset setting is optional and unset by default. Selecting it does not enable or disable presence detection. The setting can also be removed later through the helper options.

Marketplace installation instructions apply to Home Assistant `2026.11` and later. Existing installations and manual installation remain available on earlier supported versions.
