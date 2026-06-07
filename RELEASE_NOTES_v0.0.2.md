# Release v0.0.2

## What's New

### Source Icons in Media Player Card
The media player card now shows a visual icon for the currently active video source (HDMI, VGA, Wireless, etc.). Icons are automatically copied to your Home Assistant `www/acerprojector/` folder on first setup.

### Volume Control in Media Player
The media player entity now supports volume control:
- `VOLUME_SET` – set absolute level (0–20)
- `VOLUME_STEP` – volume up/down buttons
- `VOLUME_MUTE` – mute/unmute toggle

Volume is persisted across Home Assistant restarts.

### Custom Icons Support
You can replace the default SVG icons with your own designs. Simply place your custom `.svg` files in `config/www/acerprojector/`. The integration only copies missing icons, so your custom files are never overwritten.

## Changelog

| Commit | Description |
|--------|-------------|
| `9f642c0` | docs: add source icons section to README; skip existing icons on setup |
| `4b5018f` | feat: auto-copy icons to www on setup + local image paths in media_player |
| `14a6c06` | Add local SVG assets for video source images |
| `3ae3cc5` | Add media_image_url per video source (HDMI, VGA, DisplayPort, Wireless icons) |
| `df3a717` | Add volume control to Media Player entity (VOLUME_SET, VOLUME_STEP, VOLUME_MUTE) |
| `812aa91` | Update README with HACS install instructions, beta versions, release table |

## Assets

- `acerprojector.zip` – HACS-ready release package
