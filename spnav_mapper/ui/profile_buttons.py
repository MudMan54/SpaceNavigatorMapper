"""The row of Target, Save/Reload, Save as and Load under the profile name (v108.165).

Save/Reload, Save as and Load are the same width and end where the profile
name box ends; the space under the Auto Load selector is left empty. Target
keeps the width it had: two fifths of the row (less the gaps), or its text
width at the smallest Display size.

The widths are given as the row's stretch factors, recomputed whenever the
row or the Auto Load selector changes size; the empty space is a stretch item
with no size of its own. Stretch factors change no size hint, so the editor's
own size is not affected.
"""

from PyQt5.QtCore import QEvent, QObject
from PyQt5.QtWidgets import QSizePolicy

BUTTONS = 3  # Save/Reload, Save as, Load


def profile_button_widths(row_width, spacing, beside_width, target_width=None):
    """(Target, each of the three) widths for a row `row_width` wide.

    `beside_width` is the Auto Load selector's width: the three buttons end
    `beside_width` plus one gap before the row's end, where the profile name
    box ends. Without `target_width`, Target is two fifths of the row less its
    three gaps, as before v108.165.
    """
    if target_width is None:
        target_width = round(2 * (row_width - BUTTONS * spacing) / 5)
    room = row_width - beside_width - (BUTTONS + 1) * spacing - target_width
    return int(target_width), max(1, int(room // BUTTONS))


class ProfileButtonRow(QObject):
    """Keeps the row's widths as profile_button_widths() says."""

    def __init__(self, column, row, target, buttons, beside, compact=False):
        """Lay out `target` and `buttons` in `row`, leaving `beside`'s width empty at its end."""
        super().__init__(column)
        self.column, self.row, self.target = column, row, target
        self.buttons, self.beside, self.compact = tuple(buttons), beside, compact
        row.addWidget(target, 0 if compact else 2)
        for button in self.buttons:
            if compact:
                # Before v108.165 they kept their text width at the smallest size.
                button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            row.addWidget(button, 1)
        # The empty space under the Auto Load selector (and the gap before it):
        # a stretch, so it has no size of its own and no layout gap beside it;
        # the header is no wider than before.
        row.addStretch(0)
        for widget in (column, beside):
            widget.installEventFilter(self)
        self.apply()

    def eventFilter(self, obj, event):
        """The row or the Auto Load selector changed size: share the room again."""
        if event.type() == QEvent.Resize:
            self.apply()
        return False

    def stretches(self, row_width):
        """[Target, Save/Reload, Save as, Load, the empty space and its gap]: the row's stretch factors."""
        beside = self.beside.width() if self.beside.isVisible() else self.beside.sizeHint().width()
        spacing = self.row.spacing()
        if self.compact:  # Target: its text width (stretch 0)
            target, each = profile_button_widths(row_width, spacing, beside, self.target.sizeHint().width())
            return [0, each, each, each, beside + spacing]
        target, each = profile_button_widths(row_width, spacing, beside)
        return [max(1, target), each, each, each, beside + spacing]

    def apply(self):
        """Set the five stretch factors for the row's width now."""
        try:
            margins = self.column.layout().contentsMargins()
            row_width = self.column.width() - margins.left() - margins.right()
            if row_width <= 0:
                return
            for index, stretch in enumerate(self.stretches(row_width)):
                self.row.setStretch(index, stretch)
        except RuntimeError:  # the window is being destroyed
            pass
