#!/bin/bash -e

# TODO:  Remove the ls here.
on_chroot << EOF
        pwd
        ls /simpleaq/  
        pip install -r /simpleaq/requirements.txt
EOF
