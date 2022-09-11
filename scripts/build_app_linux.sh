#!/bin/bash
set -e

REPO_DIR=$(git rev-parse --show-toplevel)

pushd $REPO_DIR
./.venv/bin/pyinstaller \
--distpath=./dist_linux --workpath=./build_linux \
--noconfirm --clean \
"$@" \
./OATFWGUI.spec
popd
