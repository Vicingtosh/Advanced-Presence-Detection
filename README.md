# Advanced Presence Detection

![Advanced Presence Detection icon](custom_components/advanced_presence_detection/brand/icon.png)

Advanced Presence Detection creates a presence sensor from the sensors you already have in Home Assistant.

It is meant for rooms where motion alone is not enough. A normal motion sensor can turn off while someone is sitting still, watching TV, working at a desk, using the bathroom, cooking, or doing something else that does not create much movement.

This integration combines motion sensors with one or more **controls**. A control can be a door, but it does not have to be. It can also be a TV, switch, helper, appliance, bed sensor, media activity sensor, or anything else that says "someone is probably still here".

## Features

- Creates one calculated presence binary sensor.
- Supports one or more motion sensors.
- Supports one or more controls.
- Controls can be `binary_sensor` or `switch` entities.
- Each control can use `on` or `off` as its active state.
- The control group can use **all controls active** or **any control active**.
- Each motion sensor can have its own cooldown.
- Grace time keeps presence on while a control changes state.
- Optional no-motion timeout while controls are active.
- Optional no-motion delay while controls are not active.
- Includes troubleshooting attributes.
- Includes small debug-only easter eggs.

## Installation With HACS

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Vicingtosh&repository=Advanced-Presence-Detection&category=integration" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

After downloading, restart Home Assistant.

Then add via helpers: 

<a href="https://my.home-assistant.io/redirect/helpers/" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/helpers.svg" alt="Open your Home Assistant instance and show your helper entities." /></a>

## Manual Installation

Copy this folder into your Home Assistant `custom_components` folder:

```text
custom_components/advanced_presence_detection
```

Restart Home Assistant, then add the integration from **Settings > Devices & services**.

## Setup

The integration is set up through the Home Assistant UI.

You choose:

- **Presence sensor name:** the name of the new presence sensor.
- **Controls:** doors, switches, helpers, TVs, appliances, or other entities that can help keep presence on.
- **Motion sensors:** the sensors that detect movement.
- **Starting motion cooldown in seconds:** the default cooldown for motion sensors.
- **Open/close grace time in seconds:** how long presence should stay on while a control changes.
- **Control mode:** whether all controls must be active, or whether one active control is enough.
- **Active no-motion timeout in minutes:** how long presence may stay on after motion stops while controls are active.
- **Inactive no-motion delay in minutes:** how long presence may stay on after motion stops while controls are inactive.

For each control, the setup page shows the friendly name, entity id, and current state. Put the real device in the state that should keep presence on, then choose whether Home Assistant shows that state as `on` or `off`.

For each motion sensor, set the cooldown that matches that sensor. The cooldown starts when the controls become active.

## How It Works

During the grace time, presence stays on. This avoids quick off/on changes when a door opens or closes, or when an activity control changes state.

When the controls are inactive, presence mostly follows motion. If the inactive no-motion delay is set, presence can stay on for a little while after motion stops.

When the controls are active, motion turns presence on. If motion is still on after that motion sensor's cooldown has passed, presence is latched on. Latched presence stays on until the controls become inactive, or until the active no-motion timeout expires.

If motion turns off before the cooldown has passed, presence turns off unless it was already latched.

## Examples

- **Watching TV:** use the TV or media player as a control. Set `on` as active and choose **Any**, so presence stays on while someone is watching.
- **Bathroom or toilet:** use the door contact as a control. Set the closed-door state as active, then set a no-motion timeout so presence cannot stay on forever.
- **Kitchen:** combine motion with an extractor fan, oven helper, coffee machine, or other kitchen activity switch.
- **Home office:** use a monitor, PC, desk lamp, or meeting helper so presence stays on during calls or focused work.
- **Laundry room:** use a washer or dryer status helper so presence can stay active while a task is running.
- **Garage or workshop:** combine a door contact with a workbench light, tool outlet, or ventilation switch.
- **Bedroom:** use a closed door, reading lamp, bed sensor, or sleep-mode helper.
- **Media or gaming area:** use a console, projector, amplifier, or scene helper.

## Troubleshooting

Open the generated presence entity in Home Assistant and look at its attributes.

Useful attributes:

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

If a control behaves the wrong way around, check `control_evaluations`. It shows the friendly name, raw state, configured active state, and whether the integration currently sees the control as active.

If cooldown behavior looks wrong, check `motion_evaluations`. It shows each motion sensor's raw state, cooldown, remaining cooldown time, and pending confirmation state.
