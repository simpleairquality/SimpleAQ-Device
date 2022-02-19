#!/bin/bash -e

on_chroot << EOF
        pip install -r /simpleaq/requirements.txt
EOF
