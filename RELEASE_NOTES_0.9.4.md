## Advanced Presence Detection 0.9.4

Advanced Presence Detection 0.9.4 adds support for more control entity types, introduces multilingual setup screens, and keeps presence entity attributes lighter by default.

### Added

* Controls can now use the following entity types:

  * `binary_sensor`
  * `switch`
  * `input_boolean`
  * `fan`
* Added a **Show debug attributes** option. This is disabled by default.
* Added dark-theme icon and logo assets.
* Added translations for:

  * Dutch
  * French
  * German
  * Italian
  * Spanish
  * Portuguese
  * Brazilian Portuguese
  * Polish
  * Czech
  * Ukrainian
  * Russian
  * Simplified Chinese
  * Arabic

### Changed

Presence entities now expose fewer attributes by default.

When **Show debug attributes** is disabled, the presence entity only exposes:

* `state_reason`
* `latched`
* `control_group_active`
* `unavailable_entities`

Enable **Show debug attributes** in the helper options when you need detailed source states, evaluations, timers, cooldowns, and pending confirmations.

### Fixed

* 🐛 Fixed a recursion error that could prevent newly created presence entities from loading and leave them marked as no longer provided by the integration.

### Compatibility

Existing configurations remain compatible.

After upgrading, detailed debug attributes are disabled by default. No manual configuration changes are required.
