#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

# Install SimpleAQ requirements.
on_chroot << EOF
        pip install -r /simpleaq/requirements.txt
EOF

# Delete unnecessary custom pigen stuff.
on_chroot << EOF
        rm -rf /simpleaq/custom_pigen
EOF


