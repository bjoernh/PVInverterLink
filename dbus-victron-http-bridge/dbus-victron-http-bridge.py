#!/usr/bin/env python3
"""
Victron Venus OS D-Bus to HTTP Bridge

This script runs on Victron Venus OS (Cerbo GX, etc.) and:
1. Monitors all connected solar chargers via D-Bus
2. Collects measurement data (power, voltage, yield, per-tracker data)
3. Posts the data to a remote HTTP endpoint every N seconds

Installation:
    Place in /data/dbus-victron-http-bridge/
    Configure config.ini with your backend URL and API key
    Run install.sh to set up as a service

Author: Solar Backend Team
License: MIT
"""

import sys
import os
import time
import json
import logging
import logging.handlers
import configparser
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# Add velib_python to path (standard location on Venus OS)
sys.path.insert(1, os.path.join(os.path.dirname(__file__), "ext", "velib_python"))
sys.path.insert(1, "/opt/victronenergy/dbus-systemcalc-py/ext/velib_python")

try:
    import requests
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    import dbus
except ImportError as e:
    print(f"ERROR: Missing required dependency: {e}")
    print("This script requires: python3-dbus, python3-gi, python3-requests")
    sys.exit(1)

try:
    from dbusmonitor import DbusMonitor
except ImportError:
    print("ERROR: Could not import dbusmonitor from velib_python")
    print("Make sure velib_python is available in ext/velib_python/ or at the Venus OS standard location")
    sys.exit(1)


# Constants
CONFIG_FILE = "config.ini"
DEFAULT_UPDATE_INTERVAL = 30  # seconds
DEFAULT_TIMEOUT = 10  # seconds for HTTP requests


