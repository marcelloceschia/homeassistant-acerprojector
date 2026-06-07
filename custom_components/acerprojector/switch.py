"""Creates Switch entities for the Acer Projector Home Assistant integration."""

import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AcerProjectorCoordinator
from .const import POWERSTATUS_ON, POWERSTATUS_POWERINGON

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Acer Projector switch."""
    coordinator: AcerProjectorCoordinator = config_entry.runtime_data

    entity_descriptions = []
    if coordinator.supports_command("mute"):
        entity_descriptions.append(
            SwitchEntityDescription(key="mute", translation_key="mute")
        )
    if coordinator.supports_command("freeze"):
        entity_descriptions.append(
            SwitchEntityDescription(key="freeze", translation_key="freeze")
        )
    if coordinator.supports_command("hide"):
        entity_descriptions.append(
            SwitchEntityDescription(key="hide", translation_key="hide")
        )

    entities = [
        AcerProjectorSwitch(coordinator, description, config_entry.entry_id)
        for description in entity_descriptions
    ]

    async_add_entities(entities)


class AcerProjectorSwitch(CoordinatorEntity, SwitchEntity):
    """Acer Projector Switch."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_available = False
    _attr_is_on = None

    def __init__(
        self,
        coordinator: AcerProjectorCoordinator,
        entity_description: SwitchEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entity_description.key)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Called when switch is added to Home Assistant."""
        await super().async_added_to_hass()

        if self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Sending %s", self.entity_description.key)
        if await self.coordinator.async_send_ir_command(self.entity_description.key):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Sending %s", self.entity_description.key)
        if await self.coordinator.async_send_ir_command(self.entity_description.key):
            self._attr_is_on = False
            self.async_write_ha_state()
