"""Tests for the Advanced Presence Detection state machine."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.advanced_presence_detection.binary_sensor import (
    EASTER_EGG_MESSAGES,
)
from custom_components.advanced_presence_detection.const import DOMAIN

CONTROL = "binary_sensor.test_door"
SECOND_CONTROL = "switch.test_activity"
MOTION = "binary_sensor.test_motion"
MEDIA_PLAYER = "media_player.test_tv"
ENTITY_ID = "binary_sensor.test_presence"


def _entry(
    *,
    control: str = CONTROL,
    active_states: str | list[str] = "on",
    cooldown: int = 30,
    no_motion_timeout: int = 60,
    fresh_window: int = 0,
    control_mode: str = "all",
    unavailable_behavior: str = "mark_unavailable",
    open_no_motion_timeout: int = 0,
    show_debug_attributes: bool = False,
) -> MockConfigEntry:
    """Return a configured test entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Presence",
        data={
            "name": "Test Presence",
            "door_entities": [control],
            "motion_entities": [MOTION],
            "control_active_states": {control: active_states},
            "motion_cooldowns": {MOTION: cooldown},
            "default_cooldown": cooldown,
            "fresh_window": fresh_window,
            "control_closed_mode": control_mode,
            "unavailable_behavior": unavailable_behavior,
            "no_motion_timeout": no_motion_timeout,
            "open_no_motion_timeout": open_no_motion_timeout,
            "show_debug_attributes": show_debug_attributes,
        },
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    control: str = CONTROL,
    control_state: str = "on",
    motion_state: str = "off",
) -> None:
    """Set source states and load one helper."""
    hass.states.async_set(control, control_state)
    hass.states.async_set(MOTION, motion_state)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _presence_state(hass: HomeAssistant) -> State:
    """Return the generated presence state."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    return state


async def test_motion_latches_after_cooldown(hass: HomeAssistant, freezer) -> None:
    """Motion that remains on through cooldown latches presence."""
    entry = _entry(cooldown=30)
    await _setup(hass, entry)

    assert _presence_state(hass).state == "off"
    hass.states.async_set(MOTION, "on")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["latched"] is False

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["latched"] is True


async def test_motion_off_before_cooldown_turns_presence_off(
    hass: HomeAssistant,
) -> None:
    """Motion ending before confirmation does not latch presence."""
    entry = _entry(cooldown=30)
    await _setup(hass, entry, motion_state="on")
    assert _presence_state(hass).state == "on"

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


async def test_media_player_accepts_multiple_active_states(
    hass: HomeAssistant,
) -> None:
    """A media player can remain active while playing or paused."""
    entry = _entry(
        control=MEDIA_PLAYER,
        active_states=["playing", "paused"],
    )
    await _setup(
        hass,
        entry,
        control=MEDIA_PLAYER,
        control_state="paused",
    )
    assert _presence_state(hass).attributes["control_group_active"] is True

    hass.states.async_set(MEDIA_PLAYER, "idle")
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["control_group_active"] is False


async def test_control_grace_keeps_presence_on_after_both_transitions(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Opening and closing a control each start an unconditional grace window."""
    entry = _entry(fresh_window=15)
    await _setup(hass, entry, control_state="off", motion_state="off")
    assert _presence_state(hass).state == "off"

    hass.states.async_set(CONTROL, "on")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["state_reason"] == (
        "control_closed_or_active"
    )

    freezer.tick(timedelta(seconds=16))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"

    hass.states.async_set(CONTROL, "off")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["state_reason"] == (
        "control_opened_or_not_active"
    )


@pytest.mark.parametrize(
    ("control_mode", "expected_active"),
    [("all", False), ("any", True)],
)
async def test_control_group_all_or_any_mode(
    hass: HomeAssistant,
    control_mode: str,
    expected_active: bool,
) -> None:
    """The selected group rule controls how multiple controls are combined."""
    second_control = "switch.test_activity"
    base_entry = _entry(control_mode=control_mode)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=base_entry.title,
        data={
            **base_entry.data,
            "door_entities": [CONTROL, second_control],
            "control_active_states": {
                CONTROL: ["on"],
                second_control: ["on"],
            },
        },
    )
    hass.states.async_set(CONTROL, "on")
    hass.states.async_set(second_control, "off")
    hass.states.async_set(MOTION, "off")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _presence_state(hass).attributes["control_group_active"] is (expected_active)


