"""Config flow for Advanced Presence Detection."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
    CONTROL_ENTITY_DOMAINS,
    CONTROL_CLOSED_MODE_ALL,
    CONTROL_CLOSED_MODE_ANY,
    DEFAULT_COOLDOWN,
    DEFAULT_CONTROL_CLOSED_MODE,
    DEFAULT_FRESH_WINDOW,
    DEFAULT_NAME,
    DEFAULT_NO_MOTION_TIMEOUT,
    DEFAULT_OPEN_NO_MOTION_TIMEOUT,
    DEFAULT_SHOW_DEBUG_ATTRIBUTES,
    DEFAULT_UNAVAILABLE_BEHAVIOR,
    DOMAIN,
    MAX_CONTROL_GRACE_TIME,
    MAX_COOLDOWN,
    MAX_TIMEOUT_MINUTES,
    MIN_CONTROL_GRACE_TIME,
    MIN_COOLDOWN,
    MIN_TIMEOUT_MINUTES,
    UNAVAILABLE_BEHAVIOR_MARK_UNAVAILABLE,
    UNAVAILABLE_BEHAVIOR_TREAT_INACTIVE,
)

FIELD_CONTROL_ACTIVE_STATE = "control_active_state"
FIELD_MOTION_COOLDOWN = "motion_cooldown"
FIELD_NO_MOTION_TIMEOUT_MINUTES = "no_motion_timeout_minutes"
FIELD_OPEN_NO_MOTION_TIMEOUT_MINUTES = "open_no_motion_timeout_minutes"
OPEN_STATE_CHOICES = [STATE_ON, STATE_OFF]
CLOSED_MODE_CHOICES = [CONTROL_CLOSED_MODE_ALL, CONTROL_CLOSED_MODE_ANY]
UNAVAILABLE_BEHAVIOR_CHOICES = [
    UNAVAILABLE_BEHAVIOR_MARK_UNAVAILABLE,
    UNAVAILABLE_BEHAVIOR_TREAT_INACTIVE,
]


def _entity_ids(value: Any, allowed_domains: set[str]) -> list[str]:
    """Return valid entity ids from selector data."""
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    else:
        try:
            candidates = list(value)
        except TypeError:
            return []

    entity_ids: list[str] = []
    for candidate in candidates:
        entity_id = str(candidate)
        domain, separator, _object_id = entity_id.partition(".")
        if separator and domain in allowed_domains:
            entity_ids.append(entity_id)

    return entity_ids


def _bounded_int(
    value: Any,
    default: int,
    lower: int,
    upper: int,
) -> int:
    """Return an integer limited to the allowed range."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default

    return max(lower, min(upper, number))


