#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

# Ensure that i2c and spi are enabled.
# But still use our usual boot config, which has essential changes to i2c.
on_chroot << EOF
        cp /boot/firmware/config.txt /boot/firmware/temp
	SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_i2c 0
        SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_spi 0
        SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_serial_hw 0
        SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_serial_cons 1
        cp /boot/firmware/temp /boot/firmware/config.txt
        rm /boot/firmware/temp
EOF

# Install SimpleAQ requirements.
on_chroot << EOF
        pip install --break-system-packages -r /simpleaq/requirements.txt
EOF

# Set up a system-scoped systemd service.
# This is actually necessary because user-scoped services will not actually
# run until the user first logs in, and by default will terminate when the
# user logs out.  We obviously cannot rely on FIRST_USER_NAME ever logging
# in for most users.
# https://github.com/torfsen/python-systemd-tutorial is awesome.
cp files/simpleaq.service "${ROOTFS_DIR}/etc/systemd/system"
cp files/hostap_config.service "${ROOTFS_DIR}/etc/systemd/system"
cp files/ap0-setup.service "${ROOTFS_DIR}/etc/systemd/system"
cp files/wifi.nmconnection "${ROOTFS_DIR}/etc/NetworkManager/system-connections/"
cp files/NetworkManager.conf "${ROOTFS_DIR}/etc/NetworkManager/NetworkManager.conf"

# SimpleAQ uses python-dotenv.
# We will set the environment variables for SimpleAQ at the system level.
on_chroot << EOF
        cat /simpleaq/example.env >> /etc/environment
EOF

# Make sure our service has the right permissions and that it starts on boot.
on_chroot << EOF
        chown root:root /etc/systemd/system/simpleaq.service
        chmod 644 /etc/systemd/system/simpleaq.service
        systemctl enable simpleaq

        chown root:root /etc/systemd/system/hostap_config.service
        chmod 644 /etc/systemd/system/hostap_config.service
        systemctl enable hostap_config

        chown root:root /etc/systemd/system/ap0-setup.service
        chmod 644 /etc/systemd/system/ap0-setup.service
        systemctl enable ap0-setup

        chown root:root /etc/NetworkManager/system-connections/wifi.nmconnection
        chmod 600 /etc/NetworkManager/system-connections/wifi.nmconnection
EOF

# Delete now-unnecessary custom pigen stuff.
on_chroot << EOF
        rm -rf /simpleaq/custom_pigen
EOF

cp files/dnsmasq.conf            "${ROOTFS_DIR}/etc/dnsmasq.conf"

# Copy hostapd.conf in
cp files/hostapd.conf "${ROOTFS_DIR}/etc/hostapd/hostapd.conf"
cp files/hostapd "${ROOTFS_DIR}/etc/default/hostapd"

# The hostap no longer conflicts with the wlan0 service.
on_chroot << EOF
        systemctl enable hostapd 
        systemctl start hostapd 
EOF

cp files/gpsd "${ROOTFS_DIR}/etc/default/gpsd"

# Also enable gpsd
on_chroot << EOF
        systemctl enable gpsd
        adduser gpsd dialout
        adduser gpsd tty
EOF

# Add AP setup endpoint to /etc/hosts
on_chroot << EOF
         echo "" >> /etc/hosts
         echo "192.168.4.1             simpleaq.setup" >> /etc/hosts
EOF

# Don't let logs get too big.
on_chroot << EOF
        sed -i '/SystemMaxUse/c\SystemMaxUse=10M' /etc/systemd/journald.conf
EOF

# Choose a better HostAP name than just "SimpleAQ" if nothing else is provided. 
# This file also has firewall safeguards.
cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"

# Disable firewall safeguards for debug builds.
if [ ${ENABLE_SSH} -eq 1 ]
then
        cp files/rc.local.debug "${ROOTFS_DIR}/etc/rc.local"
fi

on_chroot << EOF
        chown root:root /etc/rc.local
        chmod a+x /etc/rc.local
EOF


