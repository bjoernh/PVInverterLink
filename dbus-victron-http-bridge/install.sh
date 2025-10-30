#!/bin/bash
#
# Installation script for Victron Venus OS HTTP Bridge
#
# This script:
# 1. Checks prerequisites
# 2. Copies files to /data/dbus-victron-http-bridge/
# 3. Downloads velib_python if needed
# 4. Sets up the service with daemontools
# 5. Configures boot persistence
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/data/dbus-victron-http-bridge"
SERVICE_NAME="dbus-victron-http-bridge"

echo "========================================="
echo "Victron Venus OS HTTP Bridge Installer"
echo "========================================="
echo ""

# Check if running on Venus OS
if [ ! -d "/opt/victronenergy" ]; then
    echo "WARNING: This doesn't appear to be a Venus OS system"
    echo "/opt/victronenergy directory not found"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check prerequisites
echo "Checking prerequisites..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed"
    exit 1
fi
echo "✓ Python 3 found"

# Check for required Python modules
python3 -c "import dbus" 2>/dev/null || {
    echo "ERROR: python3-dbus is not installed"
    echo "Install with: opkg update && opkg install python3-dbus"
    exit 1
}
echo "✓ python3-dbus found"

python3 -c "from gi.repository import GLib" 2>/dev/null || {
    echo "ERROR: python3-gi is not installed"
    echo "Install with: opkg update && opkg install python3-gi"
    exit 1
}
echo "✓ python3-gi found"

python3 -c "import requests" 2>/dev/null || {
    echo "ERROR: python3-requests is not installed"
    echo "Install with: opkg update && opkg install python3-requests"
    exit 1
}
echo "✓ python3-requests found"

echo ""
echo "Installing to ${INSTALL_DIR}..."

# Create installation directory
mkdir -p "${INSTALL_DIR}/ext"
mkdir -p "${INSTALL_DIR}/service"

# Copy files
echo "Copying files..."
cp "${SCRIPT_DIR}/dbus-victron-http-bridge.py" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/service/run" "${INSTALL_DIR}/service/"

# Copy config if it doesn't exist
if [ ! -f "${INSTALL_DIR}/config.ini" ]; then
    if [ -f "${SCRIPT_DIR}/config.ini" ]; then
        cp "${SCRIPT_DIR}/config.ini" "${INSTALL_DIR}/"
        echo "✓ Copied config.ini"
    elif [ -f "${SCRIPT_DIR}/config.ini.example" ]; then
        cp "${SCRIPT_DIR}/config.ini.example" "${INSTALL_DIR}/config.ini"
        echo "✓ Copied config.ini.example to config.ini"
        echo ""
        echo "⚠️  IMPORTANT: Edit ${INSTALL_DIR}/config.ini with your settings!"
        echo ""
    else
        echo "WARNING: No config file found. Please create ${INSTALL_DIR}/config.ini"
    fi
else
    echo "✓ config.ini already exists (not overwriting)"
fi

# Set executable permissions
chmod +x "${INSTALL_DIR}/dbus-victron-http-bridge.py"
chmod +x "${INSTALL_DIR}/service/run"

# Download velib_python if not present
if [ ! -d "${INSTALL_DIR}/ext/velib_python" ]; then
    echo ""
    echo "Downloading velib_python..."

    if command -v git &> /dev/null; then
        cd "${INSTALL_DIR}/ext"
        git clone https://github.com/victronenergy/velib_python.git
        echo "✓ velib_python downloaded"
    else
        echo "WARNING: git not found. velib_python not downloaded."
        echo "The script will try to use the system-installed velib_python at:"
        echo "  /opt/victronenergy/dbus-systemcalc-py/ext/velib_python"
    fi
else
    echo "✓ velib_python already present"
fi

# Set up service with daemontools
echo ""
echo "Setting up service..."

# Create service symlink
if [ ! -L "/service/${SERVICE_NAME}" ]; then
    ln -s "${INSTALL_DIR}/service" "/service/${SERVICE_NAME}"
    echo "✓ Service symlink created"
else
    echo "✓ Service symlink already exists"
fi

# Add to rc.local for boot persistence
RC_LOCAL="/data/rc.local"
RC_ENTRY="ln -s ${INSTALL_DIR}/service /service/${SERVICE_NAME}"

if [ ! -f "${RC_LOCAL}" ]; then
    echo "#!/bin/bash" > "${RC_LOCAL}"
    chmod +x "${RC_LOCAL}"
fi

if ! grep -qF "${RC_ENTRY}" "${RC_LOCAL}"; then
    echo "${RC_ENTRY}" >> "${RC_LOCAL}"
    echo "✓ Added to ${RC_LOCAL}"
else
    echo "✓ Already in ${RC_LOCAL}"
fi

echo ""
echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit your configuration:"
echo "   vi ${INSTALL_DIR}/config.ini"
echo ""
echo "2. Set your backend URL and API key"
echo ""
echo "3. Get your Cerbo GX serial number:"
echo "   dbus -y com.victronenergy.system /Serial GetValue"
echo ""
echo "4. In your backend, create inverter(s) with serial_logger:"
echo "   Format: <cerbo_serial>_<device_instance>"
echo "   Example: HQ2345ABCDE_0"
echo ""
echo "5. The service will start automatically within seconds"
echo ""
echo "Check service status:"
echo "   svstat /service/${SERVICE_NAME}"
echo ""
echo "View logs:"
echo "   tail -f /var/log/messages | grep victron-http-bridge"
echo ""
echo "Restart service:"
echo "   svc -t /service/${SERVICE_NAME}"
echo ""
echo "Stop service:"
echo "   svc -d /service/${SERVICE_NAME}"
echo ""
