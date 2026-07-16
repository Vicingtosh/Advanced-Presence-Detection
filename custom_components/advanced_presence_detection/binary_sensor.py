"""Binary sensor platform for Advanced Presence Detection."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from hashlib import sha256
from random import choice
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTROL_ACTIVE_STATES,
    CONF_CONTROL_CLOSED_MODE,
    CONF_CONTROL_ENTITIES,
    CONF_DEFAULT_COOLDOWN,
    CONF_FRESH_WINDOW,
    CONF_MOTION_COOLDOWNS,
    CONF_MOTION_ENTITIES,
    CONF_NO_MOTION_TIMEOUT,
    CONF_OPEN_NO_MOTION_TIMEOUT,
    CONF_SHOW_DEBUG_ATTRIBUTES,
    CONF_UNAVAILABLE_BEHAVIOR,
    CONTROL_CLOSED_MODE_ALL,
    CONTROL_CLOSED_MODE_ANY,
    CONTROL_ENTITY_DOMAINS,
    DEFAULT_CONTROL_CLOSED_MODE,
    DEFAULT_COOLDOWN,
    DEFAULT_FRESH_WINDOW,
    DEFAULT_NAME,
    DEFAULT_NO_MOTION_TIMEOUT,
    DEFAULT_OPEN_NO_MOTION_TIMEOUT,
    DEFAULT_SHOW_DEBUG_ATTRIBUTES,
    DEFAULT_UNAVAILABLE_BEHAVIOR,
    DOMAIN,
    MAX_CONTROL_GRACE_TIME,
    MAX_COOLDOWN,
    MAX_TIMEOUT_SECONDS,
    MIN_CONTROL_GRACE_TIME,
    MIN_COOLDOWN,
    MIN_TIMEOUT_SECONDS,
    UNAVAILABLE_BEHAVIOR_MARK_UNAVAILABLE,
    UNAVAILABLE_BEHAVIOR_TREAT_INACTIVE,
)
from .source_graph import normalise_entity_ids, source_ids_causing_cycle

UNKNOWN_STATES = {STATE_UNKNOWN, STATE_UNAVAILABLE}
VALID_CONTROL_CLOSED_MODES = {CONTROL_CLOSED_MODE_ALL, CONTROL_CLOSED_MODE_ANY}
VALID_UNAVAILABLE_BEHAVIORS = {
    UNAVAILABLE_BEHAVIOR_MARK_UNAVAILABLE,
    UNAVAILABLE_BEHAVIOR_TREAT_INACTIVE,
}
RESTORE_SOURCE_WAIT_SECONDS = 60
EASTER_EGG_MESSAGES: dict[str, tuple[str, ...]] = {
    "stillness_mode": (
        "Presence retained. Someone is probably just very still.",
        "Still here, just not giving the motion sensor much to work with.",
        "Presence is holding. The room passed the quiet test.",
        "No fresh motion, but the room still has a good reason to believe.",
        "Holding presence. Some rooms are better at patience than motion sensors.",
    ),
    "quiet_watch": (
        "No confirmed presence. Waiting for motion.",
        "Quiet for now. The next motion event gets the floor.",
        "No presence latched. The room is standing by.",
        "Nothing to report yet. Motion gets the final word.",
        "Presence is off. The sensor is keeping a polite eye on things.",
    ),
}


def _normalise_active_states(value: Any) -> frozenset[str]:
    """Return one or more usable active states from old or new config data."""
    if isinstance(value, str):
        candidates = [value]
    else:
        try:
            candidates = list(value)
        except TypeError:
            candidates = []

    states = {
        str(candidate)
        for candidate in candidates
        if str(candidate) and str(candidate) not in UNKNOWN_STATES
    }
    return frozenset(states or {STATE_ON})


class PresenceExtraStoredData(ExtraStoredData):
    """Restorable runtime state for one presence entity."""

    def __init__(
        self,
        *,
        config_signature: str,
        latched: bool,
        closed_since: str | None,
        control_grace_reason: str | None,
        control_grace_started_at: str | None,
        control_grace_ends_at: str | None,
        no_motion_started_at: str | None,
        no_motion_ends_at: str | None,
        open_no_motion_started_at: str | None,
        open_no_motion_ends_at: str | None,
        open_no_motion_expired: bool,
        motion_off_since: str | None,
    ) -> None:
        """Initialize stored runtime data."""
        self.config_signature = config_signature
        self.latched = latched
        self.closed_since = closed_since
        self.control_grace_reason = control_grace_reason
        self.control_grace_started_at = control_grace_started_at
        self.control_grace_ends_at = control_grace_ends_at
        self.no_motion_started_at = no_motion_started_at
        self.no_motion_ends_at = no_motion_ends_at
        self.open_no_motion_started_at = open_no_motion_started_at
        self.open_no_motion_ends_at = open_no_motion_ends_at
        self.open_no_motion_expired = open_no_motion_expired
        self.motion_off_since = motion_off_since

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-serializable restore data."""
        return {
            "version": 3,
            "config_signature": self.config_signature,
            "latched": self.latched,
            "closed_since": self.closed_since,
            "control_grace_reason": self.control_grace_reason,
            "control_grace_started_at": self.control_grace_started_at,
            "control_grace_ends_at": self.control_grace_ends_at,
            "no_motion_started_at": self.no_motion_started_at,
            "no_motion_ends_at": self.no_motion_ends_at,
            "open_no_motion_started_at": self.open_no_motion_started_at,
            "open_no_motion_ends_at": self.open_no_motion_ends_at,
            "open_no_motion_expired": self.open_no_motion_expired,
            "motion_off_since": self.motion_off_since,
        }

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> PresenceExtraStoredData | None:
        """Return validated restore data from Home Assistant storage."""
        if restored.get("version") not in (2, 3):
            return None

        def optional_string(key: str) -> str | None:
            value = restored.get(key)
            return value if isinstance(value, str) else None

        return cls(
            config_signature=optional_string("config_signature") or "",
            latched=restored.get("latched") is True,
            closed_since=optional_string("closed_since"),
            control_grace_reason=optional_string("control_grace_reason"),
            control_grace_started_at=optional_string("control_grace_started_at"),
            control_grace_ends_at=optional_string("control_grace_ends_at"),
            no_motion_started_at=optional_string("no_motion_started_at"),
            no_motion_ends_at=optional_string("no_motion_ends_at"),
            open_no_motion_started_at=optional_string("open_no_motion_started_at"),
            open_no_motion_ends_at=optional_string("open_no_motion_ends_at"),
            open_no_motion_expired=restored.get("open_no_motion_expired") is True,
            motion_off_since=optional_string("motion_off_since"),
        )


