#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

# Install SimpleAQ requirements.
on_chroot << EOF
        pip install -r /simpleaq/requirements.txt
EOF

# Set up a system-scoped systemd service.
# This is actually necessary because user-scoped services will not actually
# run until the user first logs in, and by default will terminate when the
# user logs out.  We obviously cannot rely on FIRST_USER_NAME ever logging
# in for most users.
# https://github.com/torfsen/python-systemd-tutorial is awesome.
cp files/simpleaq.service "${ROOTFS_DIR}/etc/systemd/system"

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
EOF

# Delete now-unnecessary custom pigen stuff.
on_chroot << EOF
        rm -rf /simpleaq/custom_pigen
EOF

# Set up i2c and spi, required for our scripts.
on_chroot << EOF
	SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_i2c 0
        SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_spi 0
EOF

# Unmask hostapd, which will be useful for configuration.
# A script will be responsible for turning it on or off.
on_chroot << EOF
        systemctl unmask hostapd
EOF

cat files/dnsmasq-extra.conf >> "${ROOTFS_DIR}/etc/dnsmasq.conf"
cp files/hostapd.conf "${ROOTFS_DIR}/etc/hostapd/hostapd.conf"
cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"