def _bounded_minutes_from_seconds(value: Any, default_seconds: int) -> int:
    """Return stored seconds as bounded whole minutes."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = default_seconds

    return _bounded_int(
        seconds / 60,
        int(default_seconds / 60),
        MIN_TIMEOUT_MINUTES,
        MAX_TIMEOUT_MINUTES,
    )


def _normalise_base_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise the first form input."""
    control_closed_mode = str(
        user_input.get(CONF_CONTROL_CLOSED_MODE, DEFAULT_CONTROL_CLOSED_MODE)
    )
    if control_closed_mode not in CLOSED_MODE_CHOICES:
        control_closed_mode = DEFAULT_CONTROL_CLOSED_MODE

    unavailable_behavior = str(
        user_input.get(CONF_UNAVAILABLE_BEHAVIOR, DEFAULT_UNAVAILABLE_BEHAVIOR)
    )
    if unavailable_behavior not in UNAVAILABLE_BEHAVIOR_CHOICES:
        unavailable_behavior = DEFAULT_UNAVAILABLE_BEHAVIOR

    if FIELD_NO_MOTION_TIMEOUT_MINUTES in user_input:
        no_motion_timeout_minutes = _bounded_int(
            user_input[FIELD_NO_MOTION_TIMEOUT_MINUTES],
            int(DEFAULT_NO_MOTION_TIMEOUT / 60),
            MIN_TIMEOUT_MINUTES,
            MAX_TIMEOUT_MINUTES,
        )
    else:
        no_motion_timeout_minutes = _bounded_minutes_from_seconds(
            user_input.get(CONF_NO_MOTION_TIMEOUT, DEFAULT_NO_MOTION_TIMEOUT),
            DEFAULT_NO_MOTION_TIMEOUT,
        )

    if FIELD_OPEN_NO_MOTION_TIMEOUT_MINUTES in user_input:
        open_no_motion_timeout_minutes = _bounded_int(
            user_input[FIELD_OPEN_NO_MOTION_TIMEOUT_MINUTES],
            int(DEFAULT_OPEN_NO_MOTION_TIMEOUT / 60),
            MIN_TIMEOUT_MINUTES,
            MAX_TIMEOUT_MINUTES,
        )
    else:
        open_no_motion_timeout_minutes = _bounded_minutes_from_seconds(
            user_input.get(
                CONF_OPEN_NO_MOTION_TIMEOUT,
                DEFAULT_OPEN_NO_MOTION_TIMEOUT,
            ),
            DEFAULT_OPEN_NO_MOTION_TIMEOUT,
        )

    return {
        "name": str(user_input.get("name", DEFAULT_NAME)).strip() or DEFAULT_NAME,
        CONF_CONTROL_ENTITIES: _entity_ids(
            user_input.get(CONF_CONTROL_ENTITIES),
            set(CONTROL_ENTITY_DOMAINS),
        ),
        CONF_MOTION_ENTITIES: _entity_ids(
            user_input.get(CONF_MOTION_ENTITIES),
            {"binary_sensor"},
        ),
        CONF_DEFAULT_COOLDOWN: _bounded_int(
            user_input.get(CONF_DEFAULT_COOLDOWN, DEFAULT_COOLDOWN),
            DEFAULT_COOLDOWN,
            MIN_COOLDOWN,
            MAX_COOLDOWN,
        ),
        CONF_FRESH_WINDOW: _bounded_int(
            user_input.get(CONF_FRESH_WINDOW, DEFAULT_FRESH_WINDOW),
            DEFAULT_FRESH_WINDOW,
            MIN_CONTROL_GRACE_TIME,
            MAX_CONTROL_GRACE_TIME,
        ),
        CONF_CONTROL_CLOSED_MODE: control_closed_mode,
        CONF_UNAVAILABLE_BEHAVIOR: unavailable_behavior,
        CONF_NO_MOTION_TIMEOUT: no_motion_timeout_minutes * 60,
        CONF_OPEN_NO_MOTION_TIMEOUT: open_no_motion_timeout_minutes * 60,
        CONF_SHOW_DEBUG_ATTRIBUTES: (
            user_input.get(
                CONF_SHOW_DEBUG_ATTRIBUTES,
                DEFAULT_SHOW_DEBUG_ATTRIBUTES,
            )
            is True
        ),
    }


