# Acer Projector for Home Assistant

Custom integration for controlling Acer projectors over RS232 via TCP (e.g. USR-TCP232-410S serial-to-ethernet bridge) or direct serial connection.

Inspired by [homeassistant-benqprojector](https://github.com/rrooggiieerr/homeassistant-benqprojector).

## Features

- Media Player entity (power, input source, volume control)
- Select entity (input source dropdown)
- Number entity (volume control 0-20)
- Sensor entity (lamp hours)
- Switch entities (mute, freeze, hide, eco mode)
- Config Flow setup
- TCP and serial connection support
- Multi-model support via JSON configuration files
- Service to send raw RS232 commands
- Options flow to configure visible video sources
- **Source icons** displayed in the media player card

## Supported models

| Model | Status | Video Sources |
|-------|--------|---------------|
| **H6546Ki** | ✅ Tested | HDMI1/2/3, VGA, DVI, Composite, S-Video, DisplayPort, HDBaseT, Wireless, USB Display, Media, LAN/WiFi |
| H5382BD | ⚠️ Untested | HDMI1/2, VGA, Composite, Wireless |
| P6200S | ⚠️ Untested | HDMI1/2, VGA, DVI, Composite, S-Video, Component, DisplayPort, HDBaseT |
| UL6200 | ⚠️ Untested | HDMI1/2, VGA, DVI, Composite, S-Video, DisplayPort |
| X1261 | ⚠️ Untested | VGA1/2, DVI, S-Video, Composite, Component |
| default | ⚠️ Fallback | All known Acer sources |

More models can be added by creating a JSON file under `custom_components/acerprojector/configs/`.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations → Custom repositories**
3. Add `https://github.com/marcelloceschia/homeassistant-acerprojector`
4. Install **Acer Projector**
5. Restart Home Assistant

### Latest Developer Version

If you want the latest unreleased changes:

1. In HACS, open the Acer Projector integration
2. Click the three dots (⋮) → **Download again**
3. Enable **"Show beta versions"**
4. Select `master` or the latest commit

### Manual

Copy the `custom_components/acerprojector` folder into your Home Assistant `config/custom_components/` directory and restart Home Assistant.

## Configuration

Go to **Settings → Devices & Services → Add Integration** and search for "Acer Projector".

Choose either:
- **TCP connection** – enter host and port of your serial-to-ethernet bridge (e.g. `192.168.100.15:23`)
- **Serial connection** – select the serial port and baud rate

The model can be auto-detected or selected manually.

### Options

After setup, go to **Settings → Devices & Services → Acer Projector → Configure** to:
- Set polling interval
- Choose which video sources appear in the dropdown

## Source Icons

The integration automatically copies SVG icons to your Home Assistant `www/acerprojector/` folder on first setup. These icons are shown in the media player card depending on the active video source.

| Source | Icon file |
|--------|-----------|
| HDMI1/2/3 | `hdmi.svg` |
| VGA | `vga.svg` |
| DVI / DisplayPort | `monitor.svg` |
| Wireless | `wireless.svg` |
| USB Display | `usb.svg` |
| LAN / WiFi | `lan.svg` |
| Composite / S-Video / Component | `av.svg` |
| Media | `media.svg` |
| HDBaseT | `ethernet.svg` |
| (default) | `projector.svg` |

### Custom Icons

You can replace any icon by placing your own SVG file in `config/www/acerprojector/`. The integration **only copies missing icons** — existing files are never overwritten, so your custom icons stay intact.

To restore the default icons, delete the files from `config/www/acerprojector/` and restart Home Assistant.

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

## Releases

| Version | Date | Notes |
|---------|------|-------|
| [v0.0.1](https://github.com/marcelloceschia/homeassistant-acerprojector/releases/tag/v0.0.1) | 2025-06-07 | Initial release |
