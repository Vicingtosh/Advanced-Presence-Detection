## Advanced Presence Detection 0.9.5

Advanced Presence Detection 0.9.5 improves control support, device visibility, restart behavior, diagnostics, and maintainability.

### Added

- Added direct `light`, `remote`, and `media_player` control support.

  Thanks to @raetha for requesting this in issue #1 and for the useful examples of TVs, remotes, and lights as presence controls.

  The complete supported control list is now:

- `binary_sensor`
- `switch`
- `input_boolean`
- `fan`
- `light`
- `remote`
- `media_player`

- Controls can now use multiple active states, such as `playing` and `paused`.

- Added privacy-conscious downloadable diagnostics.

- Added Home Assistant Repair warnings when configured source entities are deleted.

- Added automated tests for:

- cooldown confirmation
- early motion-off behavior
- media player, remote, and light controls
- reload persistence
- device registration
- configuration flows
- diagnostics
- repairs

- Added a GitHub Actions test workflow.

### Changed

Presence helpers now appear as normal virtual devices under **Devices** instead of hidden service entries.

Existing service entries are migrated in place, preserving their device identifiers and entity associations.

Latches, grace periods, and no-motion timer deadlines are now restored after reloads and restarts.

Restored runtime state now waits for source integrations to finish loading before it is evaluated.

Renaming a helper now also updates its Home Assistant configuration entry title.

The setup and options flows now share one wizard implementation.

The setup wizard uses the control's current state as its default active state when possible.

Setup wording and Repair messages were updated in every included translation.

### Fixed

- Prevented restored latches and timers from being reused after behavior-defining settings are changed.
- Limited startup restoration waits and prevented old snapshots from overwriting newer source activity.
- Prevented a generated presence entity from using itself as a source.
- Rejected entities selected as both controls and motion sensors.
- Prevented false missing-source Repairs while Home Assistant is still loading, or when a source exists in the entity registry but is disabled.
- Updated the test workflow to the Python version required by Home Assistant 2026.6 and pinned the matching Home Assistant test package.

### Compatibility

Existing configurations remain compatible.

Previously stored single active states are accepted automatically and are converted to the new multi-state format when the helper options are saved.
