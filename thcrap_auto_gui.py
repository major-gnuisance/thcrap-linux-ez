#!/usr/bin/python3
"""thcrap_auto_gui: auto-loader for thcrap on Linux, now with GUI!
Usage on Steam:
1. Put this file in ~/thcrap_auto_gui.py
2. In Steam, use this for command line arguments: ~/thcrap_auto_gui.py %command%
On first launch, thcrap will be downloaded.
Add patch configurations via the thcrap configurator utility (Thcrap Config button).
Don't try to add games in the "Find games" screen; when done with the thcrap configurator just click Cancel.
Configurations you have added will automatically appear in the launcher.
In the launcher, click the configuration you want to use, then "Start Game".
"""

import os
import shutil
import sys
import subprocess
import json
import urllib.request
from os import path
from pathlib import Path

APP_NAME="Unnamed Thcrap Launcher"
THCRAP_URL = 'https://github.com/thpatch/thcrap/releases/latest/download/thcrap.zip'

CONFIG_NAME_MAP = {
    "no patch": "日本語",
    "jp": "日本語",
    "en": "English",
    "es": "Español",
    "de": "Deutsch",
    "pt": "Português",
    "zh": "中文",
    "kr": " 한국어",
    "en_troll": "English Troll",
}

def decorate_lang(code):
    label = CONFIG_NAME_MAP.get(code, None)
    if label:
        return f'{label}\n({code})'
    return code

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

# Base directory for thcrap
thcrap_dir = path.join(".", "thcrap")

# The base directory can be replaced with an absolute path to use a global thcrap dir
# Example of global dir: ~/.thcrap
#thcrap_dir = path.join(os.environ["HOME"], ".thcrap")

thcrap_zip = path.join(thcrap_dir, "thcrap.zip")
thcrap = path.join(thcrap_dir, "thcrap.exe")
thcrap_loader = path.join(thcrap_dir, "thcrap_loader.exe")
thcrap_config = path.join(thcrap_dir, "config")
thcrap_configjs = path.join(thcrap_config, "config.js")

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

