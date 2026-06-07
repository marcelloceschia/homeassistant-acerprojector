"""Acer projector protocol implementation supporting TCP and serial."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from abc import ABC
from typing import Any

_LOGGER = logging.getLogger(__name__)

WHITESPACE = " \t\n\r\x00"
END_OF_RESPONSE = b"\r\n"
RESPONSE_TIMEOUT = 5.0
CONNECTION_LOCK_TIMEOUT = 5.0


class AcerProjectorError(Exception):
    """Base error."""


class AcerConnectionError(AcerProjectorError):
    """Connection error."""


class AcerResponseTimeoutError(AcerProjectorError):
    """Timeout waiting for response."""


class AcerConnection(ABC):
    """Abstract connection."""

    async def open(self) -> bool:
        """Open connection."""
        raise NotImplementedError

    async def close(self) -> None:
        """Close connection."""
        raise NotImplementedError

    def is_open(self) -> bool:
        """Return True if connection is open."""
        raise NotImplementedError

    async def write(self, data: bytes) -> None:
        """Write raw bytes."""
        raise NotImplementedError

    async def read(self, size: int = 100) -> bytes:
        """Read up to size bytes."""
        raise NotImplementedError

    async def readuntil(self, separator: bytes = END_OF_RESPONSE) -> bytes:
        """Read until separator."""
        raise NotImplementedError

    async def reset(self) -> None:
        """Reset/clear input buffer."""
        raise NotImplementedError


class AcerTcpConnection(AcerConnection):
    """TCP connection for serial-to-ethernet bridges like USR-TCP232-410S."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    def __str__(self) -> str:
        return f"tcp://{self.host}:{self.port}"

    async def open(self) -> bool:
        if self.is_open():
            return True
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=5.0
            )
            _LOGGER.debug("Connected to %s", self)
            return True
        except (OSError, asyncio.TimeoutError) as exc:
            _LOGGER.error("Failed to connect to %s: %s", self, exc)
            return False

    async def close(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except OSError:
                pass
            self._writer = None
            self._reader = None

    def is_open(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def write(self, data: bytes) -> None:
        if not self._writer:
            raise AcerConnectionError("Not connected")
        self._writer.write(data)
        await self._writer.drain()

    async def read(self, size: int = 100) -> bytes:
        if not self._reader:
            raise AcerConnectionError("Not connected")
        try:
            return await asyncio.wait_for(self._reader.read(size), timeout=RESPONSE_TIMEOUT)
        except asyncio.TimeoutError:
            return b""

    async def readuntil(self, separator: bytes = END_OF_RESPONSE) -> bytes:
        if not self._reader:
            raise AcerConnectionError("Not connected")
        try:
            data = await asyncio.wait_for(
                self._reader.readuntil(separator), timeout=RESPONSE_TIMEOUT
            )
            return data
        except asyncio.LimitOverrunError:
            return await self._reader.read(1024)
        except asyncio.IncompleteReadError as exc:
            return exc.partial
        except asyncio.TimeoutError:
            return b""

    async def reset(self) -> None:
        if self._reader:
            try:
                empty_count = 0
                while empty_count < 2:
                    chunk = await asyncio.wait_for(self._reader.read(1024), timeout=0.15)
                    if chunk:
                        empty_count = 0
                    else:
                        empty_count += 1
            except asyncio.TimeoutError:
                pass


class AcerSerialConnection(AcerConnection):
    """Serial connection using pyserial."""

    def __init__(self, port: str, baud_rate: int) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self._serial: Any | None = None

    def __str__(self) -> str:
        return f"serial://{self.port}@{self.baud_rate}"

    async def open(self) -> bool:
        if self.is_open():
            return True
        try:
            import serial  # pylint: disable=import-outside-toplevel

            self._serial = serial.Serial(
                self.port,
                self.baud_rate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=RESPONSE_TIMEOUT,
                write_timeout=RESPONSE_TIMEOUT,
            )
            return True
        except Exception as exc:  # pylint: disable=broad-except
            _LOGGER.error("Failed to open serial port %s: %s", self.port, exc)
            return False

    async def close(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            except Exception:  # pylint: disable=broad-except
                pass
            self._serial = None

    def is_open(self) -> bool:
        return self._serial is not None and self._serial.is_open

    async def write(self, data: bytes) -> None:
        if not self._serial:
            raise AcerConnectionError("Not connected")
        self._serial.write(data)

    async def read(self, size: int = 100) -> bytes:
        if not self._serial:
            raise AcerConnectionError("Not connected")
        return self._serial.read(size)

    async def readuntil(self, separator: bytes = END_OF_RESPONSE) -> bytes:
        if not self._serial:
            raise AcerConnectionError("Not connected")
        return self._serial.read_until(separator)

    async def reset(self) -> None:
        if self._serial:
            self._serial.reset_input_buffer()


class AcerProjector:
    """Acer projector controller."""

    BAUD_RATES = [2400, 4800, 9600, 19200, 38400, 57600, 115200]

    def __init__(
        self,
        connection: AcerConnection,
        model_hint: str | None = None,
    ) -> None:
        self.connection = connection
        self.model = model_hint
        self.model_config: dict[str, Any] = {}
        self.unique_id: str = str(connection)

        self.power_status = -1  # unknown
        self.poweron_time = 25
        self.poweroff_time = 5
        self._power_timestamp: float | None = None

        self.video_source: str | None = None
        self.video_sources: dict[str, str] = {}
        self.video_source_names: dict[str, str] = {}
        self.video_source_values: dict[str, str] = {}
        self.commands: dict[str, str] = {}
        self.supported_features: list[str] = []

        self.lamp_hours: int | None = None
        self.lamp2_hours: int | None = None
        self.muted = False
        self.frozen = False
        self.hidden = False

        self._connection_lock = asyncio.Lock()
        self._listeners: list[Any] = []
        self._interval: float | None = None
        self._read_task: asyncio.Task | None = None
        self._init = True

    def add_listener(self, listener: Any) -> None:
        self._listeners.append(listener)

    def _notify_listeners(self, command: str, data: Any) -> None:
        for listener in self._listeners:
            try:
                listener(command, data)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Listener error")

    def _load_config(self, model: str) -> dict[str, Any]:
        safe_model = "".join(c if c.isalnum() or c in "._-" else "_" for c in model.lower())
        config_path = os.path.join(
            os.path.dirname(__file__), "configs", f"{safe_model}.json"
        )
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        # Search all configs for a matching model alias
        configs_dir = os.path.join(os.path.dirname(__file__), "configs")
        for filename in os.listdir(configs_dir):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(configs_dir, filename), encoding="utf-8") as f:
                    cfg = json.load(f)
                aliases = cfg.get("model_aliases", {})
                if model in aliases:
                    target = aliases[model]
                    target_path = os.path.join(configs_dir, f"{target}.json")
                    if os.path.exists(target_path):
                        with open(target_path, encoding="utf-8") as f:
                            return json.load(f)
            except Exception:  # pylint: disable=broad-except
                continue
        # Fallback to default
        default_path = os.path.join(os.path.dirname(__file__), "configs", "default.json")
        with open(default_path, encoding="utf-8") as f:
            return json.load(f)

    def _apply_config(self, config: dict[str, Any]) -> None:
        self.model_config = config
        self.video_sources = config.get("video_sources", {})
        self.video_source_names = config.get("video_source_names", self.video_sources)
        self.video_source_values = config.get("video_source_values", {})
        self.commands = config.get("commands", {})
        self.supported_features = config.get("supported_features", [])
        self.poweron_time = config.get("poweron_time", 25)
        self.poweroff_time = config.get("poweroff_time", 5)

    def supports_feature(self, feature: str) -> bool:
        return feature in self.supported_features

    def supports_command(self, command_name: str) -> bool:
        if command_name == "set_video_source":
            return bool(self.video_sources)
        return command_name in self.commands

    def _map_video_source(self, raw_value: str) -> str | None:
        """Map raw source response to configured source key."""
        raw_value = raw_value.strip().lower()
        if raw_value in self.video_source_values:
            return self.video_source_values[raw_value]
        if raw_value in self.video_sources:
            return raw_value
        for key, name in self.video_source_names.items():
            if raw_value == name.lower().replace(" ", ""):
                return key
        return raw_value if raw_value else None

    async def connect(self) -> bool:
        if not await self.connection.open():
            return False

        # Load minimal/default config first so query_model is available
        if not self.model_config:
            self._apply_config(self._load_config("default"))

        # Try to detect model if not set
        if not self.model:
            try:
                model = await self.send_command("query_model", raw_response=True)
                if model:
                    self.model = model.strip()
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.debug("Could not detect model: %s", exc)

        if not self.model:
            self.model = "default"

        self._apply_config(self._load_config(self.model))

        # Update power state
        await self.update_power()

        # Update additional state if powered on
        if self.power_status == 2:
            await self.update_video_source()
            await self.update_lamp_hours()

        self._init = False
        return True

    async def disconnect(self) -> bool:
        await self._cancel_read()
        await self.connection.close()
        return not self.connection.is_open()

    async def _cancel_read(self) -> bool:
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
            return True
        return False

    async def _send_raw(self, raw_command: str) -> None:
        if not raw_command.endswith("\r"):
            raw_command += "\r"
        _LOGGER.debug("Sending: %s", raw_command.strip())
        await self.connection.write(raw_command.encode("ascii"))

    async def _read_response(self) -> str:
        """Read a complete response from the projector.

        Acer responses via USR-TCP232-410S are typically:
        *000\rAnswer\r
        """
        response = b""
        last_data = asyncio.get_event_loop().time()
        status_seen = False
        while True:
            chunk = await self.connection.read(100)
            if chunk:
                response += chunk
                last_data = asyncio.get_event_loop().time()
                if b"*" in chunk:
                    status_seen = True
                if status_seen and b"\r" in chunk:
                    await asyncio.sleep(0.05)
                    try:
                        extra = await asyncio.wait_for(self.connection.read(100), timeout=0.1)
                        if extra:
                            response += extra
                    except asyncio.TimeoutError:
                        pass
                    break
            if (asyncio.get_event_loop().time() - last_data) > 1.0:
                break

        decoded = response.decode("ascii", errors="ignore").strip(WHITESPACE)
        _LOGGER.debug("Raw response: %r", decoded)
        return decoded

    async def _read_response_formatted(self) -> str:
        """Read and format Acer response.

        Acer responses via USR-TCP232-410S come as:
        *000\rLamp 0\r
        or:
        *001\r

        Some projectors also wrap answers in *** markers.
        """
        raw = await self._read_response()
        cleaned = re.sub(r"^\*\d{3}\r\n?", "", raw)
        cleaned = re.sub(r"\*+", "", cleaned)
        cleaned = cleaned.strip(WHITESPACE)
        lines = [line.strip(WHITESPACE) for line in cleaned.splitlines() if line.strip(WHITESPACE)]
        if lines:
            return lines[-1]
        return ""

    async def send_raw_command(self, raw_command: str) -> str:
        """Send a raw command and return raw response."""
        async with self._connection_lock:
            try:
                await self.connection.reset()
                await self._send_raw(raw_command)
                return await self._read_response_formatted()
            except AcerConnectionError:
                _LOGGER.exception("Connection error sending %s", raw_command)
                return ""

    async def send_command(
        self,
        command_name: str,
        action: str | None = None,
        raw_response: bool = False,
    ) -> str | None:
        cmd = self.commands.get(command_name)
        if not cmd:
            if command_name == "set_video_source" and action in self.video_sources:
                cmd = self.video_sources[action]
            else:
                _LOGGER.warning("Command %s not configured", command_name)
                return None

        if action and command_name != "set_video_source":
            cmd = f"{cmd} {action}"
        response = await self.send_raw_command(cmd)
        if raw_response:
            return response

        response = response.strip(WHITESPACE).lower()

        if command_name == "query_power":
            if response in ("lamp 1", "lamp1", "1"):
                return "on"
            if response in ("lamp 0", "lamp0", "0"):
                return "off"
            return None

        if command_name == "query_source":
            if response.startswith("src "):
                return response[4:].strip()
            return response

        if command_name in ("query_lamp_hours", "query_lamp2_hours"):
            match = re.search(r"(\d+)", response)
            if match:
                return match.group(1)
            return None

        if command_name == "query_model":
            if response.startswith("model "):
                return response[6:].strip()
            return response

        return response

    async def update_power(self) -> bool:
        response = await self.send_command("query_power")
        if response is None:
            if self.power_status == 1 or self.power_status == 3:
                return True
            self.power_status = -1
            return False

        if response == "on":
            self.power_status = 2  # on
            return True
        if response == "off":
            self.power_status = 0  # off
            return True

        self.power_status = -1
        return False

    async def update_video_source(self) -> bool:
        if not self.supports_feature("video_source"):
            return False
        source = await self.send_command("query_source")
        if source:
            self.video_source = self._map_video_source(source)
        return True

    async def update_lamp_hours(self) -> bool:
        if not self.supports_feature("lamp_hours"):
            return False
        hours = await self.send_command("query_lamp_hours")
        if hours is not None:
            try:
                self.lamp_hours = int(hours)
            except ValueError:
                pass
        return True

    async def turn_on(self) -> bool:
        await self.update_power()
        if self.power_status == 2:
            return True
        response = await self.send_command("power_on")
        if response is not None:
            self.power_status = 1  # powering on
            self._power_timestamp = asyncio.get_event_loop().time()
            return True
        return False

    async def turn_off(self) -> bool:
        await self.update_power()
        if self.power_status == 0:
            return True
        response = await self.send_command("power_off")
        if response is not None:
            self.power_status = 3  # powering off
            self._power_timestamp = asyncio.get_event_loop().time()
            return True
        return False

    async def select_video_source(self, source: str) -> bool:
        source = source.lower()
        if source not in self.video_sources:
            return False
        response = await self.send_command("set_video_source", source)
        if response is not None:
            self.video_source = source
            return True
        return False

    async def send_ir_command(self, command_name: str) -> bool:
        """Send an IR-style command like mute/freeze/hide."""
        response = await self.send_command(command_name)
        return response is not None

    async def update(self) -> bool:
        if not await self.update_power():
            return False

        if self.power_status == 2:
            await self.update_video_source()
            await self.update_lamp_hours()
        else:
            self.video_source = None

        return True

    async def _read_coroutine(self) -> None:
        previous_data: dict[str, Any] = {}
        while True:
            try:
                if not self.connection.is_open():
                    if not await self.connection.open():
                        await asyncio.sleep(self._interval or 10)
                        continue

                if await self.update_power():
                    if previous_data.get("power") != self.power_status:
                        self._notify_listeners("power", self.power_status)
                        previous_data["power"] = self.power_status

                    if self.power_status == 2:
                        await self.update_video_source()
                        if previous_data.get("source") != self.video_source:
                            self._notify_listeners("source", self.video_source)
                            previous_data["source"] = self.video_source

                        await self.update_lamp_hours()
                        if previous_data.get("lamp_hours") != self.lamp_hours:
                            self._notify_listeners("lamp_hours", self.lamp_hours)
                            previous_data["lamp_hours"] = self.lamp_hours

                await asyncio.sleep(self._interval or 10)
            except asyncio.CancelledError:
                break
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Read coroutine error")
                try:
                    await self.connection.close()
                except Exception:  # pylint: disable=broad-except
                    pass
                await asyncio.sleep(5)

        self._read_task = None

    def start_polling(self, interval: float) -> None:
        self._interval = interval
        if self._read_task is None or self._read_task.done():
            self._read_task = asyncio.create_task(self._read_coroutine())


class AcerProjectorTcp(AcerProjector):
    """Acer projector over TCP."""

    def __init__(
        self,
        host: str,
        port: int,
        model_hint: str | None = None,
    ) -> None:
        connection = AcerTcpConnection(host, port)
        super().__init__(connection, model_hint)
        self.unique_id = f"acer_{host}_{port}"


class AcerProjectorSerial(AcerProjector):
    """Acer projector over serial."""

    def __init__(
        self,
        port: str,
        baud_rate: int,
        model_hint: str | None = None,
    ) -> None:
        connection = AcerSerialConnection(port, baud_rate)
        super().__init__(connection, model_hint)
        self.unique_id = f"acer_{port.replace('/', '_')}"
