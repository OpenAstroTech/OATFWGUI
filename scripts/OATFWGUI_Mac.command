#!/bin/bash
set -e
# This is the entry point for the "compiled" MacOS app
# Note that this based off of the Linux script, except for:
# - removal of the libc version check
# - conversion from GNU to BSD-isms
# - special checking for python3 installation

# list_include_item "10 11 12" "2"
function list_include_item {
  local list="$1"
  local item="$2"
  if [[ $list =~ (^|[[:space:]])"$item"($|[[:space:]]) ]] ; then
    # yes, list include item
    return 0
  else
    return 1
  fi
}

function check_py_version {
  local PY_VER_RAW
  PY_VER_RAW=$($PYTHON --version)
  echo "Python version: $PY_VER_RAW"
  if ! [[ $PY_VER_RAW =~ ([[:digit:]]+)\.([[:digit:]]+)\.([[:digit:]]+) ]]; then
    echo "Could not match python version! Not sure what's going on."
    return 1
  fi
  local PY_VER_ALL=${BASH_REMATCH[0]}
  local PY_VER_MAJ=${BASH_REMATCH[1]}
  local PY_VER_MIN=${BASH_REMATCH[2]}
  # local PY_VER_PAT=${BASH_REMATCH[3]}

  # Only support python 3
  if ! list_include_item '3' "$PY_VER_MAJ"; then
    echo "Python major version $PY_VER_MAJ ($PY_VER_ALL) is not supported"
    return 1
  fi
  # Only support 3.7+
  if ! list_include_item '7 8 9 10 11' "$PY_VER_MIN"; then
    echo "Python minor version $PY_VER_MIN ($PY_VER_ALL) is not supported"
    return 1
  fi
  return 0
}

function will_get_stub_popup {
  # https://stackoverflow.com/a/71150139/1313872 but modified  for all stubs
  echo "Checking if $1 is a stub"
  if [[ $(which "$1") == "/usr/bin/$1"* ]]; then
    if [ -d "/Applications/Xcode.app/Contents/Developer/usr/bin/$1" ]; then
      return 1  # won't get a popup if we try to launch
    else
      return 0  # not installed, we'll get a popup
    fi
  else
    return 1  # won't get a popup if we try to launch
  fi
}

function set_supported_python_path {
  if [ -n "${PYTHON+x}" ]; then
    # PYTHON is being set from the CLI
    echo "PYTHON overridden: $PYTHON"
    if check_py_version; then
        return 0
    fi
    echo "Overridden PYTHON not supported. Checking system python versions."
  fi
  # We already checked that python3 isn't a stub
  if command -v python3 > /dev/null; then
    PYTHON=$(command -v python3)
    if ! check_py_version; then
      # check_py_version already gives an error message
      echo "python3 version is not valid"
      exit 1
    fi
  fi
}

# Main script logic
# "readlink -f" not available: https://unix.stackexchange.com/a/690000
SCRIPT_DIR=$( cd "$(dirname "$0")" ; pwd -P )
echo "Script dir: $SCRIPT_DIR"
pushd "$SCRIPT_DIR" > /dev/null # relative paths can now be used

if will_get_stub_popup python3; then
  echo ''
  echo 'python3 is not installed. The quickest and least intrusive way to install is https://www.python.org/downloads/release/python-3114/'
  echo '(download links are at the bottom)'
  echo "Note that you do not need to install \"Python Documentation\" or \"GUI Applications\""
  echo "(click \"Customize\" during the \"Installation Type\" step)"
  echo ''
  exit 1
fi

if will_get_stub_popup git; then
  echo ''
  echo 'git is not installed. The quickest and least intrusive way to install is https://sourceforge.net/projects/git-osx-installer/files/'
  echo ''
  exit 1
fi

VENV_PATH='./.venv_OATFWGUI'
if [ ! -d "$VENV_PATH" ]; then
  echo "$VENV_PATH is not present, installing virtual environment"

  set_supported_python_path  # This sets $PYTHON
  echo "Python command is $PYTHON"
  # check venv is available
  if ! $PYTHON -c 'import venv' > /dev/null; then
    echo "Python 'venv' module is not installed. Please install it into the $PYTHON environment"
    exit 1
  fi

  $PYTHON -m venv --prompt 'OATFWGUI>' "$VENV_PATH"
  echo "Upgrading pip"
  $VENV_PATH/bin/pip install --upgrade pip
  echo "Installing requirements"
  $VENV_PATH/bin/pip install --requirement ./requirements.txt
fi
# activate virtual environment
source $VENV_PATH/bin/activate
# now can can just run python -- no need to use system $PYTHON
python3 OATFWGUI/main.py "$@"
popd >> /dev/null