def load_config():
    "Load config.js, if it exists"
    try:
        with open(thcrap_configjs, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_config(config):
    "Save config.js"
    with open(thcrap_configjs, "w", encoding="utf-8", newline="\r\n") as file:
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

def is_patch_config_file(path):
    try:
        with open(path) as file:
            contents = json.load(file)
        return contents.get('patches', None)
    except Exception:
        return false

def list_configs():
    "Return list of available patch configs"
    try:
        return [
            f.name.removesuffix('.js')
            for f in os.scandir(thcrap_config)
            if f.name.endswith('.js')
            and f.is_file()
            and f.stat().st_size < 2**20
            and is_patch_config_file(path.join(thcrap_config, f.name))
        ]
    except:
        return []


def run_thcrap_config():
    "Run thcrap configuration tool. Blocking."
    # Preseed config
    if not path.exists(thcrap_config):
        os.mkdir(thcrap_config)
        override_config_defaults()
    args = sys.argv[1:-1] + [thcrap]
    subprocess.run(args, check=False)

def exec_game(config="en"):
    if config != 'no patch':
        # Build the modified command line.
        new_command_line = sys.argv[1:-1] + [thcrap_loader, f'{config}.js', game_exe_rel]
    else:
        new_command_line = sys.argv[1:]

    ##### Aside #####
    # The line above turns a command line like:
    # [STEAM STUFF] /path/to/th18.exe
    #
    # Into something like:
    # [STEAM STUFF] /path/to/thcrap/thcrap_loader.exe en.js ../th18.exe
    #################

    # Exec the next program in the command line
    os.execvp(new_command_line[0], new_command_line)
    # This ends control for the Python script

gui = True
if gui:
    from tkinter import *
    from tkinter import ttk, font

    class Launcher:
        def __init__(self, configs):
            self.configs = configs
            root = self.root = Tk()

            root.title(APP_NAME)
            root.minsize(800, 600)
            root.geometry('1280x800')

            ######### Styling Section
    
            # Increase default font size
            default_font = font.nametofont('TkDefaultFont')
            default_font.configure(size=26)

            underline_font = default_font.copy()
            underline_font.configure(underline='yes')

            bold_font = default_font.copy()
            bold_font.configure(weight='bold')

            sty = ttk.Style(root)

            sty.configure('TFrame',
                          background='#454545')

            sty.configure('TLabel',
                          background='#454545',
                          foreground='#bbb',
                          padding=10)

            sty.configure('TNotebook',
                          background='#454545')
            sty.configure('TNotebook.Tab',
                          foreground='#bbb',
                          background='#454545',
                          padding='40 20')
            sty.map('TNotebook.Tab',
                    background=[('selected','#101010'),
                                ('active','#3c3c3c')])

            sty.configure('Toolbutton',
                          anchor='center', justify='center',
                          foreground='#eee', background='#2c2c2c')

            sty.map('Toolbutton',
                    background=[('selected', '#101010'),
                                ('active', '#3c3c3c')],
                    foreground=[('selected', '#dfd')],
                    font=[('selected', bold_font)])

            light_buttons = False
            if light_buttons:
                sty.configure('TButton',
                              foreground='#333', font=bold_font)

                sty.configure('Start.TButton', background='#b7f5ab')
                sty.map('Start.TButton', background=[('active', '#c8f4c0')])

                sty.configure('Quit.TButton', background='#f5abb6')
                sty.map('Quit.TButton', background=[('active', '#f4c0c8')])
            else:
                sty.configure('TButton',
                              foreground='#f5f5f5', background='#222',
                              font=bold_font)
                sty.map('TButton',
                        background=[('active', '#333')])

                sty.configure('Start.TButton', background='#234021')
                sty.map('Start.TButton', background=[('active', '#3c4b3b')])

                sty.configure('Quit.TButton', background='#402121')
                sty.map('Quit.TButton', background=[('active', '#4d2727')])

            ######## End of Styling Section
    

            # Top level frame, contains everything else
            mainframe = ttk.Frame(root, padding="10")
            mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

            # Make top level frame fill the window
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)

            # Configure top level frame grid.
            # 3 equal columns
            for i in range(3):
                mainframe.columnconfigure(i, weight=1, uniform='a')
            # Middle row fills extra space
            mainframe.rowconfigure(1, weight=1)

            def run_thcrap(*args):
                run_thcrap_config()
                self.refresh_configs(['no patch', *list_configs()])

            def quit_launcher(*args):
                root.destroy()

            root.bind('<Escape>', quit_launcher)

            def start_game(*args):
                config = self.configvar.get()
                config_name = self.configs[config]
                print(f'{config}: {config_name}')
                root.destroy()
                exec_game(config_name)

            # Bottom action buttons
            button_args = {'row': 2, 'padx': 10, 'pady': 10, 'ipady': 30, 'sticky': 'nsew'}
            ttk.Button(mainframe, text="Thcrap Config", command=run_thcrap)\
               .grid(column=0, **button_args)
            ttk.Button(mainframe, text="Quit", command=quit_launcher, style="Quit.TButton")\
               .grid(column=1, **button_args)
            ttk.Button(mainframe, text="Start Game", command=start_game, style="Start.TButton")\
               .grid(column=2, **button_args)

            # App name at the top
            ttk.Label(mainframe, text=APP_NAME).grid(row=0, columnspan=3)

            # Tabbed notebook widget, occupies middle row of top level frame
            notebook = ttk.Notebook(mainframe)
            notebook.grid(row=1, columnspan=3, sticky='nsew')

            # Frame that holds grid of available configurations
            configs_frame = ttk.Frame(notebook)
            self.configs_frame = configs_frame

            # Frame that holds configuration-specific settings
            config_settings_frame = ttk.Frame(notebook, padding="20")
            self.config_settings_frame = config_settings_frame
            ttk.Label(config_settings_frame, text="TODO").pack()

            # Frame that holds global settings
            settings_frame = ttk.Frame(notebook, padding="20")
            self.settings_frame = settings_frame
            ttk.Label(settings_frame, text="TODO").pack()

            # Add Frames to notebook
            notebook.add(configs_frame, text="Configurations")
            notebook.add(config_settings_frame, text="Patch Options")
            notebook.add(settings_frame, text="Launcher Settings")

            self.configvar = IntVar(value=0)
            self.refresh_configs()
            # root.attributes("-fullscreen", True)
            root.mainloop()

        def refresh_configs(self, configs=None):
            if configs:
                self.configs = configs

            radio_buttons = []
            for i,k in enumerate(self.configs):
                radio_buttons.append(
                    ttk.Radiobutton(self.configs_frame,
                                    text=decorate_lang(k),
                                    variable=self.configvar,
                                    value=i))

            configs_columns=max(3, min(5, 1+(len(radio_buttons)-1)//2))
            CONFIGS_MIN_ROWS=2

            # Set 5 columns with equal width
            for i in range(configs_columns):
                self.configs_frame.columnconfigure(i, weight=1, pad=10, uniform="a")

            for (i,r) in enumerate(radio_buttons):
                r['style']="Toolbutton"
                column = i % configs_columns
                row = i // configs_columns
                r.grid(row=row, column=column, padx=10, pady=10, sticky='nsew')

            # Distribute space among existing columns (min 2)
            configs_rows = max(CONFIGS_MIN_ROWS,
                               self.configs_frame.grid_size()[1])

            for i in range(configs_rows):
                self.configs_frame.rowconfigure(i, weight=1, uniform='b')



# configs = ["no patch", "en", "es", "de", "pt", "zh", "kr", "en_troll", "foo", "bar"]

if gui:
    Launcher(['no patch', *list_configs()])
