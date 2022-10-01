# OAT FirmWare GUI
OpenAstroTech FirmWare Graphical User Interface -- Graphical way to build and load firmware onto an OpenAstroTracker/OpenAstroMount.

## Supported platforms
- Windows 64 bit
- Linux
  - Requires Python 3.7+, LIBC >= 2.28 (check with `ldd --version`)

MacOS might work, don't have a mac to test on. Drop a line if you're willing to test it!

## Installing
Simply download the [latest release](https://github.com/julianneswinoga/OATFWGUI/releases), unzip and run:
- Windows: `OATFWGUI.exe`
- Linux: `OATFWGUI_Linux.sh`
  - Override the python interpreter by setting `PYTHON` (i.e. `PYTHON=/usr/bin/python3.10 ./OATFWGUI_Linux.sh`)
  - This creates a local python virtual environment in `.venv_OATFWGUI`. If there's an error during the first run, delete that folder to have the script try again.

> :warning: **OATFWGUI requires an active internet connection!**

It is a local installation, so to remove it simply delete the folder.

## Screenshots
Windows:
![](assets/screenshot_Windows.jpg)

Linux:
![](assets/screenshot_Linux.jpg)