async def test_latched_presence_expires_after_no_motion_timeout(
    hass: HomeAssistant,
    freezer,
) -> None:
    """A closed-room latch cannot survive past the configured quiet timeout."""
    entry = _entry(cooldown=1, no_motion_timeout=60)
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


@pytest.mark.parametrize(
    ("unavailable_behavior", "expected_available"),
    [("mark_unavailable", False), ("treat_inactive", True)],
)
async def test_unavailable_source_behavior(
    hass: HomeAssistant,
    unavailable_behavior: str,
    expected_available: bool,
) -> None:
    """Unavailable sources follow the option selected by the user."""
    entry = _entry(unavailable_behavior=unavailable_behavior)
    await _setup(hass, entry)

    hass.states.async_set(MOTION, "unavailable")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == (
        "off" if expected_available else "unavailable"
    )


async def test_treat_unavailable_as_inactive_applies_during_setup(
    hass: HomeAssistant,
) -> None:
    """The inactive fallback does not wait for unavailable startup sources."""
    entry = _entry(unavailable_behavior="treat_inactive")
    await _setup(hass, entry, control_state="unavailable", motion_state="on")

    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["control_group_active"] is False
    assert _presence_state(hass).attributes["latched"] is False


async def test_mark_unavailable_preserves_latch_until_control_recovers(
    hass: HomeAssistant,
    freezer,
) -> None:
    """A temporary control outage must not behave like an open control."""
    entry = _entry(cooldown=1, no_motion_timeout=0)
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    hass.states.async_set(CONTROL, "unavailable")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "unavailable"

    hass.states.async_set(CONTROL, "on")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["latched"] is True


async def test_expired_timer_waits_for_unavailable_control_to_recover(
    hass: HomeAssistant,
    freezer,
) -> None:
    """An expired deadline changes state only after unavailable sources recover."""
    entry = _entry(cooldown=1, no_motion_timeout=60)
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    hass.states.async_set(CONTROL, "unavailable")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "unavailable"

    hass.states.async_set(CONTROL, "on")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


async def test_debug_and_easteregg_attributes_follow_runtime_mode(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Detailed attributes are useful and easter eggs disappear while inactive."""
    entry = _entry(
        cooldown=1,
        no_motion_timeout=0,
        show_debug_attributes=True,
    )
    await _setup(hass, entry)
    attributes = _presence_state(hass).attributes
    assert attributes["show_debug_attributes"] is True
    assert attributes["control_evaluations"][0]["is_active_boolean"] is True
    assert attributes["motion_evaluations"][0]["is_on_boolean"] is False
    assert attributes["easteregg_mode"] == "quiet_watch"
    assert attributes["easteregg_message"] in EASTER_EGG_MESSAGES["quiet_watch"]

    hass.states.async_set(MOTION, "on")
    await hass.async_block_till_done()
    assert "easteregg_mode" not in _presence_state(hass).attributes
    assert "easteregg_message" not in _presence_state(hass).attributes

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    attributes = _presence_state(hass).attributes
    assert attributes["easteregg_mode"] == "stillness_mode"
    assert attributes["easteregg_message"] in EASTER_EGG_MESSAGES["stillness_mode"]


async def test_startup_unavailable_state_does_not_discard_latch(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Startup unavailable-to-usable recovery restores trusted runtime state."""
    entry = _entry(cooldown=1, no_motion_timeout=60)
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_set(CONTROL, "unavailable")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "unavailable"

    hass.states.async_set(CONTROL, "on")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["latched"] is True


async def test_reload_preserves_latch_and_remaining_timeout(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Reloading resumes a latch and its original no-motion deadline."""
    entry = _entry(cooldown=1, no_motion_timeout=60)
    await _setup(hass, entry, motion_state="on")

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"
    assert _presence_state(hass).attributes["latched"] is True

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"


async def test_reload_preserves_inactive_no_motion_deadline(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Reloading resumes the original inactive-control delay deadline."""
    entry = _entry(open_no_motion_timeout=60)
    await _setup(
        hass,
        entry,
        control_state="off",
        motion_state="on",
    )
    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass, dt_util.utcnow())

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"


async def test_reload_preserves_control_grace_deadline(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Reloading resumes control grace with only its remaining time."""
    entry = _entry(fresh_window=30)
    await _setup(hass, entry)
    hass.states.async_set(CONTROL, "off")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass, dt_util.utcnow())
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"

    freezer.tick(timedelta(seconds=21))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"


async def test_reload_discards_runtime_state_after_behavior_change(
    hass: HomeAssistant,
    freezer,
) -> None:
    """A changed configuration must not inherit the previous latch."""
    entry = _entry(cooldown=1, no_motion_timeout=0)
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    hass.config_entries.async_update_entry(
        entry,
        options={"no_motion_timeout": 120},
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


async def test_behavior_change_discards_stale_on_with_inactive_delay(
    hass: HomeAssistant,
    freezer,
) -> None:
    """A mismatched restore signature cannot start a delay from stale ON state."""
    entry = _entry(
        cooldown=1,
        no_motion_timeout=0,
        open_no_motion_timeout=120,
    )
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    hass.states.async_set(MOTION, "off")
    hass.states.async_set(CONTROL, "off")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"

    hass.config_entries.async_update_entry(
        entry,
        options={
            "no_motion_timeout": 120,
            "open_no_motion_timeout": 120,
        },
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


async def test_inactive_delay_uses_continuous_motion_off_time(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Changing a control does not restart how long motion has been off."""
    entry = _entry(
        cooldown=1,
        no_motion_timeout=0,
        open_no_motion_timeout=60,
    )
    await _setup(hass, entry, motion_state="on")
    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=50))
    async_fire_time_changed(hass, dt_util.utcnow())
    hass.states.async_set(CONTROL, "off")
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "on"

    freezer.tick(timedelta(seconds=11))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).state == "off"


