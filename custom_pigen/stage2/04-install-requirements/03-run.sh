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
        cat /etc/environment
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

