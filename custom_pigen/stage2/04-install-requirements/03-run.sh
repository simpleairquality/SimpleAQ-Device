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
        systemctl disable hostapd.service
EOF

# Following instructions at:
# https://raspberrypi.stackexchange.com/questions/93311/switch-between-wifi-client-and-access-point-without-reboot

# Disable Debian networking and dhcpcd
on_chroot << EOF
        systemctl mask networking.service dhcpcd.service
        mv /etc/network/interfaces /etc/network/interfaces-
        sed -i '1i resolvconf=NO' /etc/resolvconf.conf
EOF

# Enable systemd-networkd
on_chroot << EOF
        systemctl enable systemd-networkd.service
        systemctl enable systemd-resolved.conf
        ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
EOF

# The wifi client must be on wlan0.
on_chroot << EOF
        mv /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
        systemctl disable wpa_supplicant.service
        systemctl enable wpa_supplicant@wlan0.service
EOF

cp files/08-wlan0.network "${ROOTFS_DIR}/etc/systemd/network"

# The hostap is on ap0.
cp files/wpa_supplicant-ap0.conf "${ROOTFS_DIR}/etc/wpa_supplicant/wpa_supplicant-ap0.conf"
cp files/12-ap0.network   "${ROOTFS_DIR}/etc/systemd/network"

# The hostap starts "off".  We'll switch it on if needed.
on_chroot << EOF
        systemctl disable wpa_supplicant@ap0.service
EOF

# TODO:  Need to figure out how to set up wpa_supplicant@ap0.service appropriately.
#        This will be easier to do once we've got an otherwise valid file to look at and play with.

# TODO:  Re-add this using the wpa_supplicant hostap instead of hostapd
# cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"
