#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"[cite: 4]

# Install SimpleAQ requirements.
# We force the upgrade to break system packages if needed.
on_chroot << EOF
    export PIP_BREAK_SYSTEM_PACKAGES=1

    python3 -m pip install --upgrade pip
    python3 -m pip install -r /simpleaq/requirements.txt
    
    # --- Install bluez-tools for the background BT agent ---
    apt-get update
    apt-get install -y bluez-tools
EOF

# Load i2c module at runtime.
echo i2c-dev >> "${ROOTFS_DIR}/etc/modules"[cite: 4]

# Set up a system-scoped systemd service.
# This is actually necessary because user-scoped services will not actually
# run until the user first logs in, and by default will terminate when the
# user logs out.  We obviously cannot rely on FIRST_USER_NAME ever logging
# in for most users.
# https://github.com/torfsen/python-systemd-tutorial is awesome.
cp files/simpleaq.service "${ROOTFS_DIR}/etc/systemd/system"[cite: 4]
cp files/hostap_config.service "${ROOTFS_DIR}/etc/systemd/system"[cite: 4]
cp files/wifi.nmconnection "${ROOTFS_DIR}/etc/NetworkManager/system-connections/"[cite: 4]
cp files/NetworkManager.conf "${ROOTFS_DIR}/etc/NetworkManager/NetworkManager.conf"[cite: 4]
cp files/chrony.conf "${ROOTFS_DIR}/etc/chrony/chrony.conf"[cite: 4]
cp files/simpleaq-ap.nmconnection "${ROOTFS_DIR}/etc/NetworkManager/system-connections/"[cite: 4]
cp files/ap0-setup.service "${ROOTFS_DIR}/etc/systemd/system"[cite: 4]
cp files/wifi-watchdog.sh "${ROOTFS_DIR}/usr/local/bin/wifi-watchdog.sh"[cite: 4]
cp files/wifi-watchdog.service "${ROOTFS_DIR}/etc/systemd/system"[cite: 4]
cp files/wifi-watchdog.timer "${ROOTFS_DIR}/etc/systemd/system"[cite: 4]
mkdir -p "${ROOTFS_DIR}/etc/NetworkManager/dispatcher.d"[cite: 4]
cp files/90-simpleaq-ap-channel "${ROOTFS_DIR}/etc/NetworkManager/dispatcher.d/90-simpleaq-ap-channel"[cite: 4]

# --- Copy BLE, Reset scripts, and BT Agent services ---
cp files/simpleaq-ble.service "${ROOTFS_DIR}/etc/systemd/system/"[cite: 4]
cp files/ble_setup.py "${ROOTFS_DIR}/usr/local/bin/"[cite: 4]
cp files/simpleaq-reset.service "${ROOTFS_DIR}/etc/systemd/system/"[cite: 4]
cp files/reset_server.py "${ROOTFS_DIR}/usr/local/bin/"[cite: 4]
cp files/simpleaq-bt-agent.service "${ROOTFS_DIR}/etc/systemd/system/"

# SimpleAQ uses python-dotenv.
# We will set the environment variables for SimpleAQ at the system level.
on_chroot << EOF
        cat /simpleaq/example.env | grep -v "image_name=" >> /etc/environment[cite: 4]
        echo image_name=${IMG_NAME} >> /etc/environment[cite: 4]
EOF

