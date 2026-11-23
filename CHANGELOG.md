# Changelog

## 0.9.6 - Unreleased

### Added

- Optional master-reset entity in setup and options. A real transition from a
  known state to `off` turns presence off once, clears latches, and cancels timers.
- The continuing off state does not block detection. Subsequent motion/control
  events follow normal rules, and turning the master on has no effect.
- Startup/reload with an already-off master, unknown/unavailable recovery, and
  off-to-off attribute updates do not trigger resets.
- Master-reset support for `binary_sensor`, `switch`, `input_boolean`, `fan`,
  `light`, `remote`, and `media_player` entities.
- Included the master entity in cycle checks, missing-source Repairs, and
  privacy-conscious diagnostics. Its state, including unknown/unavailable, does
  not affect normal presence detection or availability.
- Added master-reset labels and explanations to all 14 included translations.

### Changed

- Updated installation instructions, badges, and validation workflow wording
  from HACS to Marketplace. Required technical filenames and action identifiers
  remain compatible with the catalog tooling.
- Parenthesized multiple exception types for clearer compatibility with older
  Python tooling while retaining identical behavior on Home Assistant's Python
  version. The formatter now preserves this style.
- Documented the legacy `door_entities` and `fresh_window` storage keys that are
  intentionally retained for existing configurations.
- Documented why an empty control group cannot create a presence latch.
- Added README links to current development changes, the latest published
  release notes, and the complete release history.
- Prepared `RELEASE_NOTES_0.9.6.md` using the published release-note style.

### Tests

- Added regression coverage for malformed and out-of-range stored numeric
  values.
- Added regression coverage for entries that unexpectedly contain no controls.
- Added regression coverage ensuring easter-egg messages do not repeat
  consecutively.
- Added master-reset coverage for grace periods, cooldowns, latches, both
  no-motion timers, reloads, unavailable sources, configuration flows, cycle
  prevention, diagnostics redaction, and Repairs. Verified that later activity
  works with the master still off and that non-reset events have no effect.
- Corrected the no-controls regression test to expect the existing unavailable
  entity behavior.
- Updated device-registry assertions to avoid deprecated lookup methods, and
  added Home Assistant 2026.10.4 to the automated test matrix.

### Local Validation - 2026-11-23

- All 63 tests passed on Home Assistant 2026.3.1, 2026.6.4, 2026.7.2, and
  2026.10.4 using Python 3.14.10, with approximately 93% integration coverage.
- Ruff lint and formatting checks passed. All JSON and workflow YAML parsed,
  and translation keys and placeholders matched across all 14 languages.
- All 63 tests also passed against the actual Home Assistant 2026.11.2 runtime,
  with 92.75% coverage. This local compatibility run used test plugin 0.13.375
  with its Home Assistant version pin overridden. The temporary test runner
  imported Home Assistant before pytest (to initialize HTTP library aliases)
  and forwarded the moved logger cleanup helper from its new location. No
  integration behavior or test assertions were changed for this run.
- The 2026.11.2 run reported one test-runner warning about assertion rewriting
  in the already imported third-party `anyio` module. An officially matched
  test plugin is still needed before adding 2026.11.2 to the regular CI matrix.
