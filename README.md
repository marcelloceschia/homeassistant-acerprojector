# Acer Projector for Home Assistant

Custom integration for controlling Acer projectors over RS232 via TCP (e.g. USR-TCP232-410S serial-to-ethernet bridge) or direct serial connection.

Inspired by [homeassistant-benqprojector](https://github.com/rrooggiieerr/homeassistant-benqprojector).

## Features

- Media Player entity (power, input source)
- Sensor entity (lamp hours)
- Switch entities (mute, freeze, hide)
- Config Flow setup
- TCP and serial connection support
- Multi-model support via JSON configuration files
- Service to send raw RS232 commands

## Supported models

- Acer H6546Ki
- Generic Acer (default fallback)

More models can be added by creating a JSON file under `custom_components/acerprojector/configs/`.

## Installation

### HACS

Add this repository as a custom repository in HACS and install it.

### Manual

Copy the `custom_components/acerprojector` folder into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for "Acer Projector".

Choose either:
- **TCP connection** – enter host and port of your serial-to-ethernet bridge (e.g. `192.168.100.15:23`)
- **Serial connection** – select the serial port and baud rate

The model can be auto-detected or selected manually.

## Service

### `acerprojector.send_raw`

Send a raw RS232 command to the projector.

| Field | Description | Example |
|-------|-------------|---------|
| `device_id` | Device ID of the projector | - |
| `command` | Raw command string | `* 0 Lamp ?` |

## Adding a new model

Create a JSON file in `custom_components/acerprojector/configs/` named after the model in lowercase (e.g. `h6546ki.json`). Use `default.json` as a template.

## Acer RS232 protocol

Acer projectors typically use a command format like:

```
* 0 <command> <argument>\r
```

Examples:
- Power on: `* 0 IR 001`
- Power off: `* 0 IR 002`
- Query lamp: `* 0 Lamp ?`
- Query source: `* 0 Src ?`

Default serial settings: **9600 baud, 8 data bits, no parity, 1 stop bit**.