# Make sure our services have the right permissions and start on boot.
on_chroot << EOF
        chown root:root /etc/systemd/system/simpleaq.service[cite: 4]
        chmod 644 /etc/systemd/system/simpleaq.service[cite: 4]
        systemctl enable simpleaq[cite: 4]

        chown root:root /etc/systemd/system/ap0-setup.service[cite: 4]
        chmod 644 /etc/systemd/system/ap0-setup.service[cite: 4]
        # Disabled to prioritize BLE setup
        # systemctl enable ap0-setup[cite: 4]

        chown root:root /etc/systemd/system/hostap_config.service[cite: 4]
        chmod 644 /etc/systemd/system/hostap_config.service[cite: 4]
        # Disabled to prioritize BLE setup
        # systemctl enable hostap_config[cite: 4]

        chown root:root /usr/local/bin/wifi-watchdog.sh[cite: 4]
        chmod 755 /usr/local/bin/wifi-watchdog.sh[cite: 4]
        chown root:root /etc/systemd/system/wifi-watchdog.service[cite: 4]
        chmod 644 /etc/systemd/system/wifi-watchdog.service[cite: 4]
        chown root:root /etc/systemd/system/wifi-watchdog.timer[cite: 4]
        chmod 644 /etc/systemd/system/wifi-watchdog.timer[cite: 4]
        # Disabled to prioritize BLE setup
        # systemctl enable wifi-watchdog.timer[cite: 4]

        # Ensure bluetooth radio is not soft-blocked on first boot
        rfkill unblock bluetooth || true[cite: 4]

        # BLE Provisioning Service
        chown root:root /etc/systemd/system/simpleaq-ble.service[cite: 4]
        chmod 644 /etc/systemd/system/simpleaq-ble.service[cite: 4]
        systemctl enable simpleaq-ble.service[cite: 4]
        
        chown root:root /usr/local/bin/ble_setup.py[cite: 4]
        chmod 755 /usr/local/bin/ble_setup.py[cite: 4]

        # Local Reset Web Server
        chown root:root /etc/systemd/system/simpleaq-reset.service[cite: 4]
        chmod 644 /etc/systemd/system/simpleaq-reset.service[cite: 4]
        systemctl enable simpleaq-reset.service[cite: 4]

        chown root:root /usr/local/bin/reset_server.py[cite: 4]
        chmod 755 /usr/local/bin/reset_server.py[cite: 4]

        # Enable the BT Agent Service
        chown root:root /etc/systemd/system/simpleaq-bt-agent.service
        chmod 644 /etc/systemd/system/simpleaq-bt-agent.service
        systemctl enable simpleaq-bt-agent.service

        chown root:root /etc/NetworkManager/dispatcher.d/90-simpleaq-ap-channel[cite: 4]
        chmod 755 /etc/NetworkManager/dispatcher.d/90-simpleaq-ap-channel[cite: 4]

        chown root:root /etc/NetworkManager/system-connections/wifi.nmconnection[cite: 4]
        chmod 600 /etc/NetworkManager/system-connections/wifi.nmconnection[cite: 4]

        chown root:root /etc/NetworkManager/system-connections/simpleaq-ap.nmconnection[cite: 4]
        chmod 600 /etc/NetworkManager/system-connections/simpleaq-ap.nmconnection[cite: 4]
EOF

# Delete now-unnecessary custom pigen stuff.
on_chroot << EOF
        rm -rf /simpleaq/custom_pigen[cite: 4]
EOF

cp files/gpsd "${ROOTFS_DIR}/etc/default/gpsd"[cite: 4]

# Also enable gpsd
on_chroot << EOF
        systemctl enable gpsd[cite: 4]
        adduser gpsd dialout[cite: 4]
        adduser gpsd tty[cite: 4]
EOF

# Create NetworkManager dnsmasq shared directory
mkdir -p "${ROOTFS_DIR}/etc/NetworkManager/dnsmasq-shared.d"[cite: 4]

# Add custom DNS entry for simpleaq.setup
cat > "${ROOTFS_DIR}/etc/NetworkManager/dnsmasq-shared.d/simpleaq.conf" << 'EOF'[cite: 4]
# Resolve simpleaq.setup to the AP gateway
address=/simpleaq.setup/192.168.4.1[cite: 4]
EOF

# Set permissions
on_chroot << EOF
    chown root:root /etc/NetworkManager/dnsmasq-shared.d/simpleaq.conf[cite: 4]
    chmod 644 /etc/NetworkManager/dnsmasq-shared.d/simpleaq.conf[cite: 4]
EOF

# Don't let logs get too big.
on_chroot << EOF
        sed -i '/SystemMaxUse/c\SystemMaxUse=10M' /etc/systemd/journald.conf[cite: 4]
EOF

# Choose a better HostAP name than just "SimpleAQ" if nothing else is provided. 
# This file also has firewall safeguards.
cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"[cite: 4]

# Disable firewall safeguards for debug builds.
if [ ${ENABLE_SSH} -eq 1 ][cite: 4]
then
        cp files/rc.local.debug "${ROOTFS_DIR}/etc/rc.local"[cite: 4]
fi

on_chroot << EOF
        chown root:root /etc/rc.local[cite: 4]
        chmod a+x /etc/rc.local[cite: 4]
EOF

# Force BLE-only mode and enable PIN-less "Just Works" pairing
on_chroot << EOF
    # Insert configurations directly under the [General] header in main.conf
    sed -i '/^\[General\]/a ControllerMode = le\nJustWorksRepairing = always\nFastConnectable = true' /etc/bluetooth/main.conf[cite: 4]
EOF
