# Kärcher Home & Garden — Home Assistant Integration

Custom component for Home Assistant. Connects to Kärcher's IoT cloud (`api.iot.kaercher.com` + AWS IoT `eu-west-1`) and exposes each paired device as a HA device with full control.

## Features (v0.2)

### Sensors
- Battery level (%), 4 consumable life sensors (HEPA, main brush, side brush, mop)
- Cleaning time, cleaning area, WiFi RSSI, firmware version, fault code

### Binary Sensors
- Online (connectivity), fault (problem), provisioned (diagnostic)

### Vacuum Entity (with commands!)
- Start / pause / stop / return home / locate
- Room-specific cleaning via `vacuum.send_command`
- Activity mapped from device shadow (idle, cleaning, paused, returning, charging, error)

### Map Camera
- Renders apartment floor plan from robot's protobuf map data
- Room colors, walls, charger position, robot position, room labels
- Fetched via REST/S3, rendered as PNG

## Install (HACS)
1. HACS → ⋮ → Custom repositories → URL: `https://github.com/MaxXLive/kaercher-home-and-garden-ha` → Category: Integration
2. Search "Kärcher" in HACS → Download
3. Restart HA
4. Settings → Devices & Services → Add Integration → Kärcher Home & Garden
5. Paste a Cognito **refresh token** (see below)

## Install (manual)
1. Copy `custom_components/karcher_hg/` into your HA `config/custom_components/`.
2. Restart HA.
3. Add integration, paste refresh token.

## Refresh-token extraction
mitmproxy on the running Kärcher app, look for:
`POST https://cognito-idp.eu-west-1.amazonaws.com/`
with `x-amz-target: AWSCognitoIdentityProviderService.InitiateAuth`
→ The `RefreshToken` from `AuthenticationResult` is what HA needs.

## Architecture
```
auth.py        → refresh-token → Cognito IdP → Cognito Identity AWS creds
api.py         → REST commands + map download (api.iot.kaercher.com)
iot.py         → SigV4-signed shadow reads (all 5 named shadows)
coordinator.py → 30s poll: device list + shadows → KarcherDevice dataclass
camera.py      → map fetch (S3) + protobuf parse + PNG render
sensor.py / binary_sensor.py / vacuum.py → HA entities
```
