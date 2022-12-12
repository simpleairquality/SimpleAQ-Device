#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

# Install SimpleAQ requirements.
on_chroot << EOF
        pip install -r /simpleaq/requirements.txt
EOF

# Also install Waveshare.
# This is an absolute hack.
# It doetects the build environment as Jetson, not RPi, and we must remove that library after.
# TODO:  Remove it:  https://github.com/yskoht/waveshare-epaper/issues/1
on_chroot << EOF
        pip install git+https://github.com/waveshare/e-Paper#egg=waveshare-epd\&subdirectory=RaspberryPi_JetsonNano/python
        pip uninstall Jetson.GPIO 
EOF

# Set up a system-scoped systemd service.
# This is actually necessary because user-scoped services will not actually
# run until the user first logs in, and by default will terminate when the
# user logs out.  We obviously cannot rely on FIRST_USER_NAME ever logging
# in for most users.
# https://github.com/torfsen/python-systemd-tutorial is awesome.
cp files/simpleaq.service "${ROOTFS_DIR}/etc/systemd/system"
cp files/hostap_config.service "${ROOTFS_DIR}/etc/systemd/system"

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
        systemctl enable systemd-resolved.service
        systemctl start systemd-networkd.service
        systemctl start systemd-resolved.service
        ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
EOF

# The wifi client must be on wlan0.
on_chroot << EOF
        mv /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant-wlan0.conf
        systemctl disable wpa_supplicant.service
        systemctl enable wpa_supplicant@wlan0.service
        systemctl start wpa_supplicant@wlan0.service
EOF

cp files/08-wlan0.network "${ROOTFS_DIR}/etc/systemd/network"

# The hostap is on ap0.
cp files/wpa_supplicant-ap0.conf "${ROOTFS_DIR}/etc/wpa_supplicant/wpa_supplicant-ap0.conf"
cp files/12-ap0.network          "${ROOTFS_DIR}/etc/systemd/network"
cp files/resolved.conf           "${ROOTFS_DIR}/etc/systemd/resolved.conf"
cp files/dnsmasq.conf            "${ROOTFS_DIR}/etc/dnsmasq.conf"

# The hostap starts "off".  We'll switch it on if needed.
on_chroot << EOF
        systemctl disable wpa_supplicant@ap0.service
EOF

# Custom service that allows us to switch between hostap and wifi mode.
cp files/wpa_supplicant@ap0.service "${ROOTFS_DIR}/etc/systemd/system"

# Choose a better HostAP name than just "SimpleAQ" if nothing else is provided. 
cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"

# Add AP setup endpoint to /etc/hosts
on_chroot << EOF
         echo "" >> /etc/hosts
         echo "192.168.4.1             simpleaq.setup" >> /etc/hosts
EOF

# Don't let logs get too big.
on_chroot << EOF
         journalctl --vacuum-size=1G
EOF
