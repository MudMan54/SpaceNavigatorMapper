"""Application constants shared by UI, device and profile code."""

import os

from .version import REVISION_DATE, VERSION  # noqa: F401  (re-exported)

AXES = ["X", "Y", "Z", "Rx", "Ry", "Rz"]
BINDS_PER_AXIS = 6  # All six axes support Bind #1 through Bind #6.
POLL_MS = 8
GUI_MS = 16
# v108.167: the shortest time a tapped key is up before it is pressed again
# (taps and macros): a game that reads its keys 60 times a second sees it.
MIN_KEY_UP_MS = 30
TITLE_LINE1 = "SpaceNavigator Mapper"
TITLE_LINE2 = "Logic by: Don Muddiman"


def ensure_dir(p):
    """Create a folder (and its parents) when missing."""
    os.makedirs(p, exist_ok=True)
