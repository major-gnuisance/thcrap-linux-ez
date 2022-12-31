#!/usr/bin/python3
"""thcrap_auto: auto-loader for thcrap on Linux
Usage on Steam:
1. Put this file in ~/thcrap_auto.py
2. Make it executable: chmod +x ~/thcrap_auto.py
3. In Steam, use this for command line arguments: ~/thcrap_auto.py %command%
4. On first launch, the thcrap configurator will run. If set up correctly, on subsequent runs it'll just run the game or customization tool with thcrap.
"""

import shutil
import urllib.request
import os
import sys
from os import path

# Guard
if not path.exists("custom.exe"):
    print('custom.exe not found, probably not running in a Touhou game dir. Aborting!')
    sys.exit(1)

THCRAP_URL = 'https://github.com/thpatch/thcrap/releases/latest/download/thcrap.zip'

thcrap_dir = path.join(".", "thcrap")
thcrap_zip = path.join(thcrap_dir, "thcrap.zip")
thcrap = path.join(thcrap_dir, "thcrap.exe")

# Make thcrap directory
if not path.exists(thcrap_dir):
    os.mkdir(thcrap_dir)

# Install thcrap if it doesn't already exist
if not path.exists(thcrap):
    # Get thcrap zip
    if not path.exists(thcrap_zip):
        urllib.request.urlretrieve(THCRAP_URL, thcrap_zip)

    # Extract zip
    shutil.unpack_archive(thcrap_zip, thcrap_dir)

    # Delete zip
    os.unlink(thcrap_zip)

# Initial setup, just run thcrap.exe and let the user figure it out
if not path.exists(path.join(thcrap_dir, "config", "en.js")):
    os.execvp(sys.argv[1], sys.argv[1:-1] + [path.join(thcrap_dir, "thcrap.exe")])


exec_name = path.join("..", path.basename(sys.argv[-1]))
my_args = [path.join(thcrap_dir, "thcrap_loader.exe"), "en.js", exec_name]

os.execvp(sys.argv[1], sys.argv[1:-1] + my_args)
