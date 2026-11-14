"""Where the app lives and where it keeps its profiles and settings.

configs/ sits beside the launcher: main.py for the source tree, the
single-file edition's .py, or the EXE for compiled builds.
"""

import os
import sys
from pathlib import Path


def entry_point():
    """The script that starts the app (main.py, or the single-file edition)."""
    single = globals().get("_single_file_entry")  # set by the single-file loader
    if single:
        return Path(single)
    return Path(__file__).resolve().parent.parent / "main.py"


def _restart_app_dir():
    """The folder of the copy that restarted this one (Display size change), or "".

    v108.164: a restarted copy uses the same folder, and so the same configs,
    whatever its own location says. The variable is removed so that it is not
    passed on.
    """
    folder = os.environ.pop("SPNAV_RESTART_APP_DIR", "")
    if folder and "--restart-ui-scale" in sys.argv and os.path.isdir(folder):
        return os.path.abspath(folder)
    return ""


def _app_base_dir():
    """Folder holding configs: the EXE's folder, or the launcher's folder."""
    restarted = _restart_app_dir()
    if restarted:
        return restarted
    # Nuitka onefile: __compiled__.containing_dir is the EXE's folder,
    # not Nuitka's temporary extraction directory.
    try:
        return os.path.abspath(__compiled__.containing_dir)  # noqa: F821
    except (NameError, AttributeError):
        pass
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return str(entry_point().resolve().parent)


APP_DIR = _app_base_dir()
try:
    os.chdir(APP_DIR)  # Relative profile paths in older configs resolve from here.
except OSError:
    pass
CONFIG_DIR = os.path.join(APP_DIR, "configs")
LAST_CONFIG_FILE = os.path.join(CONFIG_DIR, "last_config.json")
LAST_PATH_FILE = os.path.join(CONFIG_DIR, "last_path.txt")
RESOURCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
