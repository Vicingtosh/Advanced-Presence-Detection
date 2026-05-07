# Advanced Presence Detection

![Advanced Presence Detection icon](custom_components/advanced_presence_detection/brand/icon.png)

Advanced Presence Detection is a Home Assistant custom integration that creates one calculated presence binary sensor from motion sensors plus door or activity controls.

A control can be a door contact, a lock, a TV switch, an appliance switch, a bed sensor, a room mode helper, or another `binary_sensor` or `switch`. For each control you teach the integration which raw state means **closed/active**: a closed door, a TV that is on, a helper that is on, or anything else that should retain presence.

## Features

- One calculated presence binary sensor.
- One or more motion sensors.
- One or more door/activity controls.
- Controls can be `binary_sensor` or `switch` entities.
- Each control can define whether `on` or `off` means closed/active.
- The control group can require all controls to be closed/active, or any one control to be closed/active.
- Each motion sensor has its own cooldown in seconds.
- Door open and door close grace time keeps presence on during transitions.
- Optional no-motion timeout in minutes while closed/active.
- Optional no-motion delay in minutes while open/off.
- Helpful debug attributes for troubleshooting.
- Harmless debug-only easter eggs. They do not affect presence behavior.

## Latest Changes

- Version `0.9.1` keeps the project in the `0.x` version line.
- Updated the integration icon assets.
- Added clearly labelled easter egg attributes.
- Kept this README focused on the latest changes instead of a full version history.

## Installation With HACS

1. Open HACS in Home Assistant.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add this repository URL:

   ```text
   https://github.com/YOUR_GITHUB_USERNAME/advanced_presence_detection
   ```

4. Select **Integration** as the category.
5. Install **Advanced Presence Detection**.
6. Restart Home Assistant.
7. Go to **Settings > Devices & services > Add integration** and search for **Advanced Presence Detection**.

## Manual Installation

Copy this folder into Home Assistant:

```text
custom_components/advanced_presence_detection
```

After copying, restart Home Assistant and add the integration through **Settings > Devices & services**.

## Configuration

The integration is configured through the Home Assistant UI.

During setup you choose:

- **Presence sensor name:** the name for the new binary sensor.
- **Door or activity controls:** entities that decide when presence can be retained.
- **Motion sensors:** entities that detect movement.
- **Starting motion cooldown in seconds:** a default value for motion sensors.
- **Open/close grace time in seconds:** presence stays on during this transition window.
- **How many controls must be closed/active:** choose All or Any.
- **Closed/active no-motion timeout in minutes:** maximum time to keep latched presence after motion stops.
- **Open/off no-motion delay in minutes:** delay before turning off while controls are open/off.

For every control, setup shows the friendly name, entity id, and current raw state. Put the real thing in the state that should retain presence, then choose whether Home Assistant shows `on` or `off` in that state.

For every motion sensor, setup asks for that sensor's cooldown. This cooldown starts when the control group becomes closed/active.

## Behavior

The presence sensor follows these rules:

- During the open/close grace time, presence is always on.
- When controls are open/off, presence follows motion.
- If the open/off no-motion delay is set, presence can stay on for that many minutes after all motion sensors turn off.
- When controls are closed/active, motion immediately turns presence on.
- If motion stays on until that motion sensor's cooldown has passed, presence latches on.
- If motion turns off before its cooldown has passed while controls are closed/active, presence turns off unless it is already latched.
- Once latched while controls are closed/active, presence stays on until the controls open/turn off or the closed/active no-motion timeout expires.

## Useful Examples

- **Watching TV:** use the TV switch as an activity control. Set `on` as closed/active and choose Any, so presence stays on while someone watches TV without moving much.
- **Bathroom or toilet:** use the door contact as a control. Set the closed-door state as closed/active, then use the no-motion timeout to avoid presence staying on forever.
- **Kitchen cooking:** use motion plus an extractor fan, coffee machine, oven helper, or other kitchen activity switch to keep presence on while someone stands still at the counter.
- **Home office:** use a monitor, PC, desk lamp, or meeting helper as an activity control so presence stays on during calls or focused work.
- **Laundry or utility room:** use a washer, dryer, or utility helper so presence can stay active while a task is running and movement is occasional.
- **Garage or workshop:** combine a door contact with a workbench light, tool outlet, or ventilation switch so presence remains reliable during slow tasks.
- **Bedroom quiet time:** use a closed door, reading lamp, or sleep-mode helper to avoid motion-only presence turning off too quickly.
- **Media or gaming area:** use a console, projector, amplifier, or scene helper as the activity control.

## Troubleshooting

Open the generated presence entity in Home Assistant and inspect its attributes.

Useful attributes include:

- `control_entities`
- `control_states`
- `control_active_states`
- `control_evaluations`
- `control_active_mode`
- `control_group_active`
- `control_group`
- `motion_entities`
- `motion_states`
- `motion_cooldowns`
- `motion_evaluations`
- `door_grace_active`
- `door_grace_remaining_seconds`
- `no_motion_timeout_minutes`
- `no_motion_timer_active`
- `open_no_motion_timeout_minutes`
- `open_no_motion_timer_active`
- `latched`
- `state_reason`
- `provisional_on`
- `easteregg_mode`
- `easteregg_message`
- `pending_confirmation_sensors`

If the control group does not behave as expected, check `control_evaluations`. It shows each control's friendly name, raw state, configured active state, and whether the integration currently sees it as active.

If cooldown behavior does not behave as expected, check `motion_evaluations`. It shows each motion sensor's raw state, cooldown, cooldown remaining time, and whether that sensor has a pending confirmation.

## Known Limitation

Advanced Presence Detection only sees the states exposed to Home Assistant. If a physical motion sensor keeps its Home Assistant binary sensor `on` during its own internal cooldown, this integration cannot see the hidden raw motion event directly.

The integration works around that by starting its own cooldown when the controls become closed/active. If the motion entity is still `on` after that cooldown, presence is treated as confirmed. If the motion entity turns `off` before that cooldown finishes, presence is not latched.

## HACS Repository Notes

This repository is prepared for HACS custom repository use and possible default-store submission:

- `hacs.json` is in the repository root.
- Exactly one integration is under `custom_components/advanced_presence_detection`.
- `manifest.json` includes `domain`, `name`, `documentation`, `issue_tracker`, `codeowners`, `config_flow`, `iot_class`, and `version`.
- Local brand assets are included under `custom_components/advanced_presence_detection/brand`.
- HACS and hassfest validation workflows are included under `.github/workflows`.
- A GitHub release should be created for each published version. For this version, use release tag `v0.9.1`.

Before publishing, replace `YOUR_GITHUB_USERNAME` in `manifest.json` and this README with the real GitHub owner name. Also make sure the GitHub repository is public, has a description, has topics, and has issues enabled.
