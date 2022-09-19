#!/bin/bash
set -e
# This is the entry point for the "compiled" Linux app

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

function check_ldd_version {
  local LIBC_VER_RAW
  LIBC_VER_RAW=$(ldd --version | head -1)
  echo "LIBC version: $LIBC_VER_RAW"
  if ! [[ $LIBC_VER_RAW =~ ([[:digit:]]+)\.([[:digit:]]+) ]]; then
    echo "Could not match LIBC version! Not sure what's going on."
    return 1
  fi
  local LIBC_VER_ALL=${BASH_REMATCH[0]}
  local LIBC_VER_MAJ=${BASH_REMATCH[1]}
  local LIBC_VER_MIN=${BASH_REMATCH[2]}

  # Only support libc 2
  if ! list_include_item '2' "$LIBC_VER_MAJ"; then
    echo "LIBC major version $LIBC_VER_MAJ ($LIBC_VER_ALL) is not supported"
    return 1
  fi
  # Only support >= 28
  if [ "$LIBC_VER_MIN" -lt 28 ]; then
    echo "LIBC minor version $LIBC_VER_MIN ($LIBC_VER_ALL) is not supported"
    return 1
  fi
  return 0
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

function set_supported_python_path {
  if [ -n "${PYTHON+x}" ]; then
    # PYTHON is being set from the CLI
    echo "PYTHON overridden: $PYTHON"
    if check_py_version; then
        return 0
    fi
    echo "Overridden PYTHON not supported. Checking system python versions."
  fi
  # Check the that one of (python, python3) is supported
  if ! command -v python3 > /dev/null; then
    # ok, python3 not available. Try python
    if ! command -v python > /dev/null; then
      # python not available either
      echo "Could not find a python install. (tried python3, python)."
      echo "Please install python3"
      exit 1
    else
      # python is a command
      PYTHON=$(command -v python)
      if ! check_py_version; then
        # check_py_version already gives an error message
        echo "python version is not valid (tried python3, but it's not installed)"
        exit 1
      fi
      # Ok! python is a valid command, and is a supported version
    fi
  else
    # python3 is a command
    PYTHON=$(command -v python3)
    if ! check_py_version; then
      # check_py_version already gives an error message
      echo "python3 version is not valid"
      exit 1
    fi
  fi
}

# Main script logic
if ! check_ldd_version; then
  echo "Unsupported LIBC version, sorry :/"
  exit 1
fi
set_supported_python_path  # This sets $PYTHON
echo "Python command is $PYTHON"
# check venv is available
if ! $PYTHON -c 'import venv' > /dev/null; then
  echo "Python 'venv' module is not installed. Please install it into the $PYTHON environment"
  exit 1
fi

VENV_PATH='./.venv_OATFWGUI'
if [ ! -d "$VENV_PATH" ]; then
  echo "$VENV_PATH is not present, installing virtual environment"
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
