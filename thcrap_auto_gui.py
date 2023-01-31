#!/usr/bin/python3
"""
thcrap_auto_gui: auto-loader for thcrap on Linux, now with GUI!

Usage on Steam:
1. Put this file in ~/thcrap_auto_gui.py
2. In Steam, use this for command line arguments:
python3 ~/thcrap_auto_gui.py --gui %command%

Thcrap will be downloaded automatically when needed.

Add patch configurations via the thcrap configurator utility (Thcrap
Config button).

Any patch configurations you've added will automatically appear in the
launcher. Select the one you want, then click "Play".

"""

import argparse
import io
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

APP_ID = "thcrap-launcher"
APP_NAME = "Thcrap Launcher"
APP_DESCRIPTION = "Launcher for Touhou Games using Thcrap, for Steam on Linux or Wine."
HELP_EPILOG = """If unset, XDG_DATA_DIR defaults to ~/.local/share

The positional arguments are supposed to come from a %command% in the Steam launch options.
Otherwise, it must be something equivalent to it - a command that would start the game normally, under Wine. 

Paths can be absolute or relative.
Relative paths are relative to the process working directory, usually the game directory if launched under Steam.
Tilde expansion for home directories is applied.

Examples of paths for THCRAP_DIR:
  thcrap OR ./thcrap       - `thcrap' under the game directory.
  ../shared_thcrap         - `shared_thcrap' in the parent of the game directory.
  /home/deck/global_thcrap - An absolute path
  ~/global_thcrap          - The same as above if your HOME is /home/deck
"""

XDG_DATA_DIR_DEFAULT = path.join(os.environ["HOME"], ".local", "share")
XDG_DATA_DIR = os.environ.get("XDG_DATA_DIR", XDG_DATA_DIR_DEFAULT)

XDG_CACHE_DIR_DEFAULT = path.join(os.environ["HOME"], ".cache")
XDG_CACHE_DIR = os.environ.get("XDG_CACHE_DIR", XDG_CACHE_DIR_DEFAULT)

DEFAULT_GLOBAL_THCRAP_DIR = path.join(XDG_DATA_DIR, APP_ID)
DEFAULT_GLOBAL_THCRAP_DIR_HELP = f"$XDG_DATA_DIR/{APP_ID}"
DEFAULT_RELATIVE_THCRAP_DIR = path.join(".", "thcrap")

THCRAP_URL = 'https://github.com/thpatch/thcrap/releases/latest/download/thcrap.zip'

# Argument parsing
parser = argparse.ArgumentParser(
    prog = sys.argv[0] or 'thcrap_auto_gui.py',
    description = APP_DESCRIPTION,
    epilog = HELP_EPILOG,
    formatter_class = argparse.RawDescriptionHelpFormatter
)
parser.add_argument('-g', '--gui', action='store_true',
                    help="launch the GUI.")
parser.add_argument('-p', '--patch',
                    help="patch name for thcrap. Will be passed to thcrap as PATCH.js. Example: `-p en' will invoke thcrap with en.js. Use -p no_patch to run game without thcrap.",
                    action='store',
                    metavar='PATCH')
parser.add_argument('-c', '--thcrap-configurator', action='store_true',
                    help='Run the thcrap configurator and exit.')
parser.add_argument('-d', '--thcrap-dir',
                    help=f'directory where thcrap will be located.',
                    action='store',
                    metavar='THCRAP_DIR',
                    default=DEFAULT_GLOBAL_THCRAP_DIR)
parser.add_argument('--global', action='store_const',
                    help=f'''use default absolute thcrap dir. Same as `--thcrap-dir "{DEFAULT_GLOBAL_THCRAP_DIR_HELP}"'. Default behaviour.''',
                    dest='thcrap_dir',
                    const=DEFAULT_GLOBAL_THCRAP_DIR)
parser.add_argument('--relative', action='store_const',
                    help=f'''use default relative thcrap dir. Same as `--thcrap-dir {DEFAULT_RELATIVE_THCRAP_DIR}\'''',
                    dest='thcrap_dir',
                    const=DEFAULT_RELATIVE_THCRAP_DIR)