def _bounded_int(
    value: Any,
    default: int,
    lower: int,
    upper: int,
) -> int:
    """Return an integer limited to the allowed range."""
    try:
        number = int(value)
    except TypeError, ValueError:
        return default

    return max(lower, min(upper, number))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Advanced Presence Detection binary sensor."""
    async_add_entities([AdvancedPresenceDetectionBinarySensor(entry)])


class AdvancedPresenceDetectionBinarySensor(BinarySensorEntity, RestoreEntity):
    """Presence sensor with control, grace, and motion cooldown logic."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        self._entry = entry
        self._config = {**entry.data, **entry.options}
        self._controls = normalise_entity_ids(
            self._config.get(CONF_CONTROL_ENTITIES, []),
            set(CONTROL_ENTITY_DOMAINS),
        )
        self._motions = normalise_entity_ids(
            self._config.get(CONF_MOTION_ENTITIES, []),
            {"binary_sensor"},
        )
        raw_active_states = self._config.get(CONF_CONTROL_ACTIVE_STATES, {})
        if not isinstance(raw_active_states, dict):
            raw_active_states = {}
        self._control_active_states: dict[str, frozenset[str]] = {
            str(entity_id): _normalise_active_states(active_states)
            for entity_id, active_states in raw_active_states.items()
            if str(entity_id) in self._controls
        }
        self._control_closed_mode = str(
            self._config.get(CONF_CONTROL_CLOSED_MODE, DEFAULT_CONTROL_CLOSED_MODE)
        )
        if self._control_closed_mode not in VALID_CONTROL_CLOSED_MODES:
            self._control_closed_mode = DEFAULT_CONTROL_CLOSED_MODE
        self._unavailable_behavior = str(
            self._config.get(CONF_UNAVAILABLE_BEHAVIOR, DEFAULT_UNAVAILABLE_BEHAVIOR)
        )
        if self._unavailable_behavior not in VALID_UNAVAILABLE_BEHAVIORS:
            self._unavailable_behavior = DEFAULT_UNAVAILABLE_BEHAVIOR
        self._show_debug_attributes = (
            self._config.get(
                CONF_SHOW_DEBUG_ATTRIBUTES,
                DEFAULT_SHOW_DEBUG_ATTRIBUTES,
            )
            is True
        )
        self._default_cooldown = _bounded_int(
            self._config.get(CONF_DEFAULT_COOLDOWN, DEFAULT_COOLDOWN),
            DEFAULT_COOLDOWN,
            MIN_COOLDOWN,
            MAX_COOLDOWN,
        )
        self._control_grace_time = _bounded_int(
            self._config.get(CONF_FRESH_WINDOW, DEFAULT_FRESH_WINDOW),
            DEFAULT_FRESH_WINDOW,
            MIN_CONTROL_GRACE_TIME,
            MAX_CONTROL_GRACE_TIME,
        )
        self._no_motion_timeout = _bounded_int(
            self._config.get(CONF_NO_MOTION_TIMEOUT, DEFAULT_NO_MOTION_TIMEOUT),
            DEFAULT_NO_MOTION_TIMEOUT,
            MIN_TIMEOUT_SECONDS,
            MAX_TIMEOUT_SECONDS,
        )
        self._open_no_motion_timeout = _bounded_int(
            self._config.get(
                CONF_OPEN_NO_MOTION_TIMEOUT,
                DEFAULT_OPEN_NO_MOTION_TIMEOUT,
            ),
            DEFAULT_OPEN_NO_MOTION_TIMEOUT,
            MIN_TIMEOUT_SECONDS,
            MAX_TIMEOUT_SECONDS,
        )
        raw_cooldowns = self._config.get(CONF_MOTION_COOLDOWNS, {})
        if not isinstance(raw_cooldowns, dict):
            raw_cooldowns = {}
        self._cooldowns = {
            str(entity_id): _bounded_int(
                seconds,
                self._default_cooldown,
                MIN_COOLDOWN,
                MAX_COOLDOWN,
            )
            for entity_id, seconds in raw_cooldowns.items()
        }

        self._is_on: bool | None = False
        self._latched = False
        self._control_group_inactive: bool | None = None
        self._closed_since: datetime | None = None
        self._unsub_callbacks: list[Callable[[], None]] = []
        self._pending_confirmations: dict[str, Callable[[], None]] = {}
        self._control_grace_unsub: Callable[[], None] | None = None
        self._control_grace_reason: str | None = None
        self._control_grace_started_at: datetime | None = None
        self._control_grace_ends_at: datetime | None = None
        self._no_motion_unsub: Callable[[], None] | None = None
        self._no_motion_started_at: datetime | None = None
        self._no_motion_ends_at: datetime | None = None
        self._open_no_motion_unsub: Callable[[], None] | None = None
        self._open_no_motion_started_at: datetime | None = None
        self._open_no_motion_ends_at: datetime | None = None
        self._open_no_motion_expired = False
        self._motion_on_since: dict[str, datetime] = {}
        self._motion_off_since: datetime | None = None
        self._pending_restore_data: PresenceExtraStoredData | None = None
        self._pending_restore_unsub: Callable[[], None] | None = None
        self._waiting_for_sources = False
        self._sources_ready = False
        self._runtime_suspended = False
        self._last_usable_motion_on: bool | None = None
        self._invalid_source_entities: list[str] = []
        self._easteregg_current_mode: str | None = None
        self._easteregg_current_message: str | None = None
        self._easteregg_last_message_by_mode: dict[str, str] = {}

        name = str(self._config.get("name", DEFAULT_NAME))
        self._attr_unique_id = f"{entry.entry_id}_presence"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=name,
            manufacturer="Advanced Presence Detection",
            model="Virtual presence sensor",
            # Explicitly clear the old service classification so existing
            # registry entries are migrated to visible virtual devices.
            entry_type=None,
        )

    @property
    def extra_restore_state_data(self) -> PresenceExtraStoredData:
        """Return runtime state that should survive reloads and restarts."""
        return PresenceExtraStoredData(
            config_signature=self._configuration_signature(),
            latched=self._latched,
            closed_since=self._datetime_iso(self._closed_since),
            control_grace_reason=self._control_grace_reason,
            control_grace_started_at=self._datetime_iso(self._control_grace_started_at),
            control_grace_ends_at=self._datetime_iso(self._control_grace_ends_at),
            no_motion_started_at=self._datetime_iso(self._no_motion_started_at),
            no_motion_ends_at=self._datetime_iso(self._no_motion_ends_at),
            open_no_motion_started_at=self._datetime_iso(
                self._open_no_motion_started_at
            ),
            open_no_motion_ends_at=self._datetime_iso(self._open_no_motion_ends_at),
            open_no_motion_expired=self._open_no_motion_expired,
            motion_off_since=self._datetime_iso(self._motion_off_since),
        )

    @property
    def available(self) -> bool:
        """Return if all configured source entities are available."""
        if not self._controls or not self._motions:
            return False
        if self._treat_unavailable_as_inactive:
            return True
        return not self._unavailable_entities()

    @property
    def is_on(self) -> bool | None:
        """Return true if occupied."""
        return self._is_on

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return compact attributes and optional diagnostics."""
        control_group_inactive = self._control_group_is_inactive()
        unavailable_entities = self._unavailable_entities()
        attributes = {
            "state_reason": self._state_reason(control_group_inactive),
            "latched": self._latched,
            "control_group_active": not control_group_inactive,
            "unavailable_entities": unavailable_entities,
        }
        if not self._show_debug_attributes:
            return attributes

        now = dt_util.utcnow()
        attributes.update(
            {
                "control_entities": self._controls,
                "control_states": self._entity_states(self._controls),
                "control_active_states": self._effective_control_active_states(),
                "control_evaluations": self._control_evaluations(),
                "control_active_mode": self._control_closed_mode,
                "motion_entities": self._motions,
                "motion_states": self._entity_states(self._motions),
                "motion_cooldowns": self._effective_motion_cooldowns(),
                "motion_evaluations": self._motion_evaluations(now),
                "motion_off_since": self._datetime_iso(self._motion_off_since),
                "default_cooldown": self._default_cooldown,
                "closed_since": self._datetime_iso(self._closed_since),
                "control_grace_time": self._control_grace_time,
                "control_grace_active": self._control_grace_active,
                "control_grace_reason": self._control_grace_reason,
                "control_grace_started_at": self._datetime_iso(
                    self._control_grace_started_at
                ),
                "control_grace_ends_at": self._datetime_iso(
                    self._control_grace_ends_at
                ),
                "control_grace_remaining_seconds": self._remaining_seconds(
                    now, self._control_grace_ends_at
                ),
                "fresh_window": self._control_grace_time,
                "fresh_window_active": self._control_grace_active,
                "no_motion_timeout": self._no_motion_timeout,
                "no_motion_timeout_minutes": round(self._no_motion_timeout / 60, 2),
                "no_motion_timer_active": self._no_motion_timer_active,
                "no_motion_started_at": self._datetime_iso(self._no_motion_started_at),
                "no_motion_ends_at": self._datetime_iso(self._no_motion_ends_at),
                "no_motion_remaining_seconds": self._remaining_seconds(
                    now, self._no_motion_ends_at
                ),
                "open_no_motion_timeout": self._open_no_motion_timeout,
                "open_no_motion_timeout_minutes": round(
                    self._open_no_motion_timeout / 60, 2
                ),
                "open_no_motion_timer_active": self._open_no_motion_timer_active,
                "open_no_motion_expired": self._open_no_motion_expired,
                "open_no_motion_started_at": self._datetime_iso(
                    self._open_no_motion_started_at
                ),
                "open_no_motion_ends_at": self._datetime_iso(
                    self._open_no_motion_ends_at
                ),
                "open_no_motion_remaining_seconds": self._remaining_seconds(
                    now, self._open_no_motion_ends_at
                ),
                "control_group": (
                    "open_or_off" if control_group_inactive else "closed_or_active"
                ),
                "provisional_on": self._provisional_on(control_group_inactive),
                "provisional_reason": self._provisional_reason(control_group_inactive),
                "unavailable_behavior": self._unavailable_behavior,
                "unavailable_entity_count": len(unavailable_entities),
                "pending_confirmation_sensors": sorted(self._pending_confirmations),
                "show_debug_attributes": True,
            }
        )
        if self._easteregg_current_mode is not None:
            attributes["easteregg_mode"] = self._easteregg_current_mode
            attributes["easteregg_message"] = self._easteregg_current_message

        return attributes

    @property
    def _control_grace_active(self) -> bool:
        """Return true if a control grace timer is active."""
        return self._control_grace_unsub is not None

    @property
    def _treat_unavailable_as_inactive(self) -> bool:
        """Return true when unavailable sources should be ignored as inactive."""
        return self._unavailable_behavior == UNAVAILABLE_BEHAVIOR_TREAT_INACTIVE

    @property
    def _no_motion_timer_active(self) -> bool:
        """Return true if the closed-session no-motion timer is active."""
        return self._no_motion_unsub is not None

    @property
    def _open_no_motion_timer_active(self) -> bool:
        """Return true if the open or not-active no-motion timer is active."""
        return self._open_no_motion_unsub is not None

    async def async_added_to_hass(self) -> None:
        """Register state listeners and restore state."""
        await super().async_added_to_hass()
        self._remove_invalid_source_references()
        last_state = await self.async_get_last_state()

        restored_data = None
        if (last_extra_data := await self.async_get_last_extra_data()) is not None:
            restored_data = PresenceExtraStoredData.from_dict(last_extra_data.as_dict())
        if (
            restored_data is not None
            and restored_data.config_signature != self._configuration_signature()
        ):
            restored_data = None
        if (
            restored_data is not None
            and last_state is not None
            and last_state.state in ("on", "off")
        ):
            self._is_on = last_state.state == "on"
        else:
            self._is_on = False

        watched_entities = [*self._controls, *self._motions]
        self._unsub_callbacks.append(
            async_track_state_change_event(
                self.hass,
                watched_entities,
                self._async_state_changed,
            )
        )

        if not self._all_sources_usable() and not self._treat_unavailable_as_inactive:
            self._start_pending_restore(restored_data)
            self._async_publish_state()
            return

        self._sources_ready = True
        if restored_data is not None:
            self._async_restore_after_startup_or_reload(restored_data)
        else:
            self._async_recompute_after_startup_or_reload()
        self._remember_usable_source_summary()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up listeners."""
        self._cancel_all_pending_confirmations()
        self._cancel_control_grace_timer()
        self._cancel_no_motion_timer()
        self._cancel_open_no_motion_timer()
        for unsub in self._unsub_callbacks:
            unsub()
        self._unsub_callbacks.clear()
        self._motion_on_since.clear()
        self._cancel_pending_restore()
        await super().async_will_remove_from_hass()

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle a source entity state change."""
        entity_id = event.data["entity_id"]
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")

        if self._waiting_for_sources:
            if self._is_meaningful_usable_change(old_state, new_state):
                self._pending_restore_data = None
                self._is_on = False

            if self._all_sources_usable():
                restored_data = self._consume_pending_restore()
                self._sources_ready = True
                if restored_data is None:
                    self._async_recompute_after_startup_or_reload()
                else:
                    self._async_restore_after_startup_or_reload(restored_data)
                self._remember_usable_source_summary()
            else:
                self._async_publish_state()
            return

        if self._should_suspend_for_unavailable_sources():
            self._runtime_suspended = True
            self._async_publish_state()
            return

        if self._runtime_suspended:
            self._runtime_suspended = False
            self._async_resume_after_unavailable()
            self._remember_usable_source_summary()
            return

        if old_state is None or new_state is None:
            self._async_recompute_after_startup_or_reload()
            self._remember_usable_source_summary()
            return

        if entity_id in self._controls:
            self._async_handle_control_change(entity_id, old_state, new_state)
            self._remember_usable_source_summary()
            return

        if entity_id in self._motions:
            self._async_handle_motion_change(entity_id, old_state, new_state)
            self._remember_usable_source_summary()

    @callback
    def _async_handle_control_change(
        self,
        entity_id: str,
        old_state: State,
        new_state: State,
    ) -> None:
        """Handle a control entity state change."""
        was_group_inactive = self._control_group_inactive
        is_group_inactive = self._control_group_is_inactive()

        self._control_group_inactive = is_group_inactive
        self._async_apply_control_group_transition(
            was_group_inactive,
            is_group_inactive,
        )

    @callback
    def _async_apply_control_group_transition(
        self,
        was_group_inactive: bool | None,
        is_group_inactive: bool,
    ) -> None:
        """Apply an aggregate control-group transition."""

        if is_group_inactive:
            self._closed_since = None
            self._latched = False
            self._cancel_all_pending_confirmations()
            self._cancel_no_motion_timer()
            if was_group_inactive is False:
                self._start_control_grace("control_opened_or_not_active")
                if self._any_motion_on():
                    self._cancel_open_no_motion_timer()
                else:
                    self._start_open_no_motion_timer()
                return
            self._async_refresh_state()
            return

        if was_group_inactive is True:
            self._closed_since = dt_util.utcnow()
            self._latched = False
            self._cancel_no_motion_timer()
            self._cancel_open_no_motion_timer()
            self._start_control_grace("control_closed_or_active")
            self._schedule_confirmations_for_current_motion()
            return

        self._async_refresh_state()

    @callback
    def _async_resume_after_unavailable(self) -> None:
        """Resume from the last trusted state after every source recovers."""
        previous_group_inactive = self._control_group_inactive
        previous_motion_on = self._last_usable_motion_on
        current_group_inactive = self._calculate_control_group_inactive()
        current_motion_on = self._any_motion_on_direct()

        if current_motion_on:
            self._motion_off_since = None
        elif previous_motion_on is True or self._motion_off_since is None:
            # The exact transition time is unknowable while a source is unavailable.
            self._motion_off_since = dt_util.utcnow()

        self._control_group_inactive = current_group_inactive
        if (
            previous_group_inactive is not None
            and previous_group_inactive != current_group_inactive
        ):
            self._async_apply_control_group_transition(
                previous_group_inactive,
                current_group_inactive,
            )
            return

        self._resume_deferred_control_grace()

        if current_group_inactive:
            self._latched = False
            self._cancel_all_pending_confirmations()
            self._cancel_no_motion_timer()
            if current_motion_on:
                self._cancel_open_no_motion_timer()
            else:
                self._resume_or_start_open_no_motion_timer()
        else:
            self._cancel_open_no_motion_timer()
            if self._latched:
                if current_motion_on:
                    self._cancel_no_motion_timer()
                else:
                    self._resume_or_start_no_motion_timer()
            else:
                self._schedule_confirmations_for_current_motion()

        self._async_refresh_state()

    @callback
    def _async_handle_motion_change(
        self,
        entity_id: str,
        old_state: State,
        new_state: State,
    ) -> None:
        """Handle a motion sensor state change."""
        self._update_motion_tracking(entity_id, old_state, new_state)

        if self._control_group_is_inactive():
            self._closed_since = None
            self._latched = False
            self._cancel_pending_confirmation(entity_id)
            self._cancel_no_motion_timer()
            if new_state.state == STATE_ON:
                self._cancel_open_no_motion_timer()
            elif not self._any_motion_on():
                self._start_open_no_motion_timer()
            self._async_refresh_state()
            return

        if new_state.state == STATE_ON:
            self._cancel_no_motion_timer()
            self._cancel_open_no_motion_timer()
            self._schedule_motion_confirmation(entity_id)
            self._async_refresh_state()
            return

        self._cancel_pending_confirmation(entity_id)
        if not self._any_motion_on():
            self._cancel_all_pending_confirmations()
            if self._latched:
                self._start_no_motion_timer()
        else:
            self._cancel_no_motion_timer()
        self._async_refresh_state()

    @callback
    def _async_restore_after_startup_or_reload(
        self, restored: PresenceExtraStoredData
    ) -> None:
        """Restore safe runtime state and resume timers with remaining time."""
        self._motion_off_since = self._restore_datetime(restored.motion_off_since)
        self._synchronize_motion_off_since()
        self._control_group_inactive = self._control_group_is_inactive()
        self._cancel_all_pending_confirmations()
        self._cancel_control_grace_timer()
        self._cancel_no_motion_timer()
        self._cancel_open_no_motion_timer()

        now = dt_util.utcnow()
        grace_started_at = self._restore_datetime(restored.control_grace_started_at)
        grace_ends_at = self._restore_datetime(restored.control_grace_ends_at)

        if self._control_group_inactive:
            self._closed_since = None
            self._latched = False
            self._open_no_motion_expired = restored.open_no_motion_expired

            if (
                restored.control_grace_reason
                and grace_ends_at is not None
                and grace_ends_at > now
            ):
                self._start_control_grace(
                    restored.control_grace_reason,
                    started_at=grace_started_at,
                    ends_at=grace_ends_at,
                )

            if not self._any_motion_on() and self._is_on:
                open_started_at = self._restore_datetime(
                    restored.open_no_motion_started_at
                )
                open_ends_at = self._restore_datetime(restored.open_no_motion_ends_at)
                if open_ends_at is not None and open_ends_at > now:
                    self._start_open_no_motion_timer(
                        started_at=open_started_at,
                        ends_at=open_ends_at,
                    )
                elif open_ends_at is not None:
                    self._open_no_motion_expired = True
                elif not self._open_no_motion_expired:
                    self._start_open_no_motion_timer()

            self._async_refresh_state()
            return

        self._open_no_motion_expired = False
        self._closed_since = self._restore_datetime(restored.closed_since) or now
        self._latched = restored.latched

        if (
            restored.control_grace_reason
            and grace_ends_at is not None
            and grace_ends_at > now
        ):
            self._start_control_grace(
                restored.control_grace_reason,
                started_at=grace_started_at,
                ends_at=grace_ends_at,
            )

        if self._latched and not self._any_motion_on():
            no_motion_started_at = self._restore_datetime(restored.no_motion_started_at)
            no_motion_ends_at = self._restore_datetime(restored.no_motion_ends_at)
            if self._no_motion_timeout <= 0:
                pass
            elif no_motion_ends_at is not None and no_motion_ends_at > now:
                self._start_no_motion_timer(
                    started_at=no_motion_started_at,
                    ends_at=no_motion_ends_at,
                )
            elif no_motion_ends_at is not None:
                self._latched = False
            else:
                self._start_no_motion_timer()

        if not self._latched:
            self._schedule_confirmations_for_current_motion()

        self._async_refresh_state()

    @callback
    def _async_recompute_after_startup_or_reload(self) -> None:
        """Recompute state after startup or reload."""
        self._synchronize_motion_off_since()
        self._control_group_inactive = self._control_group_is_inactive()
        self._latched = False
        self._cancel_all_pending_confirmations()
        self._cancel_control_grace_timer()
        self._cancel_no_motion_timer()
        self._cancel_open_no_motion_timer()

        if self._control_group_inactive:
            self._closed_since = None
            if not self._any_motion_on() and self._is_on:
                self._start_open_no_motion_timer()
        else:
            self._closed_since = dt_util.utcnow()
            self._schedule_confirmations_for_current_motion()

        self._async_refresh_state()

    @callback
    def _async_refresh_state(self) -> None:
        """Apply the presence rules and write the entity state."""
        if self._should_suspend_for_unavailable_sources():
            self._async_publish_state()
            return

        control_group_inactive = self._control_group_is_inactive()
        self._control_group_inactive = control_group_inactive

        if self._control_grace_active:
            self._async_set_is_on(True)
            return

        if control_group_inactive:
            self._closed_since = None
            self._latched = False
            self._cancel_all_pending_confirmations()
            self._cancel_no_motion_timer()
            if self._any_motion_on():
                self._cancel_open_no_motion_timer()
                self._async_set_is_on(True)
                return
            if self._open_no_motion_timer_active:
                self._async_set_is_on(True)
                return
            if self._open_no_motion_expired:
                self._async_set_is_on(False)
                return
            if self._is_on and self._open_no_motion_timeout > 0:
                self._start_open_no_motion_timer()
                self._async_set_is_on(True)
                return
            self._async_set_is_on(False)
            return

        if self._closed_since is None:
            self._closed_since = dt_util.utcnow()

        if self._latched:
            if self._any_motion_on():
                self._cancel_no_motion_timer()
            else:
                self._start_no_motion_timer()
            self._async_set_is_on(True)
            return

        self._async_set_is_on(self._any_motion_on())

    @callback
    def _async_set_is_on(self, value: bool) -> None:
        """Set the presence state and write attributes."""
        self._is_on = value
        if self.hass is not None:
            self._async_publish_state()

    @callback
    def _async_publish_state(self) -> None:
        """Update derived attributes and write the entity state."""
        self._update_easteregg_state()
        self.async_write_ha_state()

    def _effective_control_active_states(self) -> dict[str, str | list[str]]:
        """Return the configured active states for every control entity."""
        result: dict[str, str | list[str]] = {}
        for entity_id in self._controls:
            states = sorted(
                self._control_active_states.get(entity_id, frozenset({STATE_ON}))
            )
            result[entity_id] = states[0] if len(states) == 1 else states
        return result

    def _effective_motion_cooldowns(self) -> dict[str, int]:
        """Return the configured cooldown for every motion sensor."""
        return {entity_id: self._cooldown_for(entity_id) for entity_id in self._motions}

    def _entity_states(self, entity_ids: list[str]) -> dict[str, str | None]:
        """Return current Home Assistant states for debug attributes."""
        states: dict[str, str | None] = {}
        for entity_id in entity_ids:
            state = self.hass.states.get(entity_id)
            states[entity_id] = None if state is None else state.state
        return states

    def _all_sources_usable(self) -> bool:
        """Return true once every configured source has a usable state."""
        return all(
            not self._entity_is_unavailable(entity_id)
            for entity_id in [*self._controls, *self._motions]
        )

    @staticmethod
    def _is_meaningful_usable_change(
        old_state: State | None,
        new_state: State | None,
    ) -> bool:
        """Return true for real source activity, not startup recovery."""
        return bool(
            old_state is not None
            and new_state is not None
            and old_state.state not in UNKNOWN_STATES
            and new_state.state not in UNKNOWN_STATES
            and old_state.state != new_state.state
        )

    def _should_suspend_for_unavailable_sources(self) -> bool:
        """Return true when runtime evaluation must preserve trusted state."""
        return bool(
            self._sources_ready
            and not self._treat_unavailable_as_inactive
            and self._unavailable_entities()
        )

    def _remember_usable_source_summary(self) -> None:
        """Remember the most recent fully usable aggregate source state."""
        if not self._all_sources_usable():
            return
        self._control_group_inactive = self._calculate_control_group_inactive()
        self._last_usable_motion_on = self._any_motion_on_direct()
        self._synchronize_motion_off_since()

    def _configuration_signature(self) -> str:
        """Return a stable fingerprint of settings that affect runtime state."""
        payload = {
            "controls": self._controls,
            "motions": self._motions,
            "control_active_states": {
                entity_id: sorted(
                    self._control_active_states.get(entity_id, frozenset({STATE_ON}))
                )
                for entity_id in self._controls
            },
            "control_closed_mode": self._control_closed_mode,
            "unavailable_behavior": self._unavailable_behavior,
            "default_cooldown": self._default_cooldown,
            "motion_cooldowns": self._effective_motion_cooldowns(),
            "control_grace_time": self._control_grace_time,
            "no_motion_timeout": self._no_motion_timeout,
            "open_no_motion_timeout": self._open_no_motion_timeout,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()

    def _remove_invalid_source_references(self) -> None:
        """Defend against self-references and overlapping stored sources."""
        own_entity_id = self.entity_id
        cyclic_sources = source_ids_causing_cycle(
            self.hass,
            self._entry.entry_id,
            [*self._controls, *self._motions],
        )
        invalid_sources = set(cyclic_sources)
        if own_entity_id in self._controls or own_entity_id in self._motions:
            invalid_sources.add(own_entity_id)
        invalid_sources.update(set(self._controls) & set(self._motions))
        self._invalid_source_entities = sorted(invalid_sources)
        self._controls = [
            entity_id
            for entity_id in self._controls
            if entity_id != own_entity_id and entity_id not in cyclic_sources
        ]
        control_entities = set(self._controls)
        self._motions = [
            entity_id
            for entity_id in self._motions
            if entity_id != own_entity_id
            and entity_id not in control_entities
            and entity_id not in cyclic_sources
        ]

    @callback
    def _start_pending_restore(self, restored: PresenceExtraStoredData | None) -> None:
        """Wait briefly for startup sources before abandoning restore data."""
        self._cancel_pending_restore()
        self._waiting_for_sources = True
        self._pending_restore_data = restored
        self._pending_restore_unsub = async_call_later(
            self.hass,
            RESTORE_SOURCE_WAIT_SECONDS,
            self._async_expire_pending_restore,
        )

    @callback
    def _consume_pending_restore(self) -> PresenceExtraStoredData | None:
        """Return and clear the pending startup restore snapshot."""
        restored = self._pending_restore_data
        if self._pending_restore_unsub is not None:
            self._pending_restore_unsub()
        self._pending_restore_unsub = None
        self._pending_restore_data = None
        self._waiting_for_sources = False
        return restored

    @callback
    def _cancel_pending_restore(self) -> None:
        """Discard a pending startup restore snapshot."""
        if self._pending_restore_unsub is not None:
            self._pending_restore_unsub()
        self._pending_restore_unsub = None
        self._pending_restore_data = None
        self._waiting_for_sources = False

    @callback
    def _async_expire_pending_restore(self, _now: datetime | None = None) -> None:
        """Expire restore data if not every source appeared in time."""
        self._pending_restore_unsub = None
        self._pending_restore_data = None
        self._waiting_for_sources = False
        self._sources_ready = True
        self._is_on = False
        self._async_recompute_after_startup_or_reload()
        self._remember_usable_source_summary()

    def _unavailable_entities(self) -> list[str]:
        """Return configured source entities that are missing or unavailable."""
        return sorted(
            {
                *self._invalid_source_entities,
                *(
                    entity_id
                    for entity_id in [*self._controls, *self._motions]
                    if self._entity_is_unavailable(entity_id)
                ),
            }
        )

    def _entity_is_unavailable(self, entity_id: str) -> bool:
        """Return true if a source entity is missing, unknown, or unavailable."""
        state = self.hass.states.get(entity_id)
        return state is None or state.state in UNKNOWN_STATES

    def _control_evaluations(self) -> list[dict[str, Any]]:
        """Return detailed control debug data."""
        evaluations: list[dict[str, Any]] = []
        for entity_id in self._controls:
            state = self.hass.states.get(entity_id)
            configured_active_states = self._control_active_states.get(
                entity_id, frozenset({STATE_ON})
            )
            configured_active_state_list = sorted(configured_active_states)
            raw_state = None if state is None else state.state
            is_unavailable = self._entity_is_unavailable(entity_id)
            evaluations.append(
                {
                    "entity_id": entity_id,
                    "friendly_name": self._friendly_name(entity_id),
                    "raw_state": raw_state,
                    "is_unavailable_boolean": is_unavailable,
                    "configured_active_state": (
                        configured_active_state_list[0]
                        if len(configured_active_state_list) == 1
                        else None
                    ),
                    "configured_active_states": configured_active_state_list,
                    "is_active_boolean": (
                        not is_unavailable and raw_state in configured_active_states
                    ),
                }
            )
        return evaluations

    def _motion_evaluations(self, now: datetime) -> list[dict[str, Any]]:
        """Return detailed motion debug data."""
        evaluations: list[dict[str, Any]] = []

        for entity_id in self._motions:
            state = self.hass.states.get(entity_id)
            raw_state = None if state is None else state.state
            last_changed = None if state is None else state.last_changed
            is_unavailable = self._entity_is_unavailable(entity_id)
            motion_on_since = self._motion_on_since.get(entity_id)
            cooldown = self._cooldown_for(entity_id)
            state_age = self._age_seconds(now, last_changed)
            cooldown_remaining = None
            if (
                raw_state == STATE_ON
                and self._closed_since is not None
                and not self._control_group_is_inactive()
            ):
                closed_age = (now - self._closed_since).total_seconds()
                cooldown_remaining = max(0.0, round(cooldown - closed_age, 1))

            evaluations.append(
                {
                    "entity_id": entity_id,
                    "friendly_name": self._friendly_name(entity_id),
                    "raw_state": raw_state,
                    "last_changed": self._datetime_iso(last_changed),
                    "is_unavailable_boolean": is_unavailable,
                    "age_seconds": state_age,
                    "motion_on_since": self._datetime_iso(motion_on_since),
                    "motion_on_age_seconds": self._age_seconds(now, motion_on_since),
                    "cooldown_seconds": cooldown,
                    "cooldown_remaining_seconds": cooldown_remaining,
                    "is_on_boolean": self._motion_is_on(entity_id),
                    "pending_confirmation_boolean": entity_id
                    in self._pending_confirmations,
                }
            )

        return evaluations

    def _friendly_name(self, entity_id: str) -> str | None:
        """Return a source entity friendly name."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return None
        friendly_name = state.attributes.get("friendly_name")
        return str(friendly_name) if friendly_name is not None else None

    @staticmethod
    def _datetime_iso(value: datetime | None) -> str | None:
        """Return an ISO formatted datetime."""
        return None if value is None else value.isoformat()

    @staticmethod
    def _restore_datetime(value: str | None) -> datetime | None:
        """Return a valid timezone-aware datetime from restore storage."""
        if value is None:
            return None
        restored = dt_util.parse_datetime(value)
        if restored is None or restored.tzinfo is None:
            return None
        return restored

    @staticmethod
    def _age_seconds(now: datetime, changed_at: datetime | None) -> float | None:
        """Return a rounded age in seconds."""
        if changed_at is None:
            return None
        return round((now - changed_at).total_seconds(), 1)

    @staticmethod
    def _remaining_seconds(now: datetime, ends_at: datetime | None) -> float | None:
        """Return rounded remaining seconds until a timer ends."""
        if ends_at is None:
            return None
        return max(0.0, round((ends_at - now).total_seconds(), 1))

    def _control_group_is_inactive(self) -> bool:
        """Return true if the control group is open or not active."""
        if (
            self._should_suspend_for_unavailable_sources()
            and self._control_group_inactive is not None
        ):
            return self._control_group_inactive
        return self._calculate_control_group_inactive()

    def _calculate_control_group_inactive(self) -> bool:
        """Calculate the control group directly from current source states."""
        return not self._control_group_closed()

    def _control_group_closed(self) -> bool:
        """Return true if the control group is closed or active."""
        if not self._controls:
            return False

        active_states = [
            self._control_is_active(entity_id) for entity_id in self._controls
        ]

        if self._control_closed_mode == CONTROL_CLOSED_MODE_ANY:
            return any(active_states)

        return all(active_states)

    def _control_is_active(self, entity_id: str) -> bool:
        """Return true if one control entity is in its active state."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in UNKNOWN_STATES:
            return False
        return self._state_is_control_active(entity_id, state)

    def _state_is_control_active(self, entity_id: str, state: State) -> bool:
        """Return true if a state is the configured active state."""
        active_states = self._control_active_states.get(
            entity_id, frozenset({STATE_ON})
        )
        return state.state in active_states

    def _any_motion_on(self) -> bool:
        """Return true if any motion sensor is on."""
        if (
            self._should_suspend_for_unavailable_sources()
            and self._last_usable_motion_on is not None
        ):
            return self._last_usable_motion_on
        return self._any_motion_on_direct()

    def _any_motion_on_direct(self) -> bool:
        """Return current motion without unavailable-state suspension."""
        return any(self._motion_is_on(entity_id) for entity_id in self._motions)

    def _motion_is_on(self, entity_id: str) -> bool:
        """Return true if a motion sensor is on."""
        state = self.hass.states.get(entity_id)
        return (
            state is not None
            and state.state not in UNKNOWN_STATES
            and state.state == STATE_ON
        )

    def _cooldown_for(self, entity_id: str) -> int:
        """Return the cooldown for a motion sensor."""
        return int(self._cooldowns.get(entity_id, self._default_cooldown))

    def _state_reason(self, control_group_inactive: bool | None = None) -> str:
        """Return why the presence sensor currently has its state."""
        if control_group_inactive is None:
            control_group_inactive = self._control_group_is_inactive()

        if self._control_grace_active:
            return self._control_grace_reason or "control_grace"
        if control_group_inactive:
            if self._any_motion_on():
                return "open_or_not_active_following_motion"
            if self._open_no_motion_timer_active:
                return "open_or_not_active_waiting_no_motion_delay"
            return "open_or_not_active_no_motion"
        if self._latched:
            if self._no_motion_timer_active:
                return "latched_closed_or_active_waiting_no_motion_timeout"
            return "latched_closed_or_active"
        if self._any_motion_on():
            return "motion_on_waiting_for_active_control_cooldown"
        return "closed_or_active_no_motion"

    def _provisional_on(self, control_group_inactive: bool | None = None) -> bool:
        """Return true if presence is on without a closed-or-active latch."""
        if control_group_inactive is None:
            control_group_inactive = self._control_group_is_inactive()
        return bool(self._is_on and not self._latched)

    def _provisional_reason(
        self,
        control_group_inactive: bool | None = None,
    ) -> str | None:
        """Return why presence is on without being latched."""
        if not self._provisional_on(control_group_inactive):
            return None
        return self._state_reason(control_group_inactive)

    def _easteregg_mode(
        self,
        control_group_inactive: bool | None = None,
    ) -> str | None:
        """Return a harmless easter egg label for quiet states."""
        if control_group_inactive is None:
            control_group_inactive = self._control_group_is_inactive()
        if self._control_grace_active or self._any_motion_on():
            return None
        if self._latched and self._is_on:
            return "stillness_mode"
        if not self._latched and not self._is_on:
            return "quiet_watch"
        return None

    def _update_easteregg_state(self) -> None:
        """Pick a stable easter egg message when the easter egg mode changes."""
        mode = self._easteregg_mode()
        if mode is None:
            self._easteregg_current_mode = None
            self._easteregg_current_message = None
            return

        if mode == self._easteregg_current_mode and self._easteregg_current_message:
            return

        self._easteregg_current_mode = mode
        self._easteregg_current_message = self._select_easteregg_message(mode)

    def _select_easteregg_message(self, mode: str) -> str | None:
        """Return a harmless easter egg message without repeating the last one."""
        messages = EASTER_EGG_MESSAGES.get(mode)
        if not messages:
            return None

        last_message = self._easteregg_last_message_by_mode.get(mode)
        choices = [message for message in messages if message != last_message]
        message = choice(choices or list(messages))
        self._easteregg_last_message_by_mode[mode] = message
        return message

    @callback
    def _update_motion_tracking(
        self,
        entity_id: str,
        old_state: State,
        new_state: State,
    ) -> None:
        """Track per-sensor motion and continuous all-motion-off time."""
        if new_state.state == STATE_ON:
            if old_state.state != STATE_ON:
                self._motion_on_since[entity_id] = new_state.last_changed
        else:
            self._motion_on_since.pop(entity_id, None)

        if self._any_motion_on_direct():
            self._motion_off_since = None
            return

        if self._last_usable_motion_on is True:
            self._motion_off_since = new_state.last_changed
        elif self._motion_off_since is None:
            self._motion_off_since = self._current_motion_off_since()

    def _synchronize_motion_off_since(self) -> None:
        """Keep the continuous all-motion-off timestamp consistent."""
        if self._any_motion_on_direct():
            self._motion_off_since = None
        elif self._motion_off_since is None:
            self._motion_off_since = self._current_motion_off_since()

    def _current_motion_off_since(self) -> datetime:
        """Return when every configured motion source most recently became off."""
        changed_times = [
            state.last_changed
            for entity_id in self._motions
            if (state := self.hass.states.get(entity_id)) is not None
            and state.state == "off"
        ]
        return max(changed_times, default=dt_util.utcnow())

    @callback
    def _schedule_confirmations_for_current_motion(self) -> None:
        """Schedule cooldown confirmations for all motion sensors currently on."""
        for entity_id in self._motions:
            if self._motion_is_on(entity_id):
                self._schedule_motion_confirmation(entity_id)

    @callback
    def _schedule_motion_confirmation(self, entity_id: str) -> None:
        """Schedule confirmation after the control-active cooldown has elapsed."""
        if self._latched or self._control_group_is_inactive():
            self._cancel_pending_confirmation(entity_id)
            return

        state = self.hass.states.get(entity_id)
        if state is None or state.state != STATE_ON:
            self._cancel_pending_confirmation(entity_id)
            return

        now = dt_util.utcnow()
        if self._closed_since is None:
            self._closed_since = now

        cooldown = self._cooldown_for(entity_id)
        closed_age = (now - self._closed_since).total_seconds()
        delay = max(0.0, cooldown - closed_age)

        self._cancel_pending_confirmation(entity_id)

        if delay <= 0:
            self._async_confirm_motion_after_cooldown(entity_id)
            return

        @callback
        def async_confirm_motion(now: datetime) -> None:
            """Confirm one motion source on the Home Assistant event loop."""
            self._async_confirm_motion_after_cooldown(entity_id, now)

        self._pending_confirmations[entity_id] = async_call_later(
            self.hass,
            delay,
            async_confirm_motion,
        )
        self._async_publish_state()

    @callback
    def _async_confirm_motion_after_cooldown(
        self,
        entity_id: str,
        now: datetime | None = None,
    ) -> None:
        """Latch presence if motion is still on after its cooldown."""
        self._pending_confirmations.pop(entity_id, None)

        if self._should_suspend_for_unavailable_sources():
            self._async_publish_state()
            return

        if self._control_group_is_inactive():
            self._async_refresh_state()
            return

        if self._motion_is_on(entity_id):
            self._latched = True
            self._cancel_all_pending_confirmations()
            self._cancel_no_motion_timer()
            self._async_refresh_state()
            return

        self._async_refresh_state()

    @callback
    def _resume_deferred_control_grace(self) -> None:
        """Resume a grace timer whose callback fired during an outage."""
        if self._control_grace_unsub is not None:
            return
        reason = self._control_grace_reason
        started_at = self._control_grace_started_at
        ends_at = self._control_grace_ends_at
        if reason is None or ends_at is None:
            return
        if ends_at <= dt_util.utcnow():
            self._control_grace_reason = None
            self._control_grace_started_at = None
            self._control_grace_ends_at = None
            return
        self._start_control_grace(
            reason,
            started_at=started_at,
            ends_at=ends_at,
        )

    @callback
    def _resume_or_start_no_motion_timer(self) -> None:
        """Resume the active-control timer or start it from motion-off time."""
        self._start_no_motion_timer(
            started_at=self._no_motion_started_at,
            ends_at=self._no_motion_ends_at,
        )

    @callback
    def _resume_or_start_open_no_motion_timer(self) -> None:
        """Resume the inactive-control timer or start it from motion-off time."""
        self._start_open_no_motion_timer(
            started_at=self._open_no_motion_started_at,
            ends_at=self._open_no_motion_ends_at,
        )

    @callback
    def _start_control_grace(
        self,
        reason: str,
        *,
        started_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> None:
        """Keep presence on for the configured control grace time."""
        self._cancel_control_grace_timer()

        if self._control_grace_time <= 0:
            self._async_refresh_state()
            return

        now = dt_util.utcnow()
        delay = (
            self._control_grace_time
            if ends_at is None
            else max(0.0, (ends_at - now).total_seconds())
        )
        if delay <= 0:
            self._async_refresh_state()
            return

        self._control_grace_reason = reason
        self._control_grace_started_at = started_at or now
        self._control_grace_ends_at = ends_at or now + timedelta(seconds=delay)
        self._control_grace_unsub = async_call_later(
            self.hass,
            delay,
            self._async_end_control_grace,
        )
        self._async_set_is_on(True)

    @callback
    def _start_no_motion_timer(
        self,
        *,
        started_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> None:
        """Start the closed-or-active no-motion timeout."""
        if self._no_motion_timeout <= 0 or self._no_motion_unsub is not None:
            return

        now = dt_util.utcnow()
        effective_started_at = started_at or self._motion_off_since or now
        effective_ends_at = ends_at or effective_started_at + timedelta(
            seconds=self._no_motion_timeout
        )
        delay = max(0.0, (effective_ends_at - now).total_seconds())
        if delay <= 0:
            self._async_no_motion_timeout()
            return

        self._no_motion_started_at = effective_started_at
        self._no_motion_ends_at = effective_ends_at
        self._no_motion_unsub = async_call_later(
            self.hass,
            delay,
            self._async_no_motion_timeout,
        )
        self._async_publish_state()

    @callback
    def _start_open_no_motion_timer(
        self,
        *,
        started_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> None:
        """Start the open-or-not-active no-motion delay."""
        if (
            self._open_no_motion_timeout <= 0
            or self._open_no_motion_unsub is not None
            or not self._control_group_is_inactive()
            or self._any_motion_on()
        ):
            return

        now = dt_util.utcnow()
        effective_started_at = started_at or self._motion_off_since or now
        effective_ends_at = ends_at or effective_started_at + timedelta(
            seconds=self._open_no_motion_timeout
        )
        delay = max(0.0, (effective_ends_at - now).total_seconds())
        if delay <= 0:
            self._open_no_motion_expired = True
            self._async_refresh_state()
            return

        self._open_no_motion_expired = False
        self._open_no_motion_started_at = effective_started_at
        self._open_no_motion_ends_at = effective_ends_at
        self._open_no_motion_unsub = async_call_later(
            self.hass,
            delay,
            self._async_open_no_motion_timeout,
        )
        self._async_publish_state()

    @callback
    def _async_no_motion_timeout(self, now: datetime | None = None) -> None:
        """Turn presence off after too long with no motion while closed or active."""
        self._no_motion_unsub = None
        if self._should_suspend_for_unavailable_sources():
            self._async_publish_state()
            return

        self._no_motion_started_at = None
        self._no_motion_ends_at = None

        if self._control_group_is_inactive() or self._any_motion_on():
            self._async_refresh_state()
            return

        self._latched = False
        self._cancel_all_pending_confirmations()
        self._async_refresh_state()

    @callback
    def _async_open_no_motion_timeout(self, now: datetime | None = None) -> None:
        """Turn presence off after the inactive no-motion delay."""
        self._open_no_motion_unsub = None
        if self._should_suspend_for_unavailable_sources():
            self._async_publish_state()
            return

        self._open_no_motion_started_at = None
        self._open_no_motion_ends_at = None

        if (
            self._control_grace_active
            or not self._control_group_is_inactive()
            or self._any_motion_on()
        ):
            if self._control_group_is_inactive() and not self._any_motion_on():
                self._open_no_motion_expired = True
            self._async_refresh_state()
            return

        self._open_no_motion_expired = True
        self._async_set_is_on(False)

    @callback
    def _async_end_control_grace(self, now: datetime | None = None) -> None:
        """End the control grace window and apply normal rules."""
        self._control_grace_unsub = None
        if self._should_suspend_for_unavailable_sources():
            self._async_publish_state()
            return

        self._control_grace_reason = None
        self._control_grace_started_at = None
        self._control_grace_ends_at = None
        self._async_refresh_state()

    @callback
    def _cancel_pending_confirmation(self, entity_id: str) -> None:
        """Cancel a pending confirmation for one motion sensor."""
        unsub = self._pending_confirmations.pop(entity_id, None)
        if unsub is not None:
            unsub()

    @callback
    def _cancel_all_pending_confirmations(self) -> None:
        """Cancel all pending confirmations."""
        for unsub in list(self._pending_confirmations.values()):
            unsub()
        self._pending_confirmations.clear()

    @callback
    def _cancel_control_grace_timer(self) -> None:
        """Cancel the control grace timer."""
        if self._control_grace_unsub is not None:
            self._control_grace_unsub()
            self._control_grace_unsub = None
        self._control_grace_reason = None
        self._control_grace_started_at = None
        self._control_grace_ends_at = None

    @callback
    def _cancel_no_motion_timer(self) -> None:
        """Cancel the closed-or-active no-motion timer."""
        if self._no_motion_unsub is not None:
            self._no_motion_unsub()
            self._no_motion_unsub = None
        self._no_motion_started_at = None
        self._no_motion_ends_at = None

    @callback
    def _cancel_open_no_motion_timer(self) -> None:
        """Cancel the open-or-not-active no-motion timer."""
        if self._open_no_motion_unsub is not None:
            self._open_no_motion_unsub()
            self._open_no_motion_unsub = None
        self._open_no_motion_started_at = None
        self._open_no_motion_ends_at = None
        self._open_no_motion_expired = False