async def test_pending_restore_expires_before_late_source_returns(
    hass: HomeAssistant,
    freezer,
) -> None:
    """A late source cannot revive a stale startup latch."""
    base_entry = _entry(cooldown=1, no_motion_timeout=0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=base_entry.title,
        data={
            **base_entry.data,
            "door_entities": [CONTROL, SECOND_CONTROL],
            "control_active_states": {
                CONTROL: ["on"],
                SECOND_CONTROL: ["on"],
            },
        },
    )
    hass.states.async_set(CONTROL, "on")
    hass.states.async_set(SECOND_CONTROL, "on")
    hass.states.async_set(MOTION, "on")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_remove(SECOND_CONTROL)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    hass.states.async_set(SECOND_CONTROL, "on")
    await hass.async_block_till_done()

    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


async def test_new_activity_discards_pending_restore_snapshot(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Current source activity takes precedence over an old restore snapshot."""
    base_entry = _entry(cooldown=1, no_motion_timeout=0)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=base_entry.title,
        data={
            **base_entry.data,
            "door_entities": [CONTROL, SECOND_CONTROL],
            "control_active_states": {
                CONTROL: ["on"],
                SECOND_CONTROL: ["on"],
            },
        },
    )
    hass.states.async_set(CONTROL, "on")
    hass.states.async_set(SECOND_CONTROL, "on")
    hass.states.async_set(MOTION, "on")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert _presence_state(hass).attributes["latched"] is True

    hass.states.async_set(MOTION, "off")
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_remove(SECOND_CONTROL)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(CONTROL, "off")
    await hass.async_block_till_done()
    hass.states.async_set(CONTROL, "on")
    await hass.async_block_till_done()
    hass.states.async_set(SECOND_CONTROL, "on")
    await hass.async_block_till_done()

    assert _presence_state(hass).state == "off"
    assert _presence_state(hass).attributes["latched"] is False


async def test_runtime_ignores_self_referential_motion_source(
    hass: HomeAssistant,
) -> None:
    """Malformed stored data cannot make the presence entity follow itself."""
    base_entry = _entry()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=base_entry.title,
        data={
            **base_entry.data,
            "motion_entities": [ENTITY_ID],
            "motion_cooldowns": {ENTITY_ID: 30},
        },
    )
    hass.states.async_set(CONTROL, "on")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert _presence_state(hass).state == "unavailable"


async def test_helper_creates_visible_virtual_device(hass: HomeAssistant) -> None:
    """The helper belongs to a normal virtual device, not a service entry."""
    entry = _entry()
    await _setup(hass, entry)

    registry = dr.async_get(hass)
    device = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    assert device is not None
    assert device.entry_type is None
    assert device.name == "Test Presence"


async def test_existing_service_device_is_migrated_in_place(
    hass: HomeAssistant,
) -> None:
    """An old hidden service device becomes a normal visible device."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    old_device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Test Presence",
        entry_type=DeviceEntryType.SERVICE,
    )
    hass.states.async_set(CONTROL, "on")
    hass.states.async_set(MOTION, "off")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    migrated = registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})

    assert migrated is not None
    assert migrated.id == old_device.id
    assert migrated.entry_type is None
