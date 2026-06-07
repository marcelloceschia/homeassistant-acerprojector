"""Creates Sensor entities for the Acer Projector Home Assistant integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
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
    """Set up the Acer Projector sensors."""
    coordinator: AcerProjectorCoordinator = config_entry.runtime_data

    entity_descriptions = []
    if coordinator.supports_feature("lamp_hours"):
        entity_descriptions.append(
            SensorEntityDescription(
                key="lamp_hours",
                translation_key="lamp_hours",
                entity_category=EntityCategory.DIAGNOSTIC,
                device_class=SensorDeviceClass.DURATION,
                native_unit_of_measurement=UnitOfTime.HOURS,
                state_class=SensorStateClass.TOTAL_INCREASING,
                suggested_display_precision=0,
            )
        )

    entities = [
        AcerProjectorSensor(coordinator, description, config_entry.entry_id)
        for description in entity_descriptions
    ]

    async_add_entities(entities)


class AcerProjectorSensor(CoordinatorEntity, SensorEntity):
    """Acer Projector Sensor."""

    _attr_has_entity_name = True
    _attr_available = False
    _attr_native_value = None

    def __init__(
        self,
        coordinator: AcerProjectorCoordinator,
        entity_description: SensorEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_description.key)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"
        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Called when sensor is added to Home Assistant."""
        await super().async_added_to_hass()

        if self.coordinator.data and (
            native_value := self.coordinator.data.get(self.entity_description.key)
        ):
            try:
                self._attr_native_value = int(native_value)
                self._attr_available = True
            except (ValueError, TypeError):
                self._attr_available = False
        else:
            _LOGGER.debug("%s is not available", self.entity_description.key)
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
        if self.entity_description.key in self.coordinator.data:
            try:
                value = self.coordinator.data.get(self.entity_description.key)
                if value is not None:
                    self._attr_native_value = int(value)
                    self._attr_available = True
                else:
                    self._attr_available = False
            except (ValueError, TypeError):
                self._attr_available = False
        elif self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()
