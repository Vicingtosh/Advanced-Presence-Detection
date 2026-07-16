"""Repair helpers for Advanced Presence Detection."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .source_graph import source_entity_ids

ISSUE_PREFIX_MISSING_SOURCES = "missing_sources"


def _issue_id(entry: ConfigEntry) -> str:
    """Return the stable issue id for a config entry."""
    return f"{ISSUE_PREFIX_MISSING_SOURCES}_{entry.entry_id}"


@callback
def async_update_missing_source_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Create or clear a repair issue for source entities that no longer exist."""
    entity_registry = er.async_get(hass)
    missing = sorted(
        entity_id
        for entity_id in source_entity_ids(entry)
        if hass.states.get(entity_id) is None
        and entity_registry.async_get(entity_id) is None
    )
    issue_id = _issue_id(entry)

    if not missing:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="missing_source_entities",
        translation_placeholders={
            "helper_name": entry.title,
            "entities": ", ".join(missing),
        },
    )


@callback
def async_delete_missing_source_issue(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Delete a config entry's missing-source repair issue."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry))
