#!/bin/bash
set -e
# This is the entry point for the "compiled" Linux app

./baked_venv/bin/python OATFWGUI/main.py "$@"
