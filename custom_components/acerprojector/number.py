"""Creates Number entities for the Acer Projector Home Assistant integration."""

import logging

from homeassistant.components.number import NumberEntity, NumberEntityDescription
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
    """Set up the Acer Projector number."""
    coordinator: AcerProjectorCoordinator = config_entry.runtime_data

    if not coordinator.supports_feature("volume"):
        return

    entity_description = NumberEntityDescription(
        key="volume",
        translation_key="volume",
        native_min_value=0,
        native_max_value=20,
        native_step=1,
    )

    async_add_entities(
        [AcerProjectorNumber(coordinator, entity_description, config_entry.entry_id)]
    )


class AcerProjectorNumber(CoordinatorEntity, NumberEntity):
    """Acer Projector Number."""

    _attr_has_entity_name = True
    _attr_available = False
    _attr_native_value = None

    def __init__(
        self,
        coordinator: AcerProjectorCoordinator,
        entity_description: NumberEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, entity_description.key)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Called when number is added to Home Assistant."""
        await super().async_added_to_hass()

        if self.coordinator.volume is not None:
            self._attr_native_value = float(self.coordinator.volume)
            self._attr_available = True
        elif self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_available = True
        else:
            _LOGGER.debug("%s is not available", self.entity_description.key)

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
        if self.coordinator.volume is not None:
            self._attr_native_value = float(self.coordinator.volume)
            self._attr_available = True
        elif self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set volume level."""
        if self.coordinator.power_status != POWERSTATUS_ON:
            self._attr_available = False
            self.async_write_ha_state()
            return

        if await self.coordinator.async_set_volume_level(int(value)):
            self._attr_native_value = float(self.coordinator.volume)
            self.async_write_ha_state()
