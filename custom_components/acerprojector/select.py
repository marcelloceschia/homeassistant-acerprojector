"""Creates Select entities for the Acer Projector Home Assistant integration."""

import logging

from homeassistant.components.select import SelectEntity, SelectEntityDescription
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
    """Set up the Acer Projector select."""
    coordinator: AcerProjectorCoordinator = config_entry.runtime_data

    if not coordinator.supports_feature("video_source"):
        return

    visible_sources = config_entry.options.get(
        "visible_video_sources", list(coordinator.video_source_names.keys())
    )
    available_options = [
        key
        for key in coordinator.video_source_names.keys()
        if key in visible_sources
    ]

    entity_description = SelectEntityDescription(
        key="video_source",
        translation_key="video_source",
        options=available_options,
    )

    async_add_entities(
        [AcerProjectorSelect(coordinator, entity_description, config_entry.entry_id)]
    )


class AcerProjectorSelect(CoordinatorEntity, SelectEntity):
    """Acer Projector Select."""

    _attr_has_entity_name = True
    _attr_available = False

    def __init__(
        self,
        coordinator: AcerProjectorCoordinator,
        entity_description: SelectEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, entity_description.key)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"
        self.entity_description = entity_description
        self._options_map = {
            key: name for key, name in coordinator.video_source_names.items()
        }

    async def async_added_to_hass(self) -> None:
        """Called when select is added to Home Assistant."""
        await super().async_added_to_hass()

        if self.coordinator.data and (
            current_option := self.coordinator.data.get("source")
        ):
            self._attr_current_option = current_option
            self._attr_available = True
        elif self.coordinator.power_status in [
            POWERSTATUS_POWERINGON,
            POWERSTATUS_ON,
        ]:
            self._attr_available = True
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

    @property
    def options(self) -> list[str]:
        return list(self._options_map.keys())

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if "source" in self.coordinator.data:
            self._attr_current_option = self.coordinator.data.get("source")
            self._attr_available = True
        elif self.coordinator.power_status in [
            POWERSTATUS_POWERINGON,
            POWERSTATUS_ON,
        ]:
            self._attr_available = True
        else:
            self._attr_available = False

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if await self.coordinator.async_select_video_source(option):
            self._attr_current_option = option
            self.async_write_ha_state()
        else:
            _LOGGER.error("Failed to set video source to %s", option)
