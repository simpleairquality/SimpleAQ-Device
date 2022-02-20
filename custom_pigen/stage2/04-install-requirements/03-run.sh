#!/bin/bash -e

# TODO:  Remove the ls here.
on_chroot << EOF
        pwd
        ls 
        pip install -r /simpleaq/requirements.txt
EOF
