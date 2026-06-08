"""Creates Media Player entities for the Acer Projector Home Assistant integration."""

import logging

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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
    """Set up the Acer Projector media player."""
    coordinator: AcerProjectorCoordinator = config_entry.runtime_data
    async_add_entities([AcerProjectorMediaPlayer(coordinator, config_entry.entry_id)])


class AcerProjectorMediaPlayer(CoordinatorEntity, MediaPlayerEntity):
    """Acer Projector Media Player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_translation_key = "projector"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    _attr_available = False
    _attr_state = None
    _attr_source_list: list[str] | None = None
    _attr_source = None
    _attr_is_volume_muted = None
    _attr_volume_level = None

    _SOURCE_IMAGES = {
        "hdmi1": "/local/acerprojector/hdmi1.svg",
        "hdmi2": "/local/acerprojector/hdmi2.svg",
        "hdmi3": "/local/acerprojector/hdmi3.svg",
        "vga": "/local/acerprojector/vga.svg",
        "dvi": "/local/acerprojector/monitor.svg",
        "displayport": "/local/acerprojector/monitor.svg",
        "wireless": "/local/acerprojector/wireless.svg",
        "usbdisplay": "/local/acerprojector/usb.svg",
        "lanwifi": "/local/acerprojector/lan.svg",
        "composite": "/local/acerprojector/av.svg",
        "svideo": "/local/acerprojector/av.svg",
        "component": "/local/acerprojector/av.svg",
        "media": "/local/acerprojector/media.svg",
        "hdbaset": "/local/acerprojector/ethernet.svg",
    }

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL for the current source."""
        if self.coordinator.video_source:
            return self._SOURCE_IMAGES.get(self.coordinator.video_source)
        return "/local/acerprojector/projector.svg"

    def __init__(
        self, coordinator: AcerProjectorCoordinator, config_entry_id: str
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-projector"

    async def async_added_to_hass(self) -> None:
        """Called when media player is added to Home Assistant."""
        await super().async_added_to_hass()

        self._attr_source_list = list(self.coordinator.video_source_names.keys())

        if self.coordinator.power_status == -1:
            self._attr_available = False
        elif self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_state = MediaPlayerState.ON
            self._attr_source = self.coordinator.video_source
            if self.coordinator.volume is not None:
                self._attr_volume_level = self.coordinator.volume / 20.0
            self._attr_available = True
        elif self.coordinator.power_status == POWERSTATUS_POWERINGOFF:
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = False
        elif self.coordinator.power_status == POWERSTATUS_OFF:
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = True

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
        if self.coordinator.power_status == -1:
            self._attr_available = False
        elif self.coordinator.power_status in [POWERSTATUS_POWERINGON, POWERSTATUS_ON]:
            self._attr_state = MediaPlayerState.ON
            self._attr_available = True
        elif self.coordinator.power_status == POWERSTATUS_POWERINGOFF:
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = False
        elif self.coordinator.power_status == POWERSTATUS_OFF:
            self._attr_state = MediaPlayerState.OFF
            self._attr_available = True

        if "source" in self.coordinator.data:
            self._attr_source = self.coordinator.data.get("source")

        if self.coordinator.volume is not None:
            self._attr_volume_level = self.coordinator.volume / 20.0

        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn projector on."""
        if await self.coordinator.async_turn_on():
            self._attr_state = MediaPlayerState.ON
            self._attr_available = True
            self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn projector off."""
        if await self.coordinator.async_turn_off():
            self._attr_state = MediaPlayerState.OFF
            self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Set the input video source."""
        if await self.coordinator.async_select_video_source(source):
            self._attr_source = source
            self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        if self.coordinator.power_status != POWERSTATUS_ON:
            return
        level = int(volume * 20.0)
        if await self.coordinator.async_set_volume_level(level):
            self._attr_volume_level = self.coordinator.volume / 20.0
            self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Volume up."""
        if self.coordinator.power_status != POWERSTATUS_ON:
            return
        current = self.coordinator.volume or 10
        if await self.coordinator.async_set_volume_level(min(20, current + 1)):
            self._attr_volume_level = self.coordinator.volume / 20.0
            self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Volume down."""
        if self.coordinator.power_status != POWERSTATUS_ON:
            return
        current = self.coordinator.volume or 10
        if await self.coordinator.async_set_volume_level(max(0, current - 1)):
            self._attr_volume_level = self.coordinator.volume / 20.0
            self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute/unmute volume."""
        if self.coordinator.power_status != POWERSTATUS_ON:
            return
        if await self.coordinator.async_send_ir_command("mute"):
            self._attr_is_volume_muted = mute
            self.async_write_ha_state()