class VictronBridge:
    """Bridge between Victron Venus OS D-Bus and HTTP backend."""

    def __init__(self, config_path: str):
        """Initialize the bridge with configuration."""
        self.config = self._load_config(config_path)
        self.logger = self._setup_logging()
        self.dbusmonitor = None
        self.mainloop = None
        self.last_post_time = 0

        self.logger.info("Victron HTTP Bridge starting")
        self.logger.info(f"Backend URL: {self.config['backend']['url']}")
        self.logger.info(f"Update interval: {self.config['device']['update_interval']}s")

    def _load_config(self, config_path: str) -> Dict[str, Dict[str, Any]]:
        """Load configuration from INI file."""
        if not os.path.exists(config_path):
            print(f"ERROR: Config file not found: {config_path}")
            print("Please create config.ini with your settings")
            sys.exit(1)

        parser = configparser.ConfigParser()
        parser.read(config_path)

        config = {
            "backend": {
                "url": parser.get("backend", "url"),
                "api_key": parser.get("backend", "api_key"),
                "timeout": parser.getint("backend", "timeout", fallback=DEFAULT_TIMEOUT),
            },
            "device": {
                "cerbo_serial": parser.get("device", "cerbo_serial"),
                "update_interval": parser.getint("device", "update_interval", fallback=DEFAULT_UPDATE_INTERVAL),
            },
            "logging": {
                "level": parser.get("logging", "level", fallback="INFO"),
            },
        }

        return config

    def _setup_logging(self) -> logging.Logger:
        """Configure logging to syslog (Venus OS standard)."""
        logger = logging.getLogger("victron-http-bridge")
        logger.setLevel(getattr(logging, self.config["logging"]["level"]))

        # Log to syslog (Venus OS standard)
        syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
        syslog_formatter = logging.Formatter(
            "victron-http-bridge[%(process)d]: %(levelname)s - %(message)s"
        )
        syslog_handler.setFormatter(syslog_formatter)
        logger.addHandler(syslog_handler)

        # Also log to console for debugging
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def _get_dbus_value(self, service: str, path: str, default: Any = None) -> Any:
        """Safely get a value from D-Bus, returning default if not available."""
        try:
            value = self.dbusmonitor.get_value(service, path)
            return value if value is not None else default
        except Exception as e:
            self.logger.debug(f"Could not read {service}{path}: {e}")
            return default

    def _read_device_data(self, service: str) -> Optional[Dict[str, Any]]:
        """Read all relevant data for a single solar charger device."""
        try:
            # Get device metadata
            device_instance = self._get_dbus_value(service, "/DeviceInstance")
            if device_instance is None:
                self.logger.warning(f"No DeviceInstance for {service}, skipping")
                return None

            serial = self._get_dbus_value(service, "/Serial", "UNKNOWN")
            custom_name = self._get_dbus_value(service, "/CustomName")
            product_name = self._get_dbus_value(service, "/ProductName", "Unknown Product")

            # Use custom name if available, otherwise product name
            name = custom_name if custom_name else product_name

            # Get operational status
            # State: 0=Off, 2=Fault, 3=Bulk, 4=Absorption, 5=Float
            state = self._get_dbus_value(service, "/State", 0)
            reachable = True  # If we can read from D-Bus, it's reachable
            producing = state in [3, 4, 5]  # Bulk, Absorption, or Float means producing

            # Get timestamp (use current time as Venus OS doesn't provide measurement timestamp)
            last_update = int(time.time())

            # Get yield data
            yield_power_w = self._get_dbus_value(service, "/Yield/Power", 0.0)
            yield_total_kwh = self._get_dbus_value(service, "/Yield/System", 0.0)

            # Get tracker data
            nr_of_trackers = self._get_dbus_value(service, "/NrOfTrackers", 1)
            trackers = []

            if nr_of_trackers == 1:
                # Single tracker - use /Pv/V and calculated power
                voltage = self._get_dbus_value(service, "/Pv/V", 0.0)
                # For single tracker, power equals yield power
                power = yield_power_w

                if voltage is not None and voltage > 0:
                    trackers.append({
                        "tracker": 0,
                        "name": "PV",
                        "voltage": float(voltage),
                        "power": float(power),
                    })
            else:
                # Multi-tracker - read each tracker
                for i in range(nr_of_trackers):
                    voltage = self._get_dbus_value(service, f"/Pv/{i}/V", 0.0)
                    power = self._get_dbus_value(service, f"/Pv/{i}/P", 0.0)

                    if voltage is not None and voltage > 0:
                        trackers.append({
                            "tracker": i,
                            "name": f"PV-{i+1}",
                            "voltage": float(voltage),
                            "power": float(power),
                        })

            device_data = {
                "device_instance": int(device_instance),
                "serial": str(serial),
                "name": str(name),
                "product_name": str(product_name),
                "reachable": reachable,
                "producing": producing,
                "last_update": last_update,
                "yield_power_w": float(yield_power_w),
                "yield_total_kwh": float(yield_total_kwh),
                "trackers": trackers,
            }

            return device_data

        except Exception as e:
            self.logger.error(f"Error reading device data from {service}: {e}")
            return None

    def _collect_measurements(self) -> Optional[Dict[str, Any]]:
        """Collect measurements from all solar chargers."""
        try:
            # Get all solar charger services
            services = self.dbusmonitor.get_service_list("com.victronenergy.solarcharger")

            if not services:
                self.logger.debug("No solar chargers found on D-Bus")
                return None

            devices = []
            for service in services:
                self.logger.debug(f"Reading data from {service}")
                device_data = self._read_device_data(service)
                if device_data:
                    devices.append(device_data)

            if not devices:
                self.logger.warning("No valid device data collected")
                return None

            # Build payload
            payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cerbo_serial": self.config["device"]["cerbo_serial"],
                "devices": devices,
            }

            return payload

        except Exception as e:
            self.logger.error(f"Error collecting measurements: {e}")
            return None

    def _post_measurements(self, payload: Dict[str, Any]) -> bool:
        """Post measurements to HTTP backend."""
        try:
            url = f"{self.config['backend']['url']}/api/victron/measurements"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.config["backend"]["api_key"],
            }

            self.logger.debug(f"Posting to {url}")
            self.logger.debug(f"Payload: {json.dumps(payload, indent=2)}")

            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=self.config["backend"]["timeout"],
            )

            if response.status_code in [201, 207]:
                # 201 = all success, 207 = partial success
                result = response.json()
                self.logger.info(
                    f"Posted measurements: {result['success_count']} success, "
                    f"{result['error_count']} errors"
                )
                if result['error_count'] > 0:
                    self.logger.warning(f"Errors in response: {result.get('results', [])}")
                return True
            elif response.status_code == 404:
                # All devices not found
                self.logger.error("All devices not found in backend database")
                self.logger.error("Make sure devices are registered with correct serial_logger format:")
                self.logger.error(f"  {self.config['device']['cerbo_serial']}_<device_instance>")
                return False
            elif response.status_code == 401:
                self.logger.error("Authentication failed - check API key in config.ini")
                return False
            else:
                self.logger.error(f"HTTP error {response.status_code}: {response.text}")
                return False

        except requests.exceptions.Timeout:
            self.logger.error("HTTP request timed out")
            return False
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error posting measurements: {e}")
            return False

    def _update_callback(self) -> bool:
        """Periodic callback to collect and post measurements."""
        current_time = time.time()

        # Check if it's time to post
        if current_time - self.last_post_time < self.config["device"]["update_interval"]:
            return True  # Continue timer

        self.logger.debug("Collecting measurements")
        payload = self._collect_measurements()

        if payload:
            self._post_measurements(payload)
        else:
            self.logger.debug("No measurements to post")

        self.last_post_time = current_time
        return True  # Continue timer

    def run(self):
        """Start the bridge main loop."""
        try:
            # Initialize D-Bus
            DBusGMainLoop(set_as_default=True)

            # Set up D-Bus monitor for solar chargers
            dummy = {"code": None, "whenToLog": "configChange", "accessLevel": None}
            dbus_tree = {
                "com.victronenergy.solarcharger": {
                    "/DeviceInstance": dummy,
                    "/Serial": dummy,
                    "/CustomName": dummy,
                    "/ProductName": dummy,
                    "/State": dummy,
                    "/Yield/Power": dummy,
                    "/Yield/System": dummy,
                    "/NrOfTrackers": dummy,
                    "/Pv/V": dummy,  # Single tracker voltage
                    "/Pv/0/V": dummy,  # Multi-tracker voltage
                    "/Pv/0/P": dummy,  # Multi-tracker power
                    "/Pv/1/V": dummy,
                    "/Pv/1/P": dummy,
                    "/Pv/2/V": dummy,
                    "/Pv/2/P": dummy,
                    "/Pv/3/V": dummy,
                    "/Pv/3/P": dummy,
                },
            }

            self.dbusmonitor = DbusMonitor(
                dbus_tree,
                deviceAddedCallback=self._device_added,
                deviceRemovedCallback=self._device_removed,
            )

            self.logger.info("D-Bus monitor initialized")

            # Set up periodic update timer
            GLib.timeout_add_seconds(5, self._update_callback)  # Check every 5 seconds

            # Run main loop
            self.mainloop = GLib.MainLoop()
            self.logger.info("Starting main loop")
            self.mainloop.run()

        except KeyboardInterrupt:
            self.logger.info("Received interrupt, shutting down")
            self.stop()
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}", exc_info=True)
            sys.exit(1)

    def _device_added(self, service, instance):
        """Callback when a device is added to D-Bus."""
        self.logger.info(f"Device added: {service} (instance {instance})")

    def _device_removed(self, service, instance):
        """Callback when a device is removed from D-Bus."""
        self.logger.info(f"Device removed: {service} (instance {instance})")

    def stop(self):
        """Stop the bridge main loop."""
        if self.mainloop:
            self.logger.info("Stopping main loop")
            self.mainloop.quit()


def main():
    """Main entry point."""
    # Check if running on Venus OS
    if not os.path.exists("/opt/victronenergy"):
        print("WARNING: This script is designed to run on Victron Venus OS")
        print("Continuing anyway for testing purposes...")

    # Load config and start bridge
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, CONFIG_FILE)

    bridge = VictronBridge(config_path)
    bridge.run()


if __name__ == "__main__":
    main()
