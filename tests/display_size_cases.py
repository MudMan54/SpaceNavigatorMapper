"""Start the Mapper at one Display size under the fakes; print its fonts and control heights (v108.154).

python tests/display_size_cases.py <repo root> <Display factor>
"""

import json
import os
import shutil
import sys
import tempfile

ROOT, FACTOR = sys.argv[1], float(sys.argv[2])
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fakeqt  # noqa: E402
from fakeqt import QFont, QRect, QScreen  # noqa: E402

SBX = tempfile.mkdtemp(prefix="spnav-display-")
os.makedirs(SBX + "/configs")
os.makedirs(SBX + "/logs")
os.environ["LOCALAPPDATA"] = SBX + "/logs"
for name in ("QT_SCREEN_SCALE_FACTORS", "SPNAV_AUTO_SCREEN_FACTORS", "SPNAV_UI_SCALE"):
    os.environ.pop(name, None)
shutil.copytree(os.path.join(ROOT, "spnav_mapper"), os.path.join(SBX, "spnav_mapper"))
shutil.copy(os.path.join(ROOT, "main.py"), os.path.join(SBX, "main.py"))
with open(SBX + "/configs/ui_preferences.json", "w", encoding="utf-8") as stream:
    json.dump({"ui_scale_factor": FACTOR}, stream)

# 1920 x 1080 at 100%, Qt's usual default font.
env = fakeqt.install([QScreen(r"\\.\DISPLAY1", QRect(0, 0, 1920, 1080), QRect(0, 0, 1920, 1032))])
env.win32.monitors = [(r"\\.\DISPLAY1", 0, 0, 1920, 1080, 1032, 96, True)]
default = QFont("MS Shell Dlg 2")
default.setPointSizeF(8.0)
fakeqt.QCoreApplication._app_font = default
result = {}


def session(app):
    win = env.main_window()
    env.advance(1500)
    panel = win.axes["X"]
    bar = win.menuBar()
    result.update(
        {
            "text": round(fakeqt.QCoreApplication._app_font.pointSizeF(), 2),
            "menu bar headings": round(bar.font().pointSizeF(), 2),
            "menus": sorted({round(a.menu().font().pointSizeF(), 2) for a in bar.actions() if a.menu()}),
            "heights": {
                "Bind button": panel.slot_btns[0].maximumHeight(),
                "comment": panel.slot_comments[0].maximumHeight(),
                "Bind Dir box": panel.qb_dir.maximumHeight(),
                "Mode box": panel.qb_mode.maximumHeight(),
                "- / + button": panel.dead_inc.maximumHeight(),
                "Button 1": win.key1_btn.maximumHeight(),
            },
        }
    )


env.session = session
sys.argv = [os.path.join(SBX, "main.py")]
os.chdir(SBX)
sys.path.insert(0, SBX)
try:
    from spnav_mapper.bootstrap import launch

    launch()
except SystemExit:
    pass
print(json.dumps(result))