def _base_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the main configuration schema."""
    defaults = defaults or {}
    no_motion_timeout_minutes = _bounded_minutes_from_seconds(
        defaults.get(CONF_NO_MOTION_TIMEOUT, DEFAULT_NO_MOTION_TIMEOUT),
        DEFAULT_NO_MOTION_TIMEOUT,
    )
    open_no_motion_timeout_minutes = _bounded_minutes_from_seconds(
        defaults.get(
            CONF_OPEN_NO_MOTION_TIMEOUT,
            DEFAULT_OPEN_NO_MOTION_TIMEOUT,
        ),
        DEFAULT_OPEN_NO_MOTION_TIMEOUT,
    )
    return vol.Schema(
        {
            vol.Required("name", default=defaults.get("name", DEFAULT_NAME)): str,
            vol.Required(
                CONF_CONTROL_ENTITIES,
                default=defaults.get(CONF_CONTROL_ENTITIES, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=list(CONTROL_ENTITY_DOMAINS),
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_MOTION_ENTITIES,
                default=defaults.get(CONF_MOTION_ENTITIES, []),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
            ),
            vol.Required(
                CONF_DEFAULT_COOLDOWN,
                default=defaults.get(CONF_DEFAULT_COOLDOWN, DEFAULT_COOLDOWN),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_COOLDOWN,
                    max=MAX_COOLDOWN,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_FRESH_WINDOW,
                default=defaults.get(CONF_FRESH_WINDOW, DEFAULT_FRESH_WINDOW),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_CONTROL_GRACE_TIME,
                    max=MAX_CONTROL_GRACE_TIME,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
            vol.Required(
                CONF_CONTROL_CLOSED_MODE,
                default=defaults.get(
                    CONF_CONTROL_CLOSED_MODE,
                    DEFAULT_CONTROL_CLOSED_MODE,
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=CLOSED_MODE_CHOICES,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_CONTROL_CLOSED_MODE,
                )
            ),
            vol.Required(
                CONF_UNAVAILABLE_BEHAVIOR,
                default=defaults.get(
                    CONF_UNAVAILABLE_BEHAVIOR,
                    DEFAULT_UNAVAILABLE_BEHAVIOR,
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=UNAVAILABLE_BEHAVIOR_CHOICES,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_UNAVAILABLE_BEHAVIOR,
                )
            ),
            vol.Required(
                FIELD_NO_MOTION_TIMEOUT_MINUTES,
                default=no_motion_timeout_minutes,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_TIMEOUT_MINUTES,
                    max=MAX_TIMEOUT_MINUTES,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                FIELD_OPEN_NO_MOTION_TIMEOUT_MINUTES,
                default=open_no_motion_timeout_minutes,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_TIMEOUT_MINUTES,
                    max=MAX_TIMEOUT_MINUTES,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="min",
                )
            ),
            vol.Required(
                CONF_SHOW_DEBUG_ATTRIBUTES,
                default=(
                    defaults.get(
                        CONF_SHOW_DEBUG_ATTRIBUTES,
                        DEFAULT_SHOW_DEBUG_ATTRIBUTES,
                    )
                    is True
                ),
            ): selector.BooleanSelector(),
        }
    )


def _control_active_state_schema(default_active_state: str) -> vol.Schema:
    """Return the one-control active state schema."""
    if default_active_state not in OPEN_STATE_CHOICES:
        default_active_state = STATE_ON

    return vol.Schema(
        {
            vol.Required(
                FIELD_CONTROL_ACTIVE_STATE,
                default=default_active_state,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=OPEN_STATE_CHOICES,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=FIELD_CONTROL_ACTIVE_STATE,
                )
            )
        }
    )


def _cooldown_schema(default_cooldown: int) -> vol.Schema:
    """Return the one-motion cooldown schema."""
    return vol.Schema(
        {
            vol.Required(
                FIELD_MOTION_COOLDOWN,
                default=int(default_cooldown),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_COOLDOWN,
                    max=MAX_COOLDOWN,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            )
        }
    )


def _entity_display_name(hass: HomeAssistant, entity_id: str) -> str:
    """Return a friendly entity display name."""
    state = hass.states.get(entity_id)
    if state is None:
        return entity_id

    friendly_name = state.attributes.get("friendly_name")
    return str(friendly_name) if friendly_name else entity_id


def _entity_current_state(hass: HomeAssistant, entity_id: str) -> str:
    """Return the current raw entity state for user-facing help text."""
    state = hass.states.get(entity_id)
    return "not available" if state is None else str(state.state)


def _control_placeholders(
    hass: HomeAssistant,
    control_entities: list[str],
    control_index: int,
) -> dict[str, str]:
    """Return description placeholders for one control setup step."""
    entity_id = control_entities[control_index]
    display_name = _entity_display_name(hass, entity_id)
    return {
        "control_number": str(control_index + 1),
        "control_total": str(len(control_entities)),
        "control_name": display_name,
        "control_entity_id": entity_id,
        "current_state": _entity_current_state(hass, entity_id),
    }


def _motion_placeholders(
    hass: HomeAssistant,
    motion_entities: list[str],
    motion_index: int,
) -> dict[str, str]:
    """Return description placeholders for one motion setup step."""
    entity_id = motion_entities[motion_index]
    return {
        "motion_number": str(motion_index + 1),
        "motion_total": str(len(motion_entities)),
        "motion_name": _entity_display_name(hass, entity_id),
        "motion_entity_id": entity_id,
        "current_state": _entity_current_state(hass, entity_id),
    }


class AdvancedPresenceDetectionConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Advanced Presence Detection."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._pending_base: dict[str, Any] = {}
        self._control_index = 0
        self._motion_index = 0

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return AdvancedPresenceDetectionOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            base = _normalise_base_input(user_input)

            if not base[CONF_CONTROL_ENTITIES]:
                errors[CONF_CONTROL_ENTITIES] = "no_controls"
            if not base[CONF_MOTION_ENTITIES]:
                errors[CONF_MOTION_ENTITIES] = "no_motions"

            if not errors:
                self._pending_base = base
                self._pending_base[CONF_CONTROL_ACTIVE_STATES] = {
                    entity_id: STATE_ON for entity_id in base[CONF_CONTROL_ENTITIES]
                }
                self._control_index = 0
                return await self.async_step_control_state()

        return self.async_show_form(
            step_id="user",
            data_schema=_base_schema(),
            errors=errors,
        )

    async def async_step_control_state(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask which state means active for each control entity."""
        control_entities: list[str] = self._pending_base[CONF_CONTROL_ENTITIES]
        entity_id = control_entities[self._control_index]

        if user_input is not None:
            self._pending_base[CONF_CONTROL_ACTIVE_STATES][entity_id] = str(
                user_input[FIELD_CONTROL_ACTIVE_STATE]
            )
            self._control_index += 1

            if self._control_index >= len(control_entities):
                default_cooldown = self._pending_base[CONF_DEFAULT_COOLDOWN]
                self._pending_base[CONF_MOTION_COOLDOWNS] = {
                    motion_entity_id: default_cooldown
                    for motion_entity_id in self._pending_base[CONF_MOTION_ENTITIES]
                }
                self._motion_index = 0
                return await self.async_step_motion_cooldown()

            entity_id = control_entities[self._control_index]

        default_active_state = self._pending_base[CONF_CONTROL_ACTIVE_STATES].get(
            entity_id, STATE_ON
        )
        return self.async_show_form(
            step_id="control_state",
            data_schema=_control_active_state_schema(default_active_state),
            description_placeholders=_control_placeholders(
                self.hass, control_entities, self._control_index
            ),
        )

    async def async_step_motion_cooldown(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for one cooldown per motion sensor."""
        motion_entities: list[str] = self._pending_base[CONF_MOTION_ENTITIES]
        entity_id = motion_entities[self._motion_index]

        if user_input is not None:
            self._pending_base[CONF_MOTION_COOLDOWNS][entity_id] = _bounded_int(
                user_input[FIELD_MOTION_COOLDOWN],
                self._pending_base[CONF_DEFAULT_COOLDOWN],
                MIN_COOLDOWN,
                MAX_COOLDOWN,
            )
            self._motion_index += 1

            if self._motion_index >= len(motion_entities):
                data = dict(self._pending_base)
                return self.async_create_entry(title=data["name"], data=data)

            entity_id = motion_entities[self._motion_index]

        default_cooldown = self._pending_base[CONF_MOTION_COOLDOWNS].get(
            entity_id, self._pending_base[CONF_DEFAULT_COOLDOWN]
        )
        return self.async_show_form(
            step_id="motion_cooldown",
            data_schema=_cooldown_schema(default_cooldown),
            description_placeholders=_motion_placeholders(
                self.hass, motion_entities, self._motion_index
            ),
        )


class AdvancedPresenceDetectionOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle options for Advanced Presence Detection."""

    def __init__(self) -> None:
        """Initialize options flow."""
        self._pending_base: dict[str, Any] = {}
        self._control_index = 0
        self._motion_index = 0

    def _current_config(self) -> dict[str, Any]:
        """Return current config with options overriding data."""
        return {**self.config_entry.data, **self.config_entry.options}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current = self._current_config()

        if user_input is not None:
            base = _normalise_base_input(user_input)

            if not base[CONF_CONTROL_ENTITIES]:
                errors[CONF_CONTROL_ENTITIES] = "no_controls"
            if not base[CONF_MOTION_ENTITIES]:
                errors[CONF_MOTION_ENTITIES] = "no_motions"

            if not errors:
                existing_active_states: dict[str, str] = current.get(
                    CONF_CONTROL_ACTIVE_STATES, {}
                )
                self._pending_base = base
                self._pending_base[CONF_CONTROL_ACTIVE_STATES] = {
                    entity_id: str(existing_active_states.get(entity_id, STATE_ON))
                    for entity_id in base[CONF_CONTROL_ENTITIES]
                }
                self._control_index = 0
                return await self.async_step_control_state()

        return self.async_show_form(
            step_id="init",
            data_schema=_base_schema(current),
            errors=errors,
        )

    async def async_step_control_state(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage which state means active for each control entity."""
        control_entities: list[str] = self._pending_base[CONF_CONTROL_ENTITIES]
        entity_id = control_entities[self._control_index]

        if user_input is not None:
            self._pending_base[CONF_CONTROL_ACTIVE_STATES][entity_id] = str(
                user_input[FIELD_CONTROL_ACTIVE_STATE]
            )
            self._control_index += 1

            if self._control_index >= len(control_entities):
                current = self._current_config()
                existing_cooldowns: dict[str, int] = current.get(
                    CONF_MOTION_COOLDOWNS, {}
                )
                if not isinstance(existing_cooldowns, dict):
                    existing_cooldowns = {}
                default_cooldown = self._pending_base[CONF_DEFAULT_COOLDOWN]
                self._pending_base[CONF_MOTION_COOLDOWNS] = {
                    motion_entity_id: _bounded_int(
                        existing_cooldowns.get(motion_entity_id, default_cooldown),
                        default_cooldown,
                        MIN_COOLDOWN,
                        MAX_COOLDOWN,
                    )
                    for motion_entity_id in self._pending_base[CONF_MOTION_ENTITIES]
                }
                self._motion_index = 0
                return await self.async_step_motion_cooldown()

            entity_id = control_entities[self._control_index]

        default_active_state = self._pending_base[CONF_CONTROL_ACTIVE_STATES].get(
            entity_id, STATE_ON
        )
        return self.async_show_form(
            step_id="control_state",
            data_schema=_control_active_state_schema(default_active_state),
            description_placeholders=_control_placeholders(
                self.hass, control_entities, self._control_index
            ),
        )

    async def async_step_motion_cooldown(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage per sensor cooldown options."""
        motion_entities: list[str] = self._pending_base[CONF_MOTION_ENTITIES]
        entity_id = motion_entities[self._motion_index]

        if user_input is not None:
            self._pending_base[CONF_MOTION_COOLDOWNS][entity_id] = _bounded_int(
                user_input[FIELD_MOTION_COOLDOWN],
                self._pending_base[CONF_DEFAULT_COOLDOWN],
                MIN_COOLDOWN,
                MAX_COOLDOWN,
            )
            self._motion_index += 1

            if self._motion_index >= len(motion_entities):
                data = dict(self._pending_base)
                return self.async_create_entry(title="", data=data)

            entity_id = motion_entities[self._motion_index]

        default_cooldown = self._pending_base[CONF_MOTION_COOLDOWNS].get(
            entity_id, self._pending_base[CONF_DEFAULT_COOLDOWN]
        )
        return self.async_show_form(
            step_id="motion_cooldown",
            data_schema=_cooldown_schema(default_cooldown),
            description_placeholders=_motion_placeholders(
                self.hass, motion_entities, self._motion_index
            ),
        )
