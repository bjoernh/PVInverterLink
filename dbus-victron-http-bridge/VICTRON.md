# Victron Venus OS D-Bus Developer Reference

Comprehensive guide to developing applications for Victron Energy's Venus OS using D-Bus communication.

**Last Updated**: October 30, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [D-Bus Fundamentals](#d-bus-fundamentals)
3. [Venus OS Architecture](#venus-os-architecture)
4. [D-Bus Services Reference](#d-bus-services-reference)
5. [Development Tools](#development-tools)
6. [Python Libraries](#python-libraries)
7. [Code Examples](#code-examples)
8. [Best Practices](#best-practices)
9. [Official Documentation](#official-documentation)
10. [Community Resources](#community-resources)

---

## Overview

### What is Venus OS?

Venus OS is Victron Energy's Linux-based operating system that runs on their GX devices (Cerbo GX, Venus GX, etc.). It provides monitoring and control for solar systems, batteries, inverters, and other energy devices.

**Official Website**: https://www.victronenergy.com/live/venus-os:start

### What is D-Bus?

D-Bus is an inter-process communication (IPC) system used in Venus OS for communication between services. All Victron devices connected to the GX device publish their data on D-Bus, and applications can read or write values.

**D-Bus Official**: https://www.freedesktop.org/wiki/Software/dbus/

---

## D-Bus Fundamentals

### Service Naming Convention

Victron D-Bus services follow this pattern:

```
com.victronenergy.<product-type>.<connection-identifier>
```

**Examples**:
- `com.victronenergy.solarcharger.ttyUSB0` - Solar charger on USB port 0
- `com.victronenergy.battery.ttyO2` - Battery monitor on VE.Direct port 2
- `com.victronenergy.vebus.ttyUSB1` - Multi/Quattro on USB port 1

**Reference**: https://github.com/victronenergy/venus/wiki/dbus#service-name

### Object Paths

Each service exposes multiple paths representing different values:

```
/<Category>/<Subcategory>/<Value>
```

**Examples**:
- `/Pv/V` - PV voltage
- `/Yield/Power` - Current power yield
- `/Dc/0/Voltage` - DC voltage on channel 0
- `/DeviceInstance` - Unique device identifier

**Reference**: https://github.com/victronenergy/venus/wiki/dbus#paths

### Interfaces

All object paths implement the `com.victronenergy.BusItem` interface with these methods:

| Method | Description | Return |
|--------|-------------|--------|
| `GetValue()` | Get current value | Variant (int, float, string, etc.) |
| `GetText()` | Get formatted text with units | String (e.g., "245.5 W") |
| `SetValue(value)` | Write value | 0 on success, error code on failure |
| `GetMin()` | Get minimum allowed value | Variant |
| `GetMax()` | Get maximum allowed value | Variant |

**Reference**: https://github.com/victronenergy/venus/wiki/dbus-api#dbus-interface

---

## Venus OS Architecture

### System Services

Special system-level services:

| Service | Purpose |
|---------|---------|
| `com.victronenergy.system` | System totals (aggregated power, consumption) |
| `com.victronenergy.settings` | Non-volatile settings storage |
| `com.victronenergy.gui` | Display and user interface |
| `com.victronenergy.modbustcp` | Modbus TCP gateway |
| `com.victronenergy.mqtt` | MQTT broker integration |

**Reference**: https://github.com/victronenergy/venus/wiki/dbus#system-services

### Product Types

Common product types you'll encounter:

| Type | Description | Example Products |
|------|-------------|------------------|
| `solarcharger` | Solar charge controllers | SmartSolar MPPT, BlueSolar MPPT, MPPT RS |
| `vebus` | Inverter/chargers | MultiPlus, Quattro |
| `battery` | Battery monitors | BMV-700, SmartShunt, Lynx Shunt VE.Can |
| `inverter` | Inverters (non-VE.Bus) | Phoenix Inverter |
| `charger` | AC chargers | Skylla-TG, Skylla-i |
| `grid` | AC energy meters | ET112, EM24 |
| `pvinverter` | PV inverters | Fronius, SMA |
| `tank` | Tank sensors | Fluid level sensors |
| `generator` | Generator controllers | Fisher Panda, Victron GX Generator |

**Reference**: https://github.com/victronenergy/venus/wiki/dbus#service-types

---

## D-Bus Services Reference

### Solar Charger Service

**Service Pattern**: `com.victronenergy.solarcharger.*`

#### Mandatory Paths

| Path | Type | Description | Units |
|------|------|-------------|-------|
| `/DeviceInstance` | int | Unique device ID (0-32767) | - |
| `/ProductId` | int | Victron product ID | - |
| `/ProductName` | string | Product model name | - |
| `/Serial` | string | Device serial number | - |
| `/FirmwareVersion` | string | Firmware version | - |
| `/Connected` | int | Connection status (0 or 1) | - |
| `/CustomName` | string | User-defined name | - |

#### Operational Data

| Path | Type | Description | Units |
|------|------|-------------|-------|
| `/State` | int | Operational state (see below) | - |
| `/Yield/Power` | float | Current PV power | W |
| `/Yield/System` | float | Lifetime energy yield | kWh |
| `/Yield/User` | float | User-resettable yield | kWh |
| `/Pv/V` | float | PV voltage (single tracker) | V |
| `/Pv/{n}/V` | float | PV voltage tracker n (0-3) | V |
| `/Pv/{n}/P` | float | PV power tracker n (0-3) | W |
| `/NrOfTrackers` | int | Number of MPPT trackers | - |
| `/Dc/0/Voltage` | float | Battery voltage | V |
| `/Dc/0/Current` | float | Battery current | A |

#### State Values

| Value | State | Description |
|-------|-------|-------------|
| 0 | Off | Charger off |
| 2 | Fault | Fault condition |
| 3 | Bulk | Bulk charging (actively producing) |
| 4 | Absorption | Absorption phase (producing) |
| 5 | Float | Float phase (producing) |
| 6 | Storage | Storage mode |
| 7 | Equalize | Equalization |
| 11 | Other (Hub-1) | Hub-1 mode |
| 252 | External Control | Under external control |

**Reference**: https://github.com/victronenergy/venus/wiki/dbus-api#solarcharger

### VE.Bus Service (Multi/Quattro)

**Service Pattern**: `com.victronenergy.vebus.*`

#### Key Paths

| Path | Type | Description | Units |
|------|------|-------------|-------|
| `/Ac/ActiveIn/L1/P` | float | AC input power L1 | W |
| `/Ac/Out/L1/P` | float | AC output power L1 | W |
| `/Ac/Out/L1/V` | float | AC output voltage L1 | V |
| `/Ac/Out/L1/I` | float | AC output current L1 | A |
| `/Dc/0/Voltage` | float | DC bus voltage | V |
| `/Dc/0/Current` | float | DC current | A |
| `/Soc` | float | State of charge | % |
| `/State` | int | Operating state | - |
| `/Mode` | int | Operating mode | - |

**Reference**: https://github.com/victronenergy/venus/wiki/dbus-api#vebus

### Battery Service

**Service Pattern**: `com.victronenergy.battery.*`

#### Key Paths

| Path | Type | Description | Units |
|------|------|-------------|-------|
| `/Dc/0/Voltage` | float | Battery voltage | V |
| `/Dc/0/Current` | float | Battery current | A |
| `/Dc/0/Power` | float | Battery power | W |
| `/Soc` | float | State of charge | % |
| `/TimeToGo` | float | Time to empty | seconds |
| `/ConsumedAmphours` | float | Consumed Ah | Ah |
| `/History/DeepestDischarge` | float | Deepest discharge | Ah |
| `/History/TotalAhDrawn` | float | Lifetime Ah drawn | Ah |

**Reference**: https://github.com/victronenergy/venus/wiki/dbus-api#battery

### System Service

**Service**: `com.victronenergy.system`

Aggregated data from all connected devices. This is what powers the Venus OS dashboard.

#### Key Paths

| Path | Type | Description | Units |
|------|------|-------------|-------|
| `/Dc/Battery/Voltage` | float | Battery voltage | V |
| `/Dc/Battery/Current` | float | Battery current | A |
| `/Dc/Battery/Power` | float | Battery power | W |
| `/Dc/Pv/Power` | float | Total PV power (all chargers) | W |
| `/Dc/Pv/Current` | float | Total PV current | A |
| `/Dc/System/Power` | float | DC system power | W |
| `/Ac/Consumption/L1/Power` | float | AC consumption L1 | W |
| `/Ac/Grid/L1/Power` | float | Grid power L1 | W |
| `/Serial` | string | GX device serial number | - |

**Reference**: https://github.com/victronenergy/dbus-systemcalc-py

---

## Development Tools

### 1. SSH Access

Enable SSH to access Venus OS command line:

1. Go to **Settings → General** on Venus OS
2. Enable **SSH on LAN**
3. Set root password if prompted

```bash
ssh root@<venus-os-ip>
# Default password: blank (just press Enter on first login)
```

**Documentation**: https://www.victronenergy.com/live/ccgx:root_access

### 2. dbus Command Line Tool

Venus OS includes a built-in `dbus` command for querying services.

#### List all services:
```bash
dbus -y
```

#### List specific service type:
```bash
dbus -y | grep solarcharger
```

#### Get value from path:
```bash
dbus -y com.victronenergy.solarcharger.ttyUSB0 /Yield/Power GetValue
```

#### Set value:
```bash
dbus -y com.victronenergy.solarcharger.ttyUSB0 /CustomName SetValue "My Solar Charger"
```

#### Get formatted text:
```bash
dbus -y com.victronenergy.solarcharger.ttyUSB0 /Yield/Power GetText
# Output: "245.5 W"
```

### 3. dbus-spy

Interactive D-Bus browser built into Venus OS.

```bash
dbus-spy
```

**Features**:
- Browse all services and paths
- See real-time values
- Navigate with arrow keys
- Press 'q' to quit

**GitHub**: https://github.com/victronenergy/dbus-spy

### 4. dbus-send

Low-level D-Bus command (standard Linux tool).

```bash
dbus-send --print-reply --system \
  --dest=com.victronenergy.solarcharger.ttyUSB0 \
  /Yield/Power \
  com.victronenergy.BusItem.GetValue
```

### 5. dbus-monitor

Monitor D-Bus traffic in real-time:

```bash
dbus-monitor --system
```

Filter for specific service:
```bash
dbus-monitor --system "sender='com.victronenergy.solarcharger.ttyUSB0'"
```

### 6. Remote Console

Web-based interface to Venus OS:

```
http://<venus-os-ip>
```

**Features**:
- Dashboard view
- Device settings
- System settings
- VRM portal connection

**Documentation**: https://www.victronenergy.com/live/venus-os:start#remote_console

### 7. VRM Portal

Cloud-based monitoring and remote control:

**URL**: https://vrm.victronenergy.com

**Features**:
- Historical data
- Remote monitoring
- Alarms and notifications
- Remote console access
- Two-way communication

**Documentation**: https://www.victronenergy.com/live/vrm_portal:start

### 8. Modbus TCP

For non-D-Bus applications, use Modbus TCP:

**Enable**: Settings → Services → Modbus TCP → Enabled

**Port**: 502 (default)

**Excel Register Map**: https://www.victronenergy.com/upload/documents/Modbus-TCP-register-list-2.90.xlsx

**Documentation**: https://www.victronenergy.com/live/ccgx:modbustcp_faq

### 9. MQTT

Publish D-Bus data to MQTT broker:

**Enable**: Settings → Services → MQTT → Enabled

**Topics**: `N/<vrm-id>/<service>/<path>`

Example: `N/c0619ab35133/solarcharger/281/Yield/Power`

**GitHub**: https://github.com/victronenergy/dbus-mqtt

**Documentation**: https://github.com/victronenergy/dbus-mqtt/blob/master/README.md

---

## Python Libraries

### velib_python

Official Victron Python library for D-Bus communication.

**GitHub**: https://github.com/victronenergy/velib_python

#### Key Modules

**1. `vedbus.py`** - Core D-Bus service handling

```python
from vedbus import VeDbusService

# Create a new D-Bus service
service = VeDbusService("com.victronenergy.example")

# Add paths
service.add_path("/Serial", "12345")
service.add_path("/Power", 245.5)
```

**2. `dbusmonitor.py`** - Monitor multiple D-Bus services

```python
from dbusmonitor import DbusMonitor

# Define what to monitor
dbus_tree = {
    'com.victronenergy.solarcharger': {
        '/Yield/Power': lambda x: x,
        '/Dc/0/Voltage': lambda x: x,
    }
}

# Create monitor
monitor = DbusMonitor(dbus_tree)

# Get values
services = monitor.get_service_list('com.victronenergy.solarcharger')
for service in services:
    power = monitor.get_value(service, '/Yield/Power')
    print(f"{service}: {power}W")
```

**3. `settingsdevice.py`** - Store settings in flash

```python
from settingsdevice import SettingsDevice

settings = SettingsDevice(
    bus=dbus.SystemBus(),
    supportedSettings={
        'update_interval': ['/Settings/UpdateInterval', 30, 0, 600],
        'api_key': ['/Settings/ApiKey', '', 0, 0],
    }
)

# Read setting
interval = settings['update_interval']

# Write setting
settings['update_interval'] = 60
```

#### Installation on Venus OS

velib_python is pre-installed at:
```
/opt/victronenergy/dbus-systemcalc-py/ext/velib_python
```

For custom scripts:
```bash
cd /data/my-script
git clone https://github.com/victronenergy/velib_python.git ext/velib_python
```

In your Python script:
```python
import sys
import os
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext/velib_python'))
```

### dbus-python

Standard Python D-Bus library (lower level).

**Documentation**: https://dbus.freedesktop.org/doc/dbus-python/

**Install on Venus OS**:
```bash
opkg update
opkg install python3-dbus
```

**Basic Usage**:
```python
import dbus

# Connect to system bus
bus = dbus.SystemBus()

# Get service
service = bus.get_object(
    'com.victronenergy.solarcharger.ttyUSB0',
    '/Yield/Power'
)

# Get interface
interface = dbus.Interface(service, 'com.victronenergy.BusItem')

# Call method
value = interface.GetValue()
print(f"Power: {value}W")
```

---

## Code Examples

### Example 1: Read All Solar Chargers

```python
#!/usr/bin/env python3
import dbus

def get_solar_chargers():
    """List all solar chargers on D-Bus."""
    bus = dbus.SystemBus()

    # Get DBus object
    dbus_obj = bus.get_object('org.freedesktop.DBus', '/')
    dbus_iface = dbus.Interface(dbus_obj, 'org.freedesktop.DBus')

    # List all services
    services = dbus_iface.ListNames()

    # Filter for solar chargers
    solar_chargers = [s for s in services if 'solarcharger' in s]

    return solar_chargers

def get_charger_data(service_name):
    """Get data from a solar charger."""
    bus = dbus.SystemBus()

    def get_value(path):
        try:
            obj = bus.get_object(service_name, path)
            iface = dbus.Interface(obj, 'com.victronenergy.BusItem')
            return iface.GetValue()
        except:
            return None

    return {
        'serial': get_value('/Serial'),
        'name': get_value('/CustomName') or get_value('/ProductName'),
        'power': get_value('/Yield/Power'),
        'voltage': get_value('/Pv/V'),
        'state': get_value('/State'),
    }

# Main
chargers = get_solar_chargers()
for charger in chargers:
    data = get_charger_data(charger)
    print(f"{charger}:")
    print(f"  Serial: {data['serial']}")
    print(f"  Name: {data['name']}")
    print(f"  Power: {data['power']}W")
    print(f"  Voltage: {data['voltage']}V")
    print(f"  State: {data['state']}")
```

**Reference**: https://github.com/victronenergy/velib_python/blob/master/examples/

### Example 2: Monitor Values with Callbacks

```python
#!/usr/bin/env python3
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

def value_changed(path, value):
    """Callback when value changes."""
    print(f"Value changed: {path} = {value}")

def monitor_service(service_name, paths):
    """Monitor specific paths in a service."""
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()

    for path in paths:
        obj = bus.get_object(service_name, path)
        iface = dbus.Interface(obj, 'com.victronenergy.BusItem')

        # Subscribe to PropertiesChanged signal
        obj.connect_to_signal(
            'PropertiesChanged',
            lambda changes: value_changed(path, changes.get('Value')),
            dbus_interface='com.victronenergy.BusItem'
        )

    # Run main loop
    mainloop = GLib.MainLoop()
    mainloop.run()

# Monitor power and voltage
monitor_service(
    'com.victronenergy.solarcharger.ttyUSB0',
    ['/Yield/Power', '/Pv/V']
)
```

### Example 3: Using DbusMonitor (Recommended)

```python
#!/usr/bin/env python3
import sys
import os
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

# Add velib_python to path
sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

from dbusmonitor import DbusMonitor

def on_value_changed(dbusServiceName, dbusPath, dict, changes, deviceInstance):
    """Callback when monitored value changes."""
    print(f"Changed: {dbusServiceName}{dbusPath} = {changes['Value']}")

def on_device_added(dbusServiceName, deviceInstance):
    """Callback when new device appears."""
    print(f"Device added: {dbusServiceName} (instance {deviceInstance})")

def on_device_removed(dbusServiceName, deviceInstance):
    """Callback when device disappears."""
    print(f"Device removed: {dbusServiceName} (instance {deviceInstance})")

# Initialize D-Bus main loop
DBusGMainLoop(set_as_default=True)

# Define what to monitor
dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
dbus_tree = {
    'com.victronenergy.solarcharger': {
        '/DeviceInstance': dummy,
        '/Serial': dummy,
        '/CustomName': dummy,
        '/ProductName': dummy,
        '/Yield/Power': dummy,
        '/Pv/V': dummy,
        '/State': dummy,
    },
}

# Create monitor
monitor = DbusMonitor(
    dbus_tree,
    valueChangedCallback=on_value_changed,
    deviceAddedCallback=on_device_added,
    deviceRemovedCallback=on_device_removed
)

# Get all solar chargers
services = monitor.get_service_list('com.victronenergy.solarcharger')
print(f"Found {len(services)} solar chargers")

for service in services:
    serial = monitor.get_value(service, '/Serial')
    power = monitor.get_value(service, '/Yield/Power')
    print(f"  {service}: Serial={serial}, Power={power}W")

# Run main loop
mainloop = GLib.MainLoop()
print("Monitoring... Press Ctrl+C to exit")
mainloop.run()
```

**Reference**: https://github.com/victronenergy/velib_python/blob/master/examples/dbusmonitor_example.py

### Example 4: Create Custom D-Bus Service

```python
#!/usr/bin/env python3
import sys
import os
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import dbus

sys.path.insert(1, '/opt/victronenergy/dbus-systemcalc-py/ext/velib_python')

from vedbus import VeDbusService

# Initialize
DBusGMainLoop(set_as_default=True)

# Create service
service = VeDbusService("com.victronenergy.example")

# Add management paths (mandatory)
service.add_path('/Mgmt/ProcessName', 'my-example')
service.add_path('/Mgmt/ProcessVersion', '1.0')
service.add_path('/Mgmt/Connection', 'Custom connection')

# Add device info
service.add_path('/DeviceInstance', 100)
service.add_path('/ProductId', 0)
service.add_path('/ProductName', 'My Custom Device')
service.add_path('/FirmwareVersion', '1.0.0')
service.add_path('/Serial', 'ABC123')
service.add_path('/Connected', 1)

# Add data paths
service.add_path('/Power', 0.0, writeable=True)
service.add_path('/Voltage', 0.0, writeable=True)

print("Service published on D-Bus: com.victronenergy.example")
print("Try: dbus -y com.victronenergy.example /Power GetValue")

# Run main loop
mainloop = GLib.MainLoop()
mainloop.run()
```

**Reference**: https://github.com/victronenergy/velib_python/blob/master/examples/vedbusservice_example.py

---

## Best Practices

### 1. Service Discovery

✅ **DO**: Use `DbusMonitor` to automatically discover services
```python
services = monitor.get_service_list('com.victronenergy.solarcharger')
```

❌ **DON'T**: Hardcode service names (connection identifiers change)
```python
# Bad - ttyUSB0 might change
power = get_value('com.victronenergy.solarcharger.ttyUSB0', '/Yield/Power')
```

### 2. Handle Missing Values

✅ **DO**: Always check for None
```python
value = monitor.get_value(service, '/Yield/Power')
if value is not None:
    total += value
```

❌ **DON'T**: Assume values exist
```python
total += monitor.get_value(service, '/Yield/Power')  # May crash
```

### 3. Units

✅ **DO**: Use SI units as documented
- Voltage: Volts (V)
- Current: Amperes (A)
- Power: Watts (W)
- Energy: Kilowatt-hours (kWh)
- Temperature: Celsius (°C)

**Exception**: Energy is in kWh, not Wh or J

**Reference**: https://github.com/victronenergy/venus/wiki/dbus-api#units

### 4. Invalid Values

When a value is invalid or not available, D-Bus returns an empty array `[]` or `None`.

✅ **DO**: Check for invalid values
```python
soc = monitor.get_value(service, '/Soc')
if soc is not None and soc != []:
    print(f"SoC: {soc}%")
```

### 5. Service Installation Location

✅ **DO**: Install in `/data/` for persistence
```bash
/data/my-custom-service/
```

❌ **DON'T**: Install in `/opt/` or `/usr/` (gets wiped on firmware update)

**Reference**: https://www.victronenergy.com/live/ccgx:root_access#file_system_and_firmware_updates

### 6. Logging

✅ **DO**: Log to syslog for Venus OS integration
```python
import logging
import logging.handlers

logger = logging.getLogger(__name__)
syslog = logging.handlers.SysLogHandler(address='/dev/log')
logger.addHandler(syslog)
```

View logs:
```bash
tail -f /var/log/messages
```

### 7. Error Handling

✅ **DO**: Catch D-Bus exceptions
```python
try:
    value = interface.GetValue()
except dbus.exceptions.DBusException as e:
    logger.error(f"D-Bus error: {e}")
```

### 8. Main Loop

✅ **DO**: Use GLib main loop for event-driven apps
```python
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
mainloop = GLib.MainLoop()
mainloop.run()
```

### 9. Device Instance

Use `/DeviceInstance` for unique identification, not serial or connection.

✅ **DO**:
```python
instance = monitor.get_value(service, '/DeviceInstance')
```

**Reference**: https://github.com/victronenergy/venus/wiki/dbus-api#deviceinstance

### 10. Permissions

When writing to D-Bus, check if path is writeable:

```python
# Check if writable before setting
obj = bus.get_object(service, '/CustomName')
interface = dbus.Interface(obj, 'com.victronenergy.BusItem')
result = interface.SetValue('New Name')
if result == 0:
    print("Success")
else:
    print(f"Error: {result}")
```

---

## Official Documentation

### Primary Resources

1. **Venus OS Wiki**
   https://www.victronenergy.com/live/venus-os:start
   Official Venus OS documentation

2. **D-Bus API Documentation**
   https://github.com/victronenergy/venus/wiki/dbus-api
   Complete D-Bus service reference

3. **D-Bus Service List**
   https://github.com/victronenergy/venus/wiki/dbus
   All available services and paths

4. **velib_python GitHub**
   https://github.com/victronenergy/velib_python
   Official Python D-Bus library

5. **How to Write a Driver**
   https://github.com/victronenergy/venus/wiki/howto-add-a-driver-to-Venus
   Complete guide for creating custom services

### GitHub Repositories

6. **dbus-systemcalc-py**
   https://github.com/victronenergy/dbus-systemcalc-py
   System calculation service (how aggregation works)

7. **dbus-mqtt**
   https://github.com/victronenergy/dbus-mqtt
   MQTT bridge implementation

8. **dbus-spy**
   https://github.com/victronenergy/dbus-spy
   Interactive D-Bus browser

9. **venus**
   https://github.com/victronenergy/venus
   Venus OS meta repository and documentation

### Example Drivers

10. **dbus-fronius**
    https://github.com/victronenergy/dbus-fronius
    Fronius inverter integration

11. **dbus-fronius-smartmeter**
    https://github.com/RalfZim/venus.dbus-fronius-smartmeter
    Community: Fronius smart meter (good example structure)

12. **dbus-serialbattery**
    https://github.com/mr-manuel/venus-os_dbus-serialbattery
    Community: Serial battery driver (comprehensive example)

### Modbus Alternative

13. **Modbus TCP Documentation**
    https://www.victronenergy.com/live/ccgx:modbustcp_faq
    For non-D-Bus applications

14. **Modbus Register Excel**
    https://www.victronenergy.com/upload/documents/Modbus-TCP-register-list-2.90.xlsx
    Complete register mapping

---

## Community Resources

### Forums

1. **Victron Community**
   https://community.victronenergy.com/
   Official community forum

2. **Modifications Space**
   https://community.victronenergy.com/spaces/31/modifications.html
   Community modifications and custom integrations

### Community Archives

3. **Old Community Archive**
   https://communityarchive.victronenergy.com/
   Archived Q&A (searchable)

### Third-Party Integrations

4. **Home Assistant Integration**
   https://github.com/keshavdv/victron-ble
   Bluetooth integration examples

5. **Node-RED Flows**
   https://flows.nodered.org/search?term=victron
   Node-RED integration examples

### Blogs and Tutorials

6. **Ryan Britton's Dashboard**
   https://ryanbritton.com/2018/12/victron-system-data-collection-dashboard/
   Real-world D-Bus integration example

7. **Venus OS Large Image**
   https://www.victronenergy.com/live/venus-os:large
   For development on x86 machines

---

## Development Workflow

### 1. Local Development

For development and testing outside Venus OS:

**Venus OS Large** (x86/x64):
```bash
# Download Venus OS Large image
wget https://downloads.victronenergy.com/...

# Run in VirtualBox or QEMU
# Includes full Venus OS stack with D-Bus
```

**Reference**: https://www.victronenergy.com/live/venus-os:large

### 2. Install on Venus OS

**Via SSH**:
```bash
# Connect
ssh root@<venus-ip>

# Create directory
mkdir -p /data/my-service

# Upload files (from local machine)
scp -r my-service/ root@<venus-ip>:/data/

# Set permissions
chmod +x /data/my-service/service/run

# Create service symlink
ln -s /data/my-service/service /service/my-service

# Add to rc.local for persistence
echo "ln -s /data/my-service/service /service/my-service" >> /data/rc.local
```

### 3. Service Management

**Check status**:
```bash
svstat /service/my-service
```

**Restart**:
```bash
svc -t /service/my-service
```

**Stop**:
```bash
svc -d /service/my-service
```

**Start**:
```bash
svc -u /service/my-service
```

**View logs**:
```bash
tail -f /var/log/messages | grep my-service
```

### 4. Package Installation

Venus OS uses opkg package manager:

```bash
# Update package list
opkg update

# Search for package
opkg find python3-*

# Install package
opkg install python3-requests

# List installed packages
opkg list-installed
```

**Note**: Packages are wiped on firmware update. Document dependencies.

---

## Troubleshooting

### D-Bus Not Responding

```bash
# Check if D-Bus is running
ps aux | grep dbus

# Restart D-Bus (use with caution)
/etc/init.d/dbus restart
```

### Service Not Appearing

```bash
# Check if service script is executable
ls -la /data/my-service/service/run

# Check supervise status
svstat /service/my-service

# Check for Python errors
tail -20 /var/log/messages
```

### Values Not Updating

```bash
# Monitor D-Bus traffic
dbus-monitor --system | grep -A5 solarcharger

# Check specific value repeatedly
watch -n 1 'dbus -y com.victronenergy.solarcharger.ttyUSB0 /Yield/Power GetValue'
```

### Network Issues

```bash
# Check connectivity
ping 8.8.8.8

# Check DNS
nslookup victronenergy.com

# Check firewall (if applicable)
iptables -L
```

---

## Appendix: Quick Command Reference

### Essential D-Bus Commands

```bash
# List all services
dbus -y

# List solar chargers
dbus -y | grep solarcharger

# Get device serial
dbus -y com.victronenergy.solarcharger.ttyUSB0 /Serial GetValue

# Get current power
dbus -y com.victronenergy.solarcharger.ttyUSB0 /Yield/Power GetValue

# Get formatted text
dbus -y com.victronenergy.solarcharger.ttyUSB0 /Yield/Power GetText

# Set custom name
dbus -y com.victronenergy.solarcharger.ttyUSB0 /CustomName SetValue "My Charger"

# Browse interactively
dbus-spy
```

### Essential System Commands

```bash
# Check Venus OS version
cat /opt/victronenergy/version

# View system logs
tail -f /var/log/messages

# List running services
ls -l /service/

# Check service status
svstat /service/*

# Restart service
svc -t /service/my-service

# Check network
ifconfig

# Check disk usage
df -h

# List installed packages
opkg list-installed
```

---

## Version History

- **v1.0** - October 30, 2025 - Initial comprehensive documentation

---

## License

This documentation is provided as-is for educational purposes.

Victron Energy documentation and software are subject to their respective licenses.

---

## Contributing

To update this document:

1. Verify information against official Victron sources
2. Test code examples on Venus OS hardware
3. Include reference links to official documentation
4. Update version history

**Maintainer**: Solar Backend Team
**Repository**: https://github.com/your-repo/dbus-victron-http-bridge