parser.add_argument('args', nargs='+',
                    help='Arbitrary command line arguments that will be executed verbatim when launching the game or thcrap.')
parser.add_argument('game_exe',
                    metavar='GAME.exe',
                    help='UNIX path to game executable. Must be the very last argument.')

if not TEST:
    args = parser.parse_args()
else:
    args = parser.parse_args(['--gui', 'foo', 'bar.exe'])
    parser.print_help()

# Whether or not to use the GUI
gui = args.gui

# UNIX path to the game's executable.
game_exe = args.game_exe

# Base directory for thcrap
thcrap_dir = args.thcrap_dir

# Path to a cached thcrap.zip, to avoid redownloads. Used during development.
thcrap_zip_cache = path.join(XDG_CACHE_DIR, APP_ID, "thcrap.zip")

thcrap = path.join(thcrap_dir, "thcrap.exe")
thcrap_loader = path.join(thcrap_dir, "thcrap_loader.exe")
thcrap_config = path.join(thcrap_dir, "config")
thcrap_configjs = path.join(thcrap_config, "config.js")
thcrap_update_dll = path.join(thcrap_dir, "bin", "thcrap_update.dll")
thcrap_update_dll_disabled = thcrap_update_dll.replace(".dll", "_disabled.dll")
thcrap_steam_dll = path.join(thcrap_dir, "bin", "steam_api.dll")
thcrap_steam_dll_disabled = thcrap_steam_dll.replace(".dll", "_disabled.dll")

launcher_settings_path = path.join(thcrap_dir, "thcrap_launcher.json")

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
        # TODO: use mode 700 if creating app dir under $XDG_DATA_DIR, per XDG Base Directory Specification.

    # Install thcrap if it doesn't already exist
    if not path.exists(thcrap):
        # Use cached development zip, if available
        if path.exists(thcrap_zip_cache):
            shutil.unpack_archive(thcrap_zip, thcrap_dir)
        # Download and extract the thcrap zip
        else:
            with urllib.request.urlopen(zip_url) as f:
                data = io.BytesIO(f.read())
            with ZipFile(data) as zipf:
                zipf.extractall(thcrap_dir)

