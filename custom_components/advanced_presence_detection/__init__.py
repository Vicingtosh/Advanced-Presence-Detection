"""Advanced Presence Detection custom integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_entity_registry_updated_event,
    async_track_state_change_event,
)

from .const import PLATFORMS
from .repairs import (
    async_delete_missing_source_issue,
    async_update_missing_source_issue,
)
from .source_graph import source_entity_ids


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Advanced Presence Detection from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def update_missing_sources(_event: Event | None = None) -> None:
        """Refresh the repair issue after source registry or state changes."""
        async_update_missing_source_issue(hass, entry)

    @callback
    def begin_missing_source_monitoring(_now: object | None = None) -> None:
        """Start Repairs monitoring after source integrations have loaded."""
        update_missing_sources()
        if sources:
            entry.async_on_unload(
                async_track_state_change_event(hass, sources, update_missing_sources)
            )
            entry.async_on_unload(
                async_track_entity_registry_updated_event(
                    hass,
                    sources,
                    update_missing_sources,
                )
            )

    sources = source_entity_ids(entry)

    if hass.state is CoreState.running:
        begin_missing_source_monitoring()
    else:

        @callback
        def schedule_missing_source_check(_event: Event) -> None:
            """Give source integrations time to publish their initial states."""
            entry.async_on_unload(
                async_call_later(
                    hass,
                    60,
                    begin_missing_source_monitoring,
                )
            )

        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                schedule_missing_source_check,
            )
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        async_delete_missing_source_issue(hass, entry)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove repair issues belonging to a deleted helper."""
    async_delete_missing_source_issue(hass, entry)
