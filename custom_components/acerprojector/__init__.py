"""The Acer Projector integration."""

import logging
import os
import shutil
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BAUD_RATE,
    CONF_CONNECTION_TYPE,
    CONF_DEFAULT_INTERVAL,
    CONF_DEFAULT_VOLUME,
    CONF_INTERVAL,
    CONF_MODEL,
    CONF_SERIAL_PORT,
    CONF_TYPE_SERIAL,
    CONF_TYPE_TCP,
    CONF_VOLUME,
    DOMAIN,
    POWERSTATUS_ON,
)
from .projector import AcerProjector, AcerProjectorSerial, AcerProjectorTcp

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONF_SERVICE_COMMAND = "command"

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_SERVICE_COMMAND): cv.string,
    }
)


class AcerProjectorCoordinator(DataUpdateCoordinator):
    """Acer Projector Data Update Coordinator."""

    unique_id: str | None = None
    model: str | None = None
    device_info: DeviceInfo | None = None
    config_entry: ConfigEntry | None = None

    def __init__(
        self,
        hass: HomeAssistant | None,
        projector: AcerProjector,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize Acer Projector Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=__name__,
            update_interval=None,
        )

        self.config_entry = config_entry
        self.projector = projector
        self.projector.add_listener(self._listener)

        self.unique_id = self.projector.unique_id
        self.model = self.projector.model

        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=f"Acer {self.model or 'Projector'}",
            model=self.model,
            manufacturer="Acer",
        )

    @property
    def power_status(self) -> int:
        return self.projector.power_status

    @property
    def video_source(self) -> str | None:
        return self.projector.video_source

    @property
    def video_sources(self) -> dict[str, str]:
        return self.projector.video_sources

    @property
    def video_source_names(self) -> dict[str, str]:
        return self.projector.video_source_names

    @property
    def lamp_hours(self) -> int | None:
        return self.projector.lamp_hours

    @property
    def volume(self) -> int | None:
        return self.projector.volume

    @property
    def eco_mode(self) -> bool | None:
        return self.projector.eco_mode

    @callback
    def _listener(self, command: str, data: Any) -> None:
        self.async_set_updated_data({command: data})

    async def async_disconnect(self) -> None:
        await self.projector.disconnect()
        _LOGGER.debug("Disconnected from Acer projector on %s", self.projector.connection)

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Any:
        # Wrap HA's no-arg callback to match projector's (command, data) signature
        def _wrapper(command: str, data: Any) -> None:
            update_callback()
        self.projector.add_listener(_wrapper)
        return super().async_add_listener(update_callback, context)

    def supports_feature(self, feature: str) -> bool:
        return self.projector.supports_feature(feature)

    def supports_command(self, command: str) -> bool:
        return self.projector.supports_command(command)

    async def async_send_raw_command(self, command: str) -> str:
        return await self.projector.send_raw_command(command)

    async def async_turn_on(self) -> bool:
        return await self.projector.turn_on()

    async def async_turn_off(self) -> bool:
        return await self.projector.turn_off()

    async def async_select_video_source(self, source: str) -> bool:
        return await self.projector.select_video_source(source)

    async def async_set_volume_level(self, level: int) -> bool:
        if await self.projector.set_volume_level(level):
            # Persist the new volume in config entry options
            if self.hass and self.config_entry:
                new_options = dict(self.config_entry.options)
                new_options[CONF_VOLUME] = self.projector.volume
                self.hass.config_entries.async_update_entry(
                    self.config_entry, options=new_options
                )
            return True
        return False

    async def async_set_eco_mode(self, enabled: bool) -> bool:
        return await self.projector.set_eco_mode(enabled)

    async def async_send_ir_command(self, command: str) -> bool:
        return await self.projector.send_ir_command(command)

    async def _async_update_data(self) -> dict[str, Any]:
        await self.projector.update()
        return {
            "power": self.projector.power_status,
            "source": self.projector.video_source,
            "lamp_hours": self.projector.lamp_hours,
            "eco_mode": self.projector.eco_mode,
        }


async def _async_setup_icons(hass: HomeAssistant) -> None:
    """Copy icon assets to www folder so they are served by HA."""
    try:
        integration_dir = os.path.dirname(os.path.abspath(__file__))
        source_dir = os.path.join(integration_dir, "assets")
        target_dir = os.path.join(hass.config.config_dir, "www", "acerprojector")

        if not os.path.isdir(source_dir):
            _LOGGER.debug("No assets dir found at %s, skipping icon setup", source_dir)
            return

        os.makedirs(target_dir, exist_ok=True)

        copied = 0
        skipped = 0
        for fname in os.listdir(source_dir):
            if fname.endswith(".svg"):
                src = os.path.join(source_dir, fname)
                dst = os.path.join(target_dir, fname)
                if os.path.exists(dst):
                    skipped += 1
                    continue
                shutil.copy2(src, dst)
                copied += 1

        if copied:
            _LOGGER.info("Copied %d new icon(s) to %s", copied, target_dir)
        if skipped:
            _LOGGER.debug("Skipped %d existing icon(s) in %s", skipped, target_dir)
    except Exception as exc:
        _LOGGER.warning("Failed to copy Acer projector icons: %s", exc)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Acer Projector from a config entry."""
    # Ensure icons are available in www for the media player card
    await _async_setup_icons(hass)

    projector: AcerProjector | None = None

    model = entry.data.get(CONF_MODEL)
    conf_type = entry.data.get(CONF_CONNECTION_TYPE, CONF_TYPE_TCP)
    interval = entry.options.get(CONF_INTERVAL, CONF_DEFAULT_INTERVAL)

    if conf_type == CONF_TYPE_TCP:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        projector = AcerProjectorTcp(host, port, model)
    else:
        serial_port = entry.data[CONF_SERIAL_PORT]
        baud_rate = entry.data[CONF_BAUD_RATE]
        projector = AcerProjectorSerial(serial_port, baud_rate, model)

    @callback
    def _async_migrate_entity_entry(registry_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if registry_entry.unique_id.startswith(f"{projector.unique_id}-"):
            new_unique_id = registry_entry.unique_id.replace(
                f"{projector.unique_id}-", f"{registry_entry.config_entry_id}-"
            )
            _LOGGER.debug("Migrating entity unique id")
            return {"new_unique_id": new_unique_id}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrate_entity_entry)

    if not await projector.connect():
        raise ConfigEntryNotReady(f"Unable to connect to device {projector.unique_id}")

    _LOGGER.info("Device %s is available", projector.unique_id)

    # Restore last known volume from options, default to 3
    projector.volume = entry.options.get(CONF_VOLUME, CONF_DEFAULT_VOLUME)

    coordinator = AcerProjectorCoordinator(hass, projector, config_entry=entry)

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    projector.start_polling(interval)

    async def async_handle_send(call: ServiceCall) -> dict[str, str]:
        command: str = call.data.get(CONF_SERVICE_COMMAND)
        response = await coordinator.async_send_raw_command(command)
        return {"response": response}

    hass.services.async_register(
        DOMAIN,
        "send_raw",
        async_handle_send,
        schema=SERVICE_SEND_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: AcerProjectorCoordinator = entry.runtime_data
    await coordinator.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    hass.config_entries.async_schedule_reload(entry.entry_id)
