#!/bin/bash -e

cp -R /simpleaq "${ROOTFS_DIR}"

on_chroot << EOF
        pip install -r /simpleaq/requirements.txt
EOF
