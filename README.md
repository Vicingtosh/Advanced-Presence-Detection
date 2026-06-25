# Advanced Presence Detection

[![HACS Default][hacs-shield]][hacs]
[![Release][release-shield]][releases]
[![Validate HACS][hacs-action-shield]][hacs-action]
[![Hassfest][hassfest-shield]][hassfest-action]
[![License][license-shield]][license]

<!-- Optional badges for later:
[![Downloads][downloads-shield]][releases]
[![Installs][installs-shield]][analytics]
-->

![Advanced Presence Detection icon](custom_components/advanced_presence_detection/brand/icon.png)

Advanced Presence Detection creates a calculated presence sensor from the sensors you already use in Home Assistant.

It is built for rooms where motion alone is not reliable. A normal motion sensor can turn off while someone is sitting still, watching TV, working at a desk, using the bathroom, cooking, or staying in the room without much movement.

This integration combines motion sensors with one or more **controls**. A control is an entity that helps confirm that presence should stay on. Common examples are door contacts, switches, helpers, appliance status sensors, TV activity helpers, bed sensors, or anything else that indicates someone is probably still there.

Controls are configured as `binary_sensor` or `switch` entities. If the real device is a TV, appliance, media player, or other entity type, you can usually expose its useful state through a helper or template entity.

## Features

* Creates one calculated presence binary sensor.
* Supports one or more motion sensors.
* Supports one or more controls.
* Controls can be `binary_sensor` or `switch` entities.
* Each control can use `on` or `off` as its active state.
* The control group can require **all controls active** or **any control active**.
* Each motion sensor can have its own cooldown.
* Grace time keeps presence on while a control changes state.
* Optional no-motion timeout while controls are active.
* Optional no-motion delay while controls are not active.
* Troubleshooting attributes show how the sensor reached its current state.

## Installation With HACS

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=Vicingtosh&repository=Advanced-Presence-Detection&category=integration" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open your Home Assistant instance and open a repository inside the Home Assistant Community Store." /></a>

After downloading, restart Home Assistant.

Then add it via helpers:

<a href="https://my.home-assistant.io/redirect/helpers/" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/helpers.svg" alt="Open your Home Assistant instance and show your helper entities." /></a>

## Manual Installation

Copy this folder into your Home Assistant `custom_components` folder:

```text
custom_components/advanced_presence_detection
```

Restart Home Assistant, then add the integration from **Settings > Devices & services > Helpers**.

## Setup

The integration is configured through the Home Assistant UI.

You choose:

* **Presence sensor name:** the name of the new presence sensor.
* **Controls:** doors, switches, helpers, appliance status entities, or other entities that help keep presence on.
* **Motion sensors:** the sensors that detect movement.
* **Starting motion cooldown in seconds:** the default cooldown for motion sensors.
* **Control change grace time in seconds:** how long presence should stay on while a control changes state.
* **Control mode:** whether all controls must be active, or whether one active control is enough.
* **Unavailable source behavior:** whether missing or unavailable selected entities make the presence sensor unavailable, or simply count as inactive/off.
* **Active no-motion timeout in minutes:** how long presence may stay on after motion stops while controls are active.
* **Inactive no-motion delay in minutes:** how long presence may stay on after motion stops while controls are inactive.

For each control, the setup page shows the friendly name, entity id, and current state. Put the real device in the state that should keep presence on, then choose whether Home Assistant shows that state as `on` or `off`.

For each motion sensor, set the cooldown that matches that sensor. The cooldown starts when the controls become active.

## How It Works

During grace time, presence stays on. This prevents quick off/on changes when a door opens or closes, or when another activity control changes state.

When the controls are inactive, presence mostly follows motion. If the inactive no-motion delay is set, presence can stay on briefly after motion stops.

When the controls are active, motion turns presence on. If motion is still on after that motion sensor's cooldown has passed, presence is latched on. Latched presence stays on until the controls become inactive, or until the active no-motion timeout expires.

If motion turns off before the cooldown has passed, presence turns off unless it was already latched.

## Examples

* **Watching TV:** use the TV state, media activity, or a helper as a control. Set `on` as active and choose **Any**, so presence stays on while someone is watching.
* **Bathroom or toilet:** use the door contact as a control. Set the closed-door state as active, then set a no-motion timeout so presence cannot stay on forever.
* **Kitchen:** combine motion with an extractor fan, oven helper, coffee machine, or other kitchen activity switch.
* **Home office:** use a monitor, PC, desk lamp, or meeting helper so presence stays on during calls or focused work.
* **Laundry room:** use a washer or dryer status helper so presence can stay active while a task is running.
* **Garage or workshop:** combine a door contact with a workbench light, tool outlet, or ventilation switch.
* **Bedroom:** use a closed door, reading lamp, bed sensor, or sleep-mode helper.
* **Media or gaming area:** use a console, projector, amplifier, or scene helper.

## Troubleshooting

Open the generated presence entity in Home Assistant and look at its attributes.

Useful attributes:

* `control_entities`
* `control_states`
* `control_active_states`
* `control_evaluations`
* `control_active_mode`
* `control_group_active`
* `control_group`
* `motion_entities`
* `motion_states`
* `motion_cooldowns`
* `motion_evaluations`
* `control_grace_active`
* `control_grace_remaining_seconds`
* `no_motion_timeout_minutes`
* `no_motion_timer_active`
* `open_no_motion_timeout_minutes`
* `open_no_motion_timer_active`
* `latched`
* `state_reason`
* `provisional_on`
* `unavailable_behavior`
* `unavailable_entities`
* `pending_confirmation_sensors`

If a control behaves the wrong way around, check `control_evaluations`. It shows the friendly name, raw state, configured active state, and whether the integration currently sees the control as active.

If cooldown behavior looks wrong, check `motion_evaluations`. It shows each motion sensor's raw state, cooldown, remaining cooldown time, and pending confirmation state.

[analytics]: https://analytics.home-assistant.io/custom_integrations.json
[downloads-shield]: https://img.shields.io/github/downloads/Vicingtosh/Advanced-Presence-Detection/total?style=for-the-badge
[hacs]: https://www.hacs.xyz/docs/default_repositories
[hacs-action]: https://github.com/Vicingtosh/Advanced-Presence-Detection/actions/workflows/hacs.yml
[hacs-action-shield]: https://img.shields.io/github/actions/workflow/status/Vicingtosh/Advanced-Presence-Detection/hacs.yml?branch=main&label=HACS&style=for-the-badge
[hacs-shield]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[hassfest-action]: https://github.com/Vicingtosh/Advanced-Presence-Detection/actions/workflows/hassfest.yml
[hassfest-shield]: https://img.shields.io/github/actions/workflow/status/Vicingtosh/Advanced-Presence-Detection/hassfest.yml?branch=main&label=Hassfest&style=for-the-badge
[installs-shield]: https://img.shields.io/badge/dynamic/json?style=for-the-badge&color=blue&label=installs&cacheSeconds=3600&url=https://analytics.home-assistant.io/custom_integrations.json&query=$.advanced_presence_detection.total
[license]: https://github.com/Vicingtosh/Advanced-Presence-Detection/blob/main/LICENSE
[license-shield]: https://img.shields.io/github/license/Vicingtosh/Advanced-Presence-Detection?style=for-the-badge
[release-shield]: https://img.shields.io/github/v/release/Vicingtosh/Advanced-Presence-Detection?style=for-the-badge
[releases]: https://github.com/Vicingtosh/Advanced-Presence-Detection/releases
