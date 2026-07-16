"""Tests for Advanced Presence Detection configuration flows."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.advanced_presence_detection.const import DOMAIN

MEDIA_PLAYER = "media_player.test_tv"
REMOTE = "remote.test_tv"
LIGHT = "light.test_lamp"
MOTION = "binary_sensor.test_motion"


def _base_input(name: str) -> dict:
    """Return the first setup form values."""
    return {
        "name": name,
        "door_entities": [MEDIA_PLAYER],
        "motion_entities": [MOTION],
        "default_cooldown": 180,
        "fresh_window": 15,
        "control_closed_mode": "any",
        "unavailable_behavior": "mark_unavailable",
        "no_motion_timeout_minutes": 60,
        "open_no_motion_timeout_minutes": 0,
        "show_debug_attributes": False,
    }


async def test_config_flow_stores_multiple_media_states(
    hass: HomeAssistant,
) -> None:
    """The setup wizard stores all selected media-player states."""
    hass.states.async_set(MEDIA_PLAYER, "playing")
    hass.states.async_set(MOTION, "off")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _base_input("Cinema Presence"),
    )
    assert result["step_id"] == "control_state"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"control_active_state": ["playing", "paused"]},
    )
    assert result["step_id"] == "motion_cooldown"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"motion_cooldown": 180},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cinema Presence"
    assert result["data"]["control_active_states"][MEDIA_PLAYER] == [
        "playing",
        "paused",
    ]


async def test_control_state_selector_is_translated_and_rejects_empty(
    hass: HomeAssistant,
) -> None:
    """State choices use translations and require at least one selection."""
    hass.states.async_set(MEDIA_PLAYER, "playing")
    hass.states.async_set(MOTION, "off")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        _base_input("Translated States"),
    )

    state_selector = next(iter(result["data_schema"].schema.values()))
    assert state_selector.config["translation_key"] == "control_active_state"
    assert "standby" not in state_selector.config["options"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"control_active_state": []},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "control_state"
    assert result["errors"]["control_active_state"] == "no_active_states"


async def test_config_flow_accepts_remote_and_light_controls(
    hass: HomeAssistant,
) -> None:
    """The setup wizard accepts remote and light control entities."""
    hass.states.async_set(REMOTE, "off")
    hass.states.async_set(LIGHT, "on")
    hass.states.async_set(MOTION, "off")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    user_input = _base_input("Living Room Presence")
    user_input["door_entities"] = [REMOTE, LIGHT]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    assert result["step_id"] == "control_state"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"control_active_state": ["on"]},
    )
    assert result["step_id"] == "control_state"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"control_active_state": ["on"]},
    )
    assert result["step_id"] == "motion_cooldown"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"motion_cooldown": 180},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["door_entities"] == [REMOTE, LIGHT]
    assert result["data"]["control_active_states"] == {
        REMOTE: ["on"],
        LIGHT: ["on"],
    }


async def test_options_flow_updates_config_entry_title(
    hass: HomeAssistant,
) -> None:
    """Renaming a helper also updates its config-entry title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Old Name",
        data={
            **_base_input("Old Name"),
            "control_active_states": {MEDIA_PLAYER: "playing"},
            "motion_cooldowns": {MOTION: 180},
            "no_motion_timeout": 3600,
            "open_no_motion_timeout": 0,
        },
    )
    entry.add_to_hass(hass)
    hass.states.async_set(MEDIA_PLAYER, "playing")
    hass.states.async_set(MOTION, "off")

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        _base_input("New Name"),
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"control_active_state": ["playing", "paused"]},
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"motion_cooldown": 180},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "New Name"


async def test_config_flow_rejects_same_entity_in_both_source_roles(
    hass: HomeAssistant,
) -> None:
    """One entity cannot be both a control and a motion source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    user_input = _base_input("Invalid Presence")
    user_input["door_entities"] = [MOTION]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["door_entities"] == "same_source_roles"
    assert result["errors"]["motion_entities"] == "same_source_roles"


async def test_options_flow_rejects_presence_entity_as_source(
    hass: HomeAssistant,
) -> None:
    """A helper cannot select its generated entity as a source."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Existing Presence",
        data={
            **_base_input("Existing Presence"),
            "control_active_states": {MEDIA_PLAYER: ["playing"]},
            "motion_cooldowns": {MOTION: 180},
            "no_motion_timeout": 3600,
            "open_no_motion_timeout": 0,
        },
    )
    entry.add_to_hass(hass)
    registry_entry = er.async_get(hass).async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{entry.entry_id}_presence",
        suggested_object_id="existing_presence",
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    user_input = _base_input("Existing Presence")
    user_input["motion_entities"] = [registry_entry.entity_id]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"]["motion_entities"] == "self_reference"


async def test_options_flow_rejects_indirect_presence_cycle(
    hass: HomeAssistant,
) -> None:
    """Two generated presence helpers cannot depend on each other."""
    first = MockConfigEntry(
        domain=DOMAIN,
        title="First Presence",
        data={
            **_base_input("First Presence"),
            "control_active_states": {MEDIA_PLAYER: ["playing"]},
            "motion_cooldowns": {MOTION: 180},
        },
    )
    first.add_to_hass(hass)
    registry = er.async_get(hass)
    first_entity = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{first.entry_id}_presence",
        suggested_object_id="first_presence",
    )

    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second Presence",
        data={
            **_base_input("Second Presence"),
            "door_entities": [first_entity.entity_id],
            "control_active_states": {first_entity.entity_id: ["on"]},
            "motion_cooldowns": {MOTION: 180},
        },
    )
    second.add_to_hass(hass)
    second_entity = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{second.entry_id}_presence",
        suggested_object_id="second_presence",
    )

    result = await hass.config_entries.options.async_init(first.entry_id)
    user_input = _base_input("First Presence")
    user_input["door_entities"] = [second_entity.entity_id]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"]["door_entities"] == "presence_cycle"
