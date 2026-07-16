"""Source dependency helpers for Advanced Presence Detection."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CONTROL_ENTITIES,
    CONF_MOTION_ENTITIES,
    CONTROL_ENTITY_DOMAINS,
    DOMAIN,
)


def normalise_entity_ids(value: Any, allowed_domains: set[str]) -> list[str]:
    """Return supported entity IDs from stored configuration data."""
    if isinstance(value, str):
        candidates: Iterable[Any] = [value]
    else:
        try:
            candidates = list(value)
        except TypeError:
            return []

    entity_ids: list[str] = []
    for candidate in candidates:
        entity_id = str(candidate)
        domain, separator, _object_id = entity_id.partition(".")
        if separator and domain in allowed_domains and entity_id not in entity_ids:
            entity_ids.append(entity_id)
    return entity_ids


def source_entity_ids(entry: ConfigEntry) -> list[str]:
    """Return normalized source entities selected by a config entry."""
    config = {**entry.data, **entry.options}
    return list(
        dict.fromkeys(
            [
                *normalise_entity_ids(
                    config.get(CONF_CONTROL_ENTITIES, []),
                    set(CONTROL_ENTITY_DOMAINS),
                ),
                *normalise_entity_ids(
                    config.get(CONF_MOTION_ENTITIES, []),
                    {"binary_sensor"},
                ),
            ]
        )
    )


def _presence_entry_id_for_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> str | None:
    """Return the owning presence config entry for a generated entity."""
    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry is None or registry_entry.platform != DOMAIN:
        return None
    if registry_entry.config_entry_id is not None:
        return registry_entry.config_entry_id

    suffix = "_presence"
    if registry_entry.unique_id.endswith(suffix):
        candidate = registry_entry.unique_id[: -len(suffix)]
        if any(
            entry.entry_id == candidate
            for entry in hass.config_entries.async_entries(DOMAIN)
        ):
            return candidate
    return None


def source_entry_ids(
    hass: HomeAssistant,
    entity_ids: Iterable[str],
) -> set[str]:
    """Return presence config entries represented by selected source entities."""
    return {
        entry_id
        for entity_id in entity_ids
        if (entry_id := _presence_entry_id_for_entity(hass, entity_id)) is not None
    }


def source_ids_causing_cycle(
    hass: HomeAssistant,
    owner_entry_id: str,
    selected_source_ids: Iterable[str],
) -> set[str]:
    """Return selected source entities that lead back to their owner."""
    entries = {
        entry.entry_id: entry for entry in hass.config_entries.async_entries(DOMAIN)
    }

    def reaches_owner(start_entry_id: str) -> bool:
        pending = [start_entry_id]
        visited: set[str] = set()
        while pending:
            entry_id = pending.pop()
            if entry_id == owner_entry_id:
                return True
            if entry_id in visited:
                continue
            visited.add(entry_id)
            entry = entries.get(entry_id)
            if entry is not None:
                pending.extend(
                    source_entry_ids(hass, source_entity_ids(entry)) - visited
                )
        return False

    return {
        entity_id
        for entity_id in selected_source_ids
        if (
            (source_entry_id := _presence_entry_id_for_entity(hass, entity_id))
            is not None
            and reaches_owner(source_entry_id)
        )
    }
