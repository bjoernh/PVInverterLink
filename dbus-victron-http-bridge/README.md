# Victron Venus OS D-Bus HTTP Bridge

A Python bridge script that runs on Victron Venus OS devices (Cerbo GX, etc.) to collect solar inverter data from D-Bus and send it to a remote HTTP backend.

## Features

- ✅ Monitors all connected Victron solar chargers automatically
- ✅ Supports single and multi-MPPT devices (up to 4 trackers)
- ✅ Collects power, voltage, and yield data
- ✅ Posts measurements to HTTP endpoint every 30 seconds (configurable)
- ✅ Automatic retry and error handling
- ✅ Integrates with Venus OS daemontools for reliability
- ✅ Logs to syslog for easy monitoring

## Prerequisites

### Venus OS Requirements

- Victron Cerbo GX, Venus GX, or similar device running Venus OS
- SSH access enabled (Settings → General → SSH on LAN)
- Internet connectivity for posting data to backend
- Python packages:
  - `python3-dbus`
  - `python3-gi`
  - `python3-requests`

### Backend Requirements

- Backend server running the Solar Backend API
- User account with API key generated
- Inverters registered with correct `serial_logger` format

## Installation

### 1. Enable SSH on Venus OS

1. Go to **Settings → General**
2. Enable **SSH on LAN**
3. Note the IP address shown at the bottom

### 2. Connect to Venus OS

```bash
ssh root@<venus-os-ip>
# Default password: blank (just press Enter)
# You'll be prompted to set a new password on first login
```

### 3. Install Required Packages

```bash
opkg update
opkg install python3-dbus python3-gi python3-requests
```

### 4. Download and Install Bridge

#### Option A: Using git (if available)

```bash
cd /data
git clone https://github.com/your-repo/dbus-victron-http-bridge.git
cd dbus-victron-http-bridge
```

#### Option B: Manual upload via SCP

On your local machine:

```bash
scp -r dbus-victron-http-bridge root@<venus-os-ip>:/data/
```

Then on Venus OS:

```bash
cd /data/dbus-victron-http-bridge
```

### 5. Configure the Bridge

```bash
# Copy example config and edit it
cp config.ini.example config.ini
vi config.ini
```

Required settings:

```ini
[backend]
url = https://your-backend.com
api_key = your-api-key-from-backend

[device]
cerbo_serial = HQ2345ABCDE  # Your Cerbo GX serial
update_interval = 30
```

### 6. Get Your Cerbo GX Serial Number

```bash
dbus -y com.victronenergy.system /Serial GetValue
```

Example output: `HQ2345ABCDE`

### 7. Run Installation Script

```bash
chmod +x install.sh
./install.sh
```

The installer will:
- Check prerequisites
- Copy files to `/data/dbus-victron-http-bridge/`
- Download `velib_python` if needed
- Set up daemontools service
- Configure boot persistence

### 8. Configure Backend Inverters

In your backend, create inverter entries for each solar charger using the **actual device serial number**.

**Serial Logger Format**: Use the device's actual serial number (e.g., `HQ2208AXN7V`)

**Finding Device Serial Numbers:**

```bash
# List all solar chargers
dbus -y | grep solarcharger

# Example output:
# com.victronenergy.solarcharger.ttyUSB0
# com.victronenergy.solarcharger.ttyUSB1

# Get serial number for a specific charger
dbus -y com.victronenergy.solarcharger.ttyUSB0 /Serial GetValue
# Output: HQ2208AXN7V

dbus -y com.victronenergy.solarcharger.ttyUSB1 /Serial GetValue
# Output: HQ22377MQDC
```

These are the actual device serial numbers printed on your solar chargers.

## Usage

### Service Management

The bridge runs as a daemontools service:

```bash
# Check service status
svstat /service/dbus-victron-http-bridge

# Restart service
svc -t /service/dbus-victron-http-bridge

# Stop service
svc -d /service/dbus-victron-http-bridge

# Start service
svc -u /service/dbus-victron-http-bridge
```

### View Logs

```bash
# Follow live logs
tail -f /var/log/messages | grep victron-http-bridge

# View recent logs
grep victron-http-bridge /var/log/messages | tail -20
```

### Test Configuration

You can test the bridge manually before installing as a service:

```bash
cd /data/dbus-victron-http-bridge
python3 dbus-victron-http-bridge.py
```

Press `Ctrl+C` to stop.

## Configuration Reference

### config.ini

```ini
[backend]
# Backend URL (without trailing slash)
url = https://your-backend.com

# API key from your backend user account
api_key = abc123xyz789...

# HTTP request timeout in seconds
timeout = 10

[device]
# Your Cerbo GX serial number
cerbo_serial = HQ2345ABCDE

# How often to post measurements (seconds)
# Recommended: 30 seconds
update_interval = 30

[logging]
# Log level: DEBUG, INFO, WARNING, ERROR
level = INFO
```

## Data Format

The bridge posts data in this format:

```json
{
  "timestamp": "2025-10-30T15:27:33.058551+00:00",
  "cerbo_serial": "c0619ab35133",
  "devices": [
    {
      "device_instance": 281,
      "serial": "HQ2208AXN7V",
      "name": "PV Carport",
      "product_name": "BlueSolar Charger MPPT 150/45 rev3",
      "reachable": true,
      "producing": false,
      "last_update": 1761838053,
      "yield_power_w": 16.38,
      "yield_total_kwh": 1274.38,
      "trackers": [
        {
          "tracker": 0,
          "name": "PV",
          "voltage": 62.55,
          "power": 16.38
        }
      ]
    },
    {
      "device_instance": 280,
      "serial": "HQ22377MQDC",
      "name": "PV Garden",
      "product_name": "BlueSolar Charger MPPT 150/45 rev3",
      "reachable": true,
      "producing": false,
      "last_update": 1761838053,
      "yield_power_w": 348.09,
      "yield_total_kwh": 6515.43,
      "trackers": [
        {
          "tracker": 0,
          "name": "PV",
          "voltage": 98.73,
          "power": 348.09
        }
      ]
    }
  ]
}
```

## Troubleshooting

### Service Not Starting

1. Check service status:
   ```bash
   svstat /service/dbus-victron-http-bridge
   ```

2. Check logs for errors:
   ```bash
   tail -20 /var/log/messages | grep victron-http-bridge
   ```

3. Test manually:
   ```bash
   cd /data/dbus-victron-http-bridge
   python3 dbus-victron-http-bridge.py
   ```

### Authentication Errors (401)

- Verify API key in `config.ini` matches backend
- Regenerate API key in backend if needed

### Device Not Found Errors (404)

- Verify inverters exist in backend database
- Check serial_logger matches the actual device serial number
- Get the correct serial from D-Bus: `dbus -y com.victronenergy.solarcharger.ttyUSB0 /Serial GetValue`

### No Data Being Posted

1. Check if solar chargers are visible on D-Bus:
   ```bash
   dbus -y | grep solarcharger
   ```

2. Check if bridge can read data:
   ```bash
   dbus -y com.victronenergy.solarcharger.ttyUSB0 /Yield/Power GetValue
   ```

3. Verify network connectivity:
   ```bash
   ping your-backend.com
   curl -I https://your-backend.com
   ```

### Increase Logging

Change log level to DEBUG in `config.ini`:

```ini
[logging]
level = DEBUG
```

Restart service:

```bash
svc -t /service/dbus-victron-http-bridge
```

## Supported Devices

The bridge supports all Victron solar chargers that publish data via D-Bus:

- SmartSolar MPPT (all models)
- BlueSolar MPPT (with VE.Direct)
- MPPT RS (multi-tracker models)

### Multi-Tracker Support

For MPPT RS models with 2 or 4 trackers, the bridge automatically reads per-tracker data:

- Voltage and power per tracker
- Aggregated yield data at device level
- Proper channel mapping in backend

## Uninstallation

```bash
# Stop and remove service
svc -d /service/dbus-victron-http-bridge
rm /service/dbus-victron-http-bridge

# Remove from rc.local
vi /data/rc.local
# Delete the line containing: dbus-victron-http-bridge

# Remove files
rm -rf /data/dbus-victron-http-bridge
```

## Development

### Project Structure

```
dbus-victron-http-bridge/
├── dbus-victron-http-bridge.py  # Main bridge script
├── config.ini.example            # Example configuration
├── config.ini                    # Your configuration (not in git)
├── service/
│   └── run                       # Daemontools service runner
├── install.sh                    # Installation script
├── README.md                     # This file
└── ext/
    └── velib_python/             # Victron D-Bus library (auto-downloaded)
```

### Testing Locally

The script can run on non-Venus OS systems for testing (with warnings):

```bash
python3 dbus-victron-http-bridge.py
```

### D-Bus Paths Reference

Key D-Bus paths used by the bridge:

| Path | Description | Type |
|------|-------------|------|
| `/DeviceInstance` | Unique device instance ID | int |
| `/Serial` | Device serial number | string |
| `/CustomName` | User-set device name | string |
| `/ProductName` | Product model name | string |
| `/State` | Operational state | int |
| `/Yield/Power` | Current power output (W) | float |
| `/Yield/System` | Lifetime energy (kWh) | float |
| `/NrOfTrackers` | Number of MPPT trackers | int |
| `/Pv/V` | PV voltage (single tracker) | float |
| `/Pv/{n}/V` | PV voltage tracker n | float |
| `/Pv/{n}/P` | PV power tracker n | float |

### State Values

- `0` = Off
- `2` = Fault
- `3` = Bulk charging (producing)
- `4` = Absorption (producing)
- `5` = Float (producing)

## License

MIT License - see LICENSE file

## Support

For issues or questions:
- Backend issues: Check backend documentation
- Venus OS issues: Victron Community Forums
- Bridge issues: Create GitHub issue

## Contributing

Contributions welcome! Please:
1. Test on actual Venus OS hardware
2. Follow existing code style
3. Update documentation
4. Add logging for new features
