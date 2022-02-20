#!/bin/bash -e

# TODO:  Remove the ls here.
on_chroot << EOF
        ls /simpleaq/  
        pip install -r /simpleaq/requirements.txt
EOF
