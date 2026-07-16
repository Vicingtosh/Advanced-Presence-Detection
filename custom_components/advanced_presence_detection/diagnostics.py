"""Diagnostics support for Advanced Presence Detection."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CONTROL_ACTIVE_STATES,
    CONF_CONTROL_ENTITIES,
    CONF_MOTION_COOLDOWNS,
    CONF_MOTION_ENTITIES,
    DOMAIN,
)
from .source_graph import source_entity_ids

TO_REDACT = {
    CONF_CONTROL_ACTIVE_STATES,
    CONF_CONTROL_ENTITIES,
    CONF_MOTION_COOLDOWNS,
    CONF_MOTION_ENTITIES,
    "entity_id",
    "name",
    "title",
}

SAFE_RUNTIME_ATTRIBUTES = {
    "control_group_active",
    "control_grace_active",
    "control_grace_reason",
    "default_cooldown",
    "fresh_window_active",
    "latched",
    "motion_off_since",
    "no_motion_timer_active",
    "open_no_motion_expired",
    "open_no_motion_timer_active",
    "provisional_on",
    "provisional_reason",
    "show_debug_attributes",
    "state_reason",
    "unavailable_behavior",
    "unavailable_entity_count",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return privacy-conscious diagnostics for one helper."""
    registry = er.async_get(hass)
    presence_entity_id = registry.async_get_entity_id(
        "binary_sensor",
        DOMAIN,
        f"{entry.entry_id}_presence",
    )
    presence_state = (
        hass.states.get(presence_entity_id) if presence_entity_id is not None else None
    )

    config = {**entry.data, **entry.options}
    raw_controls = config.get(CONF_CONTROL_ENTITIES, [])
    if isinstance(raw_controls, str):
        controls = {raw_controls}
    else:
        try:
            controls = {str(entity_id) for entity_id in raw_controls}
        except TypeError:
            controls = set()
    active_states = config.get(CONF_CONTROL_ACTIVE_STATES, {})
    if not isinstance(active_states, dict):
        active_states = {}
    cooldowns = config.get(CONF_MOTION_COOLDOWNS, {})
    if not isinstance(cooldowns, dict):
        cooldowns = {}

    sources = []
    for entity_id in source_entity_ids(entry):
        state = hass.states.get(entity_id)
        is_control = entity_id in controls
        sources.append(
            async_redact_data(
                {
                    "entity_id": entity_id,
                    "role": "control" if is_control else "motion",
                    "state": None if state is None else state.state,
                    "available": state is not None
                    and state.state not in ("unknown", "unavailable"),
                    "active_states": (
                        active_states.get(entity_id) if is_control else None
                    ),
                    "cooldown": (None if is_control else cooldowns.get(entity_id)),
                },
                TO_REDACT,
            )
        )

    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "presence": {
            "state": None if presence_state is None else presence_state.state,
            "attributes": (
                {}
                if presence_state is None
                else {
                    key: value
                    for key, value in presence_state.attributes.items()
                    if key in SAFE_RUNTIME_ATTRIBUTES
                }
            ),
        },
        "sources": sources,
    }