def load_json(path):
    """Load config.js, if it exists."""
    # TODO: support JSON5, maybe
    try:
        with open(path, encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_json(config, path):
    "Save config.js"
    with open(path, "w", encoding="utf-8", newline="\r\n") as file:
        json.dump(config, file, indent=2)

def override_config_defaults():
    "Change some default settings for thcrap"
    config = load_json(thcrap_configjs)
    overrides = {
        # Stop thcrap from running in the background
        "background_updates": False,
        # Update only the game being launched
        "update_others": False,
    }
    save_json(config | overrides, thcrap_configjs)

def is_patch_config_file(path):
    try:
        with open(path) as file:
            contents = json.load(file)
        return contents.get('patches', None)
    except Exception:
        return False

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
    except Exception:
        return []


def run_thcrap_config():
    "Run thcrap configuration tool. Blocking."
    # Preseed config
    if not path.exists(thcrap_config):
        os.mkdir(thcrap_config)
        override_config_defaults()
    run_args = args.args + [thcrap, '--skip-search-games']
    subprocess.run(run_args, check=False)

def load_settings():
    return load_json(launcher_settings_path)

def save_settings(settings):
    save_json(settings, launcher_settings_path)

def get_lastrun(settings=load_settings()):
    """Get name of last config used"""
    return str(settings.get('last_run', 'no_config'))

def set_lastrun(config_name):
    """Save name of last config used"""
    save_settings(load_settings() | {'last_run': config_name})

def exec_game(config="en"):
    if config not in ('no patch', 'no_patch'):
        # Relative path to game exe, from thcrap dir.
        # Usually something like "../thXX.exe"
        game_exe_rel = os.path.relpath(game_exe, thcrap_dir)

        # Build the modified command line.
        new_command_line = args.args + [thcrap_loader, f'{config}.js', game_exe_rel]
    else:
        # Launch game unpatched, in Japanese locale
        os.environ["LANG"]="ja_JP.UTF-8"
        new_command_line = args.args + [game_exe]

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
    import tkinter.colorchooser
    import tkinter.messagebox
    import colorsys
    import types

    def hex2rgb(hx):
        "hex string to rgb (float)"
        hx = hx.strip('#')
        n = len(hx) // 3 # nibbles per color
        m = 2 ** (n * 4) - 1 # max value per color
        def hex2float(h):
            return int(h, 16) / m
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

            self.default_color = {
                'bg_main': '#1f3b3e',
                'bg_button': '#475a61',
                'green': '#5abd42',
                'red': '#bd4242',
                'fg_1': '#bbb',
                'fg_2': '#eee',
            }

            settings = load_settings()
            
            self.color = settings.get('color', {})

            self.set_style()

            # Top level frame, contains everything else
            mainframe = ttk.Frame(root, padding="10", style='Main.TFrame')
            self.mainframe = mainframe
            mainframe.grid(column=0, row=0, sticky=(N, W, E, S))

            # Make top level frame fill the window
            root.columnconfigure(0, weight=1)
            root.rowconfigure(0, weight=1)

            # Quit on ESC
            root.bind('<Escape>', lambda *_: self.quit())

            # Press buttons with enter key
            root.bind_class('TButton', '<Return>', ' ttk::button::activate %W')

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
            self.add_settings()

            # Add Frames to notebook
            notebook.add(configs_frame, text="Configurations")
            notebook.add(config_settings_frame, text="Patch Options")
            notebook.add(settings_frame, text="Launcher Settings")

            self.configvar = IntVar(value=0)
            self.refresh_configs()
            # root.attributes("-fullscreen", True)
            if not TEST:
                root.mainloop()

        def set_color(self, color_name, color):
            self.color[color_name]=color

        def get_colors(self):
            return (self.default_color | self.color)

        def get_color(self, color_name):
            return self.get_colors().get(color_name)

        def save_colors(self):
            settings = load_settings()
            settings['color']=self.color
            save_settings(settings)

        def reset_colors(self):
            self.color = {}
            self.set_style()
            self.add_settings()

        def change_color(self, color_name):
            """Show color picker and change color."""
            current_color = self.get_color(color_name)
            (_, color) = tkinter.colorchooser.askcolor(color=current_color)
            if color:
                self.set_color(color_name, color)
                self.set_style()
                self.add_settings()

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

            color = types.SimpleNamespace(**(self.get_colors()))

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

            sty.configure('Setting.TButton',
                          anchor='w')

            sty.configure('Start.TButton', background=color.green)
            sty.map('Start.TButton',
                    background=[('active', lighten(color.green))])

            sty.configure('Quit.TButton', background=color.red)
            sty.map('Quit.TButton',
                    background=[('active', lighten(color.red))])

            sty.configure('TCheckbutton',
                          foreground='#f5f5f5', background=color.bg_button,
                          font=bold_font, borderwidth=2,
                          relief='flat',
                          indicatorcolor=darken(color.bg_button),
                          indicatordiameter=25,
                          indicatormargin=10,
                          indicatorrelief='flat')
            
            sty.map('TCheckbutton',
                    background=[('active', lighten(color.bg_button))],
                    indicatorcolor=[('selected', color.green)])

        def set_updater(self, enable):
            if enable and path.exists(thcrap_update_dll_disabled):
                os.rename(thcrap_update_dll_disabled, thcrap_update_dll)
                self.updater_var.set(1)
            elif path.exists(thcrap_update_dll):
                os.rename(thcrap_update_dll, thcrap_update_dll_disabled)
                self.updater_var.set(0)

        def set_steamintegration(self, enable):
            if enable and path.exists(thcrap_steam_dll_disabled):
                os.rename(thcrap_steam_dll_disabled, thcrap_steam_dll)
                self.steamintegration_var.set(1)
            elif path.exists(thcrap_steam_dll):
                os.rename(thcrap_steam_dll, thcrap_steam_dll_disabled)
                self.steamintegration_var.set(0)

        def add_settings(self):
            frame = self.settings_frame

            for widget in frame.winfo_children():
                widget.destroy()

            gridargs = {
                'ipady': 30,
                'pady': 4,
                'padx': 10,
                'sticky': 'ew',
            }

            self.updater_var = IntVar(value=1 if path.exists(thcrap_update_dll) else 0)
            updater_checkbox = ttk.Checkbutton(
                frame,
                text='Thcrap Updater',
                command=lambda *_: self.set_updater(self.updater_var.get() != 0),
                variable=self.updater_var)
            updater_checkbox.grid(**gridargs)

            self.steamintegration_var = IntVar(value=1 if path.exists(thcrap_steam_dll) else 0)
            steamintegration_checkbox = ttk.Checkbutton(
                frame,
                text='Thcrap Steam Integration',
                command=lambda *_: self.set_steamintegration(self.steamintegration_var.get() != 0),
                variable=self.steamintegration_var)
            steamintegration_checkbox.grid(**gridargs)

            self._bugs = IntVar(value=0)
            bugs = ttk.Checkbutton(
                frame,
                text='Disable all bugs',
                # state='disabled',
                variable=self._bugs,
                command=lambda *_: bugs.destroy()
            )
            bugs.grid(**gridargs)

            save_colors = ttk.Button(
                frame,
                text='Save Colors',
                command=lambda *_: self.save_colors())
            save_colors.grid(**gridargs)

            default_colors = ttk.Button(
                frame,
                text='Reset Colors',
                command=lambda *_: self.reset_colors())
            default_colors.grid(**gridargs)

            def change_color_factory(color_name):
                def change_color():
                    self.change_color(color_name)
                return change_color

            color_buttons = []
            for color_name, color in self.get_colors().items():
                color_buttons.append(
                    ttk.Button(
                        frame, style='Setting.TButton',
                        text=f'Change color {color_name} ({color})',
                        command=change_color_factory(color_name)))
            for i,button in enumerate(color_buttons):
                button.grid(**gridargs, column=1, row=i)

            for i in range(frame.grid_size()[1]):
                frame.rowconfigure(i, weight=1, uniform='a')

            for i in range(frame.grid_size()[0]):
                frame.columnconfigure(i, weight=1, uniform='a')



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

            self.bottom_buttons = bottom_buttons
            bottom_buttons[2].focus()


        def run_thcrap(self, *args):
            run_thcrap_config()
            self.refresh_configs(['no patch', *list_configs()])

        def quit(self, *args):
            self.root.destroy()

        def start_game(self, *args):
            config = self.configvar.get()
            config_name = self.configs[config]
            self.root.destroy()
            set_lastrun(config_name)
            exec_game(config_name)

        def refresh_configs(self, configs=None):
            if configs:
                self.configs = configs

            try:
                lastrun = get_lastrun()
                self.configvar.set(self.configs.index(lastrun))
            except ValueError:
                pass

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



configs = ["no patch", "en", "es", "de", "pt", "zh", "kr", "en_troll",
           "foo", "bar", "en", "jp"]

if gui:
    if TEST:
        launcher = Launcher(configs[:2])
        launcher.refresh_configs([f'Config {i}\n({i})' for i in range(20)])

    else:
        try:
            check_exe(game_exe)
            init_thcrap()
            Launcher(['no patch', *list_configs()])
        except Exception as e:
            tkinter.messagebox.showerror(
                title=f'Error in {APP_NAME}',
                message=f'{APP_NAME} encountered an error and will now exit.\nError: {e}'
            )
else:
    first_run = not path.exists(thcrap_config)
    init_thcrap()
    if args.thcrap_configurator:
        run_thcrap_config()
        sys.exit()
    elif first_run:
        run_thcrap_config()

    check_exe(game_exe)
    if args.patch in list_configs():
        exec_game(args.patch)
