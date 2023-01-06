#!/usr/bin/python3
"""
thcrap_auto_gui: auto-loader for thcrap on Linux, now with GUI!

Usage on Steam:
1. Put this file in ~/thcrap_auto_gui.py
2. In Steam, use this for command line arguments: ~/thcrap_auto_gui.py %command%

On first launch, thcrap will be downloaded.

Add patch configurations via the thcrap configurator utility (Thcrap
Config button).
Don't try to add games in the "Find games" screen; when done with the
thcrap configurator, just click Cancel.

Any configurations you've added will automatically appear in the
launcher. Click the one you want to use, then "Start Game".
"""

import os
import shutil
import sys
import subprocess
import json
import urllib.request
from os import path
from pathlib import Path
from zipfile import ZipFile

# Development: keep TEST definition.
try:
    TEST
except NameError:
    TEST = False

# Eventually set this based on options & args
gui = True

APP_NAME="Unnamed Thcrap Launcher"
THCRAP_URL = 'https://github.com/thpatch/thcrap/releases/latest/download/thcrap.zip'

# UNIX path to the game's executable. Must be the last argument in the
# command line in normal use.
GAME_EXE = sys.argv[-1]

# Base directory for thcrap
thcrap_dir = path.join(".", "thcrap")

# The base directory can be replaced with an absolute path to use a
# global thcrap dir

# Example of global dir: ~/.thcrap
#thcrap_dir = path.join(os.environ["HOME"], ".thcrap")

# Path to a cached thcrap.zip, to avoid redownloads. Used during development.
thcrap_zip_cache = path.join(os.environ["HOME"], ".cache", "thcrap", "thcrap.zip")

thcrap = path.join(thcrap_dir, "thcrap.exe")
thcrap_loader = path.join(thcrap_dir, "thcrap_loader.exe")
thcrap_config = path.join(thcrap_dir, "config")
thcrap_configjs = path.join(thcrap_config, "config.js")

CONFIG_NAME_MAP = {
    "no patch": "日本語",
    "jp": "日本語",
    "en": "English",
    "es": "Español",
    "de": "Deutsch",
    "pt": "Português",
    "fr": "Français",
    "zh": "中文",
    "kr": " 한국어",
    "en_troll": "English Troll",
}

def decorate_lang(code):
    label = CONFIG_NAME_MAP.get(code, None)
    if label:
        return f'{label}\n({code})'
    return code

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

def init_thcrap(thcrap=thcrap,
                thcrap_dir=thcrap_dir,
                thcrap_zip_cache=thcrap_zip_cache,
                zip_url=THCRAP_URL):
    """Ensures thcrap_dir exists and thcrap is extracted in it"""
    # Make thcrap directory
    if not path.isdir(thcrap_dir):
        Path(thcrap_dir).mkdir(parents=True)

    # Install thcrap if it doesn't already exist
    if not path.exists(thcrap):
        # Use cached development zip, if available
        if path.exists(thcrap_zip_cache):
            shutil.unpack_archive(thcrap_zip, thcrap_dir)
        # Download and extract the thcrap zip
        else:
            with urllib.request.urlopen(zip_url) as f:
                data = io.BytesIO(f.read())
                ZipFile(data).extractall(thcrap_dir)

def load_config():
    """Load config.js, if it exists."""
    # TODO: support JSON5, maybe
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
        # Relative path to game exe, from thcrap dir.
        # Usually something like "../thXX.exe"
        game_exe_rel = os.path.relpath(GAME_EXE, thcrap_dir)

        # Build the modified command line.
        new_command_line = sys.argv[1:-1] + [thcrap_loader, f'{config}.js', game_exe_rel]
    else:
        # Launch game unpatched, in Japanese locale
        os.environ["LANG"]="ja_JP.UTF-8"
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

