"""Creates Switch entities for the Acer Projector Home Assistant integration."""

import logging

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AcerProjectorCoordinator
from .const import POWERSTATUS_OFF, POWERSTATUS_ON, POWERSTATUS_POWERINGOFF, POWERSTATUS_POWERINGON

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Acer Projector switch."""
    coordinator: AcerProjectorCoordinator = config_entry.runtime_data

    entity_descriptions = []
    # Always add power switch
    entity_descriptions.append(
        SwitchEntityDescription(
            key="power",
            translation_key="power",
            device_class=SwitchDeviceClass.SWITCH,
        )
    )
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
    if coordinator.supports_feature("eco_mode"):
        entity_descriptions.append(
            SwitchEntityDescription(
                key="eco_mode",
                translation_key="eco_mode",
                entity_category=EntityCategory.CONFIG,
            )
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

    @property
    def _is_power_switch(self) -> bool:
        return self.entity_description.key == "power"

    async def async_added_to_hass(self) -> None:
        """Called when switch is added to Home Assistant."""
        await super().async_added_to_hass()

        key = self.entity_description.key
        if self._is_power_switch:
            # Power switch availability follows coordinator connection
            if self.coordinator.power_status == -1:
                self._attr_available = False
            else:
                self._attr_available = True
                self._attr_is_on = self.coordinator.power_status == POWERSTATUS_ON
        elif self.coordinator.data and (new_state := self.coordinator.data.get(key)) is not None:
            self._attr_is_on = bool(new_state)
            self._attr_available = True
        elif self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_available = True
        else:
            _LOGGER.debug("%s is not available", key)
            self._attr_available = False

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self._is_power_switch:
            return self.coordinator.power_status != -1
        if not self._attr_available:
            return self._attr_available
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        key = self.entity_description.key
        if self._is_power_switch:
            if self.coordinator.power_status == -1:
                self._attr_available = False
            else:
                self._attr_available = True
                self._attr_is_on = self.coordinator.power_status == POWERSTATUS_ON
        elif key in self.coordinator.data:
            self._attr_is_on = bool(self.coordinator.data.get(key))
            self._attr_available = True
        elif self.coordinator.power_status in [
            POWERSTATUS_POWERINGON,
            POWERSTATUS_ON,
        ]:
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        _LOGGER.debug("Turning on %s", self.name)
        if self._is_power_switch:
            success = await self.coordinator.async_turn_on()
        elif self.entity_description.key == "eco_mode":
            success = await self.coordinator.async_set_eco_mode(True)
        else:
            success = await self.coordinator.async_send_ir_command(self.entity_description.key)
        if success:
            self._attr_is_on = True
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch on %s", self.name)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        _LOGGER.debug("Turning off %s", self.name)
        if self._is_power_switch:
            success = await self.coordinator.async_turn_off()
        elif self.entity_description.key == "eco_mode":
            success = await self.coordinator.async_set_eco_mode(False)
        else:
            success = await self.coordinator.async_send_ir_command(self.entity_description.key)
        if success:
            self._attr_is_on = False
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to switch off %s", self.name)
