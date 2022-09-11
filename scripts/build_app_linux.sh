#!/bin/bash
set -e

REPO_DIR=$(git rev-parse --show-toplevel)
MEI_BIN_DIR="bin"

pushd $REPO_DIR
./.venv/bin/pyinstaller \
--distpath=./dist_linux --workpath=./build_linux \
--noconfirm --onedir --clean --name=OATFWGUI \
--collect-all=platformio \
--add-binary=./.venv/bin/platformio:$MEI_BIN_DIR \
 "$@" \
./OATFWGUI/main.py
popd