if gui:
    from tkinter import *
    from tkinter import ttk, font
    import colorsys
    import types

    def hex2rgb(hx):
        "hex string to rgb (float)"
        hx = hx.strip('#')
        n = len(hx) // 3 # nibbles per color
        m = 2 ** (n * 4) - 1 # max value per color
        hex2float = lambda h: int(h, 16) / m
        return tuple(hex2float(hx[i:i+n])
                     for i in range(0, len(hx), n))

    def rgb2hex(r, g, b, nibbles=3):
        "rgb (float) to hex, with given number of nibbles"
        m = 2 ** (nibbles * 4) - 1 # max value per color
        def float2hex(fl):
            i = min(m, max(0, int(fl * m)))
            return format(i, f'0{nibbles}x')
        hex = "".join([float2hex(fl) for fl in (r, g, b)])
        return f"#{hex}"

    def lighten(rgb, factor=0.20):
        (h, s, v) = colorsys.rgb_to_hsv(*hex2rgb(rgb))
        v = min(1, v + v * factor)
        return rgb2hex(*colorsys.hsv_to_rgb(h, s, v))

    def darken(rgb, factor=0.20):
        (h, s, v) = colorsys.rgb_to_hsv(*hex2rgb(rgb))
        v = max(0, v - v * factor)
        return rgb2hex(*colorsys.hsv_to_rgb(h, s, v))

    class Launcher:
        def __init__(self, configs):
            self.configs = configs
            root = self.root = Tk()

            root.title(APP_NAME)
            root.minsize(800, 600)
            root.geometry('1280x800')

            self.set_style()

            # Top level frame, contains everything else
            mainframe = ttk.Frame(root, padding="10", style='Main.TFrame')
            self.mainframe = mainframe
            mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

            # Make top level frame fill the window
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)
            root.bind('<Escape>', lambda *_: self.quit())

            # Configure top level frame grid.
            # 3 equal columns
            for i in range(3):
                mainframe.columnconfigure(i, weight=1, uniform='a')
            # Middle row fills extra space
            mainframe.rowconfigure(1, weight=1)

            self.add_bottom_buttons()
            
            # App name at the top
            ttk.Label(mainframe, text=APP_NAME, style="Main.TLabel")\
               .grid(row=0, columnspan=3)

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
            if not TEST:
                root.mainloop()

        def set_style(self):
            """Define and alter Tk styles"""

            # Increase default font size
            default_font = font.nametofont('TkDefaultFont')
            default_font.configure(size=18)

            underline_font = default_font.copy()
            underline_font.configure(underline='yes')

            bold_font = default_font.copy()
            bold_font.configure(weight='bold')

            # Gotta keep a reference or they get garbage collected and
            # removed from Tk.
            self.__fonts = (bold_font, underline_font)

            sty = ttk.Style(self.root)

            color = types.SimpleNamespace(**{
                'bg_main': '#1f3b3e',
                'bg_button': '#475a61',
                'green': '#5abd42',
                'red': '#bd4242',
                'fg_1': '#bbb',
                'fg_2': '#eee',
            })

            # Prevents unsightly flashes of white when changing
            # notebook tabs
            self.root.configure(background=color.bg_main)

            sty.configure('TFrame',
                          background=color.bg_main)

            sty.configure('Main.TFrame',
                          background=lighten(color.bg_main))

            sty.configure('Main.TLabel',
                          background=lighten(color.bg_main))

            sty.configure('TLabel',
                          background=color.bg_main,
                          foreground=color.fg_1,
                          padding=10)

            sty.configure('TNotebook',
                          background=lighten(color.bg_main),
                          tabposition='nwe',
                          borderwidth=0)
            sty.configure('TNotebook.Tab',
                          foreground=color.fg_2,
                          background=darken(color.bg_main),
                          padding='20 20',
                          borderwidth=0)
            sty.map('TNotebook.Tab',
                    background=[('selected', color.bg_main)])

            sty.configure('Toolbutton',
                          anchor='center', justify='center',
                          foreground=color.fg_2, background=color.bg_button,
                          relief='flat')

            sty.map('Toolbutton',
                    background=[('selected', lighten(color.bg_button, 0.4)),
                                ('active', lighten(color.bg_button, 0.2))],
                    # foreground=[('selected', '#8fd')],
                    borderwidth=[('', 0)])

            sty.configure('TButton',
                          foreground='#f5f5f5', background=color.bg_button,
                          font=bold_font, borderwidth=2,
                          relief='flat')
            sty.map('TButton',
                    background=[('active', lighten(color.bg_button))])

            sty.configure('Start.TButton', background=color.green)
            sty.map('Start.TButton',
                    background=[('active', lighten(color.green))])

            sty.configure('Quit.TButton', background=color.red)
            sty.map('Quit.TButton',
                    background=[('active', lighten(color.red))])

                
        def add_bottom_buttons(self):
            bottom_buttons = [
                ttk.Button(self.mainframe,
                           text="Thcrap Config",
                           command=lambda *_: self.run_thcrap()),
                ttk.Button(self.mainframe, style="Quit.TButton",
                           text="Quit",
                           command=lambda *_: self.quit()),
                ttk.Button(self.mainframe, style="Start.TButton",
                           text="Play",
                           command=lambda *_: self.start_game()),
            ]
            bottom_button_args = {
                'row': 2,
                'padx': 10,
                'pady': 10,
                'ipady': 20,
                'sticky': 'nsew',
            }
            for i,b in enumerate(bottom_buttons):
                b.grid(column=i, **bottom_button_args)


        def run_thcrap(self, *args):
            run_thcrap_config()
            self.refresh_configs(['no patch', *list_configs()])

        def quit(self, *args):
            self.root.destroy()

        def start_game(self, *args):
            config = self.configvar.get()
            config_name = self.configs[config]
            self.root.destroy()
            exec_game(config_name)

        def refresh_configs(self, configs=None):
            if configs:
                self.configs = configs

            for widget in self.configs_frame.winfo_children():
                widget.destroy()

            radio_buttons = []
            for i,k in enumerate(self.configs):
                radio_buttons.append(
                    ttk.Radiobutton(self.configs_frame,
                                    text=decorate_lang(k),
                                    variable=self.configvar,
                                    value=i))

            MIN_ROWS = 2
            MAX_ROWS = 6 # Desired. Can exceed.
            MIN_COLUMNS = 2
            MAX_COLUMNS = 4

            # More rows up to MAX_ROWS, then more columns up to
            # MAX_COLUMNS, then even more rows.
            columns_want = 1 + (len(radio_buttons) - 1) // MAX_ROWS
            columns = max(min(columns_want, MAX_COLUMNS), MIN_COLUMNS)

            # Create columns with equal width
            for i in range(columns):
                self.configs_frame\
                    .columnconfigure(i, weight=1, pad=4, uniform='a')

            # Distribute buttons into grid
            for (i,r) in enumerate(radio_buttons):
                r['style'] = 'Toolbutton'
                r.grid(row = i // columns,
                       column = i % columns,
                       padx=4, pady=4, sticky='nsew')

            # Distribute space among existing rows
            rows = max(self.configs_frame.grid_size()[1], MIN_ROWS)
            for i in range(rows):
                self.configs_frame.rowconfigure(i, weight=1, uniform='a')



configs = ["no patch", "en", "es", "de", "pt", "zh", "kr", "en_troll", "foo", "bar", "en", "jp", "13", "14", "15"]

if TEST:
    launcher = Launcher(configs[:2])
    launcher.refresh_configs([f'Config {i}\n({i})' for i in range(20)])
elif gui:
    check_exe(GAME_EXE)
    init_thcrap()
    Launcher(['no patch', *list_configs()])
else:
    check_exe(GAME_EXE)
    init_thcrap()
    exec_game(list_configs()[0])
