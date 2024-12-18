#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

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
cp files/ap0-setup.service "${ROOTFS_DIR}/etc/systemd/system"
cp files/ap0-hotspot.nmconnection "${ROOTFS_DIR}/etc/NetworkManager/system-connections/"
cp files/NetworkManager.conf "${ROOTFS_DIR}/etc/NetworkManager/NetworkManager.conf"

# Remove this later.
cp files/test_commands.sh "${ROOTFS_DIR}/"

# cp files/99-wlan0.rules "${ROOTFS_DIR}/etc/udev/rules.d"

# My belief is that this should be, or at least was, auto-generated.
# Now it's not anymore.  We copy it over.
# cp files/wpa_supplicant.conf "${ROOTFS_DIR}/etc/wpa_supplicant/wpa_supplicant.conf"

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

        chown root:root /etc/NetworkManager/system-connections/ap0-hotspot.nmconnection
        chmod 600 /etc/NetworkManager/system-connections/ap0-hotspot.nmconnection
EOF

# Delete now-unnecessary custom pigen stuff.
on_chroot << EOF
        rm -rf /simpleaq/custom_pigen
EOF


# Remove rfkill, as it seems to cause problems.  We don't want it anyway.
# on_chroot << EOF
#         apt-get remove -y rfkill
# EOF

# Following instructions at:
# https://raspberrypi.stackexchange.com/questions/93311/switch-between-wifi-client-and-access-point-without-reboot

# Ensure that systemd-resolved is configured properly.
# on_chroot << EOF
#        apt-get install -y systemd-resolved
#        rm /etc/resolv.conf 
#        ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
# EOF

# Enable systemd-networkd
# on_chroot << EOF
#         systemctl disable NetworkManager.service
#         systemctl enable systemd-networkd.service
#         systemctl enable systemd-resolved.service
#         systemctl start systemd-networkd.service
#         systemctl start systemd-resolved.service
#         ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
# EOF

# cp files/08-wlan0.network "${ROOTFS_DIR}/etc/systemd/network"

# The hostap is on ap0.
# cp files/12-ap0.network          "${ROOTFS_DIR}/etc/systemd/network"
# cp files/resolved.conf           "${ROOTFS_DIR}/etc/systemd/resolved.conf"
cp files/dnsmasq.conf            "${ROOTFS_DIR}/etc/dnsmasq.conf"

# Copy hostapd.conf in
# cp files/hostapd.conf "${ROOTFS_DIR}/etc/hostapd/hostapd.conf"
# cp files/hostapd "${ROOTFS_DIR}/etc/default/hostapd"

# The hostap no longer conflicts with the wlan0 service.
# on_chroot << EOF
#         systemctl enable hostapd 
#         systemctl start hostapd 
# EOF

# Choose a better HostAP name than just "SimpleAQ" if nothing else is provided. 
# This file also has firewall safeguards.
# cp files/rc.local "${ROOTFS_DIR}/etc/rc.local"
# on_chroot << EOF
#         chown root:root /etc/rc.local
#         chmod 644 /etc/rc.local
# EOF


# Add AP setup endpoint to /etc/hosts
# on_chroot << EOF
#          echo "" >> /etc/hosts
#          echo "192.168.4.1             simpleaq.setup" >> /etc/hosts
# EOF

# Don't let logs get too big.
on_chroot << EOF
        sed -i '/SystemMaxUse/c\SystemMaxUse=100M' /etc/systemd/journald.conf
EOF

# Disable firewall safeguards for debug builds.
# if [ ${ENABLE_SSH} -eq 1 ]
# then
#   cp files/rc.local.debug "${ROOTFS_DIR}/etc/rc.local"
# fi 
