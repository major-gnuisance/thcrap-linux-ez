#!/usr/bin/python3
"""thcrap_auto: auto-loader for thcrap on Linux
Usage on Steam:
1. Put this file in ~/thcrap_auto.py
2. In Steam, use this for command line arguments: ~/thcrap_auto.py %command%
On first launch, the thcrap configurator will run.
Click next until the "Find games" screen, then click "Cancel"
On subsequent runs it'll just run the game or customization tool with thcrap.
"""

import os
import shutil
import sys
import subprocess
import json
import urllib.request
from os import path
from pathlib import Path

# Last argument in the command line. It must be an UNIX path to the game's executable.
GAME_EXE = sys.argv[-1]

# Guard
def check_exe(filename):
    """Does filename look like a .exe that exists under the current directory?"""
    cwd = os.environ["PWD"] # Not os.cwd(), that one canonicalizes the cwd path
    if not filename.casefold().endswith(".exe"):
        raise Exception(f"{filename} doesn't end in exe")
    if not Path(filename).is_relative_to(cwd):
        raise Exception(f"{filename} is not inside the current directory, {cwd}")
    if not path.exists(filename):
        raise Exception(f"{filename} does not exist")
    return True

# Guard invocation
check_exe(GAME_EXE)

THCRAP_URL = 'https://github.com/thpatch/thcrap/releases/latest/download/thcrap.zip'

# Base directory for thcrap
thcrap_dir = path.join(".", "thcrap")

# The base directory can be replaced with an absolute path to use a global thcrap dir
# Example of global dir: ~/.thcrap
#thcrap_dir = path.join(os.environ["HOME"], ".thcrap")

thcrap_zip = path.join(thcrap_dir, "thcrap.zip")
thcrap = path.join(thcrap_dir, "thcrap.exe")
thcrap_loader = path.join(thcrap_dir, "thcrap_loader.exe")
thcrap_config = path.join(thcrap_dir, "config", "config.js")
enjs = path.join(thcrap_dir, "config", "en.js")

# Relative path to game exe, from thcrap dir. Usually something like "../thXX.exe"
game_exe_rel = os.path.relpath(GAME_EXE, thcrap_dir)

# Make thcrap directory
if not path.exists(thcrap_dir):
    Path(thcrap_dir).mkdir(parents=True)

# Install thcrap if it doesn't already exist
if not path.exists(thcrap):
    # Get thcrap zip
    if not path.exists(thcrap_zip):
        urllib.request.urlretrieve(THCRAP_URL, thcrap_zip)

    # Extract zip
    shutil.unpack_archive(thcrap_zip, thcrap_dir)

    # Delete zip
    os.unlink(thcrap_zip)

def is_thcrap_installed():
    "Checks if thcrap is installed."
    # Basic implementation for now.
    return path.exists(enjs)

def load_config():
    "Load config.js, if it exists"
    try:
        with open(thcrap_config, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_config(config):
    "Save config.js"
    with open(thcrap_config, "w", encoding="utf-8", newline="\r\n") as file:
        json.dump(config, file, indent=2)

def override_config_defaults():
    "Change some default settings for thcrap"
    config = load_config()
    overrides = {
        # Stop thcrap from running in the background
        "background_updates": False,
        # Update only the game being launched
        "update_others": False,
    }
    save_config(config | overrides)

# Initial setup.
# Run thcrap.exe instead of the game and let the user figure it out
if not is_thcrap_installed():
    args = sys.argv[1:-1] + [thcrap, '--skip-search-games']
    subprocess.run(args, check=False)
    # Check if it was installed correctly
    if not is_thcrap_installed():
        raise Exception("Thcrap installation appears to have failed.")
    override_config_defaults()

# Build the new modified command line.
new_command_line = sys.argv[1:-1] + [thcrap_loader, "en.js", game_exe_rel]

##### Aside #####
# The line above turns a command line like:
# [STEAM PLAY STUFF] /path/to/th18.exe
#
# Into something like:
# [STEAM PLAY STUFF] /path/to/thcrap/thcrap_loader.exe en.js ../th18.exe
#################

# Exec into the next program in the Steam Play chain
os.execvp(new_command_line[0], new_command_line)

# Reminder: any code after the exec is unreachable.
