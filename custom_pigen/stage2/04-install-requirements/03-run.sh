#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

# Enable resize2fs, which apparently isn't executing now?
on_chroot << EOF
        systemctl enable resize2fs_once
EOF

# Ensure that i2c and spi are enabled.
# But still use our usual boot config, which has essential changes to i2c.
on_chroot << EOF
        cp /boot/firmware/config.txt /boot/firmware/temp
	SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_i2c 0
        SUDO_USER="${FIRST_USER_NAME}" raspi-config nonint do_spi 0
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
cp files/dnsmasq.service "${ROOTFS_DIR}/etc/systemd/system"
cp files/uap0.service "${ROOTFS_DIR}/etc/systemd/system"

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

        chown root:root /etc/systemd/system/uap0.service
        chmod 644 /etc/systemd/system/uap0.service
        systemctl enable uap0
EOF

# Delete now-unnecessary custom pigen stuff.
on_chroot << EOF
        rm -rf /simpleaq/custom_pigen
EOF

# Copy dnsmasq.conf over.
cp files/dnsmasq.conf            "${ROOTFS_DIR}/etc/dnsmasq.conf"

# Choose a better HostAP name than just "SimpleAQ" if nothing else is provided. 
# This file also has firewall safeguards.
cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"

# Add AP information to dhcpcd.conf
on_chroot << EOF
        echo "interface uap0" >> /etc/dhcpcd.conf
        echo "static ip_address=192.168.4.1/24" >> /etc/dhcpcd.conf
        echo "nohook wpa_supplicant" >> dhcpcd.conf
EOF

# Add AP setup endpoint to /etc/hosts
on_chroot << EOF
         echo "" >> /etc/hosts
         echo "192.168.4.1             simpleaq.setup" >> /etc/hosts
EOF

# Setup hostapd
on_chroot << EOF
         echo "interface=uap0"          >> /etc/hostapd/hostapd.conf
         echo "ssid=SimpleAQ"           >> /etc/hostapd/hostapd.conf
         echo "hw_mode=g"               >> /etc/hostapd/hostapd.conf
         echo "channel=4"               >> /etc/hostapd/hostapd.conf
         echo "wmm_enabled=0"           >> /etc/hostapd/hostapd.conf
         echo "macaddr_acl=0"           >> /etc/hostapd/hostapd.conf
         echo "auth_algs=1"             >> /etc/hostapd/hostapd.conf
         echo "ignore_broadcast_ssid=0" >> /etc/hostapd/hostapd.conf
         echo "wpa=2"                   >> /etc/hostapd/hostapd.conf
         echo "wpa_passphrase=SimpleAQ" >> /etc/hostapd/hostapd.conf

         sed -i 's|^DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|' /etc/default/hostapd

         systemctl enable hostapd
         systemctl enable dnsmasq
EOF

# Don't let logs get too big.
on_chroot << EOF
         sed -i '/SystemMaxUse/c\SystemMaxUse=10M' /etc/systemd/journald.conf
EOF

# Don't block wifi.
on_chroot << EOF
	rfkill unblock wifi
EOF

# Disable firewall safeguards for debug builds.
if [ ${ENABLE_SSH} -eq 1 ]
then
  cp files/rc.local.debug "${ROOTFS_DIR}/etc/rc.local"
fi 
