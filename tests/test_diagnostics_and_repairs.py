"""Tests for diagnostics and repair reporting."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.advanced_presence_detection.const import DOMAIN
from custom_components.advanced_presence_detection.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.advanced_presence_detection.repairs import (
    async_update_missing_source_issue,
)

CONTROL = "binary_sensor.private_door"
MOTION = "binary_sensor.private_motion"


def _entry() -> MockConfigEntry:
    """Return a minimal configured helper."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Private Room",
        data={
            "name": "Private Room",
            "door_entities": [CONTROL],
            "motion_entities": [MOTION],
            "control_active_states": {CONTROL: ["on"]},
            "motion_cooldowns": {MOTION: 30},
            "default_cooldown": 30,
            "fresh_window": 0,
            "control_closed_mode": "all",
            "unavailable_behavior": "mark_unavailable",
            "no_motion_timeout": 3600,
            "open_no_motion_timeout": 0,
            "show_debug_attributes": False,
        },
    )


async def test_diagnostics_redact_names_and_source_ids(
    hass: HomeAssistant,
) -> None:
    """Diagnostics retain useful state while redacting private identifiers."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.states.async_set(CONTROL, "on")
    hass.states.async_set(MOTION, "off")
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    rendered = str(diagnostics)
    assert "Private Room" not in rendered
    assert CONTROL not in rendered
    assert MOTION not in rendered
    assert diagnostics["sources"][0]["state"] == "on"


async def test_repair_tracks_sources_that_no_longer_exist(
    hass: HomeAssistant,
) -> None:
    """A repair appears for removed entities and clears when they return."""
    entry = _entry()
    entry.add_to_hass(hass)

    async_update_missing_source_issue(hass, entry)
    registry = ir.async_get(hass)
    issue_id = f"missing_sources_{entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    hass.states.async_set(CONTROL, "unavailable")
    hass.states.async_set(MOTION, "off")
    async_update_missing_source_issue(hass, entry)
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_repair_treats_registered_sources_without_states_as_existing(
    hass: HomeAssistant,
) -> None:
    """Registry entries without runtime states are not reported as deleted."""
    entry = _entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    control = registry.async_get_or_create(
        "binary_sensor",
        "test",
        "private_door",
        suggested_object_id="private_door",
    )
    motion = registry.async_get_or_create(
        "binary_sensor",
        "test",
        "private_motion",
        suggested_object_id="private_motion",
    )
    assert control.entity_id == CONTROL
    assert motion.entity_id == MOTION

    async_update_missing_source_issue(hass, entry)

    issue_id = f"missing_sources_{entry.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_repair_waits_for_startup_and_tracks_registry_deletion(
    hass: HomeAssistant,
    freezer,
) -> None:
    """Monitoring starts after grace and observes registry-only deletion."""
    hass.set_state(CoreState.starting)
    entry = _entry()
    entry.add_to_hass(hass)
    entity_registry = er.async_get(hass)
    motion = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "private_motion",
        suggested_object_id="private_motion",
    )
    assert motion.entity_id == MOTION
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = ir.async_get(hass)
    issue_id = f"missing_sources_{entry.entry_id}"
    assert registry.async_get_issue(DOMAIN, issue_id) is None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    hass.states.async_set(CONTROL, "on")
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is None

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is None

    entity_registry.async_remove(MOTION)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, issue_id) is not None
