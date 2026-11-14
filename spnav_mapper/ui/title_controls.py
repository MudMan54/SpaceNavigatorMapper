"""Title fit helpers (v108.84).

The title is a styled QLabel in the menu bar's corner. Without a fixed width
its styled background can stretch far past the text. Only its geometry is
changed; the rainbow overlay follows it.
"""


def title_button_width(text_width, horizontal_padding=6, border=1, slack=4):
    """Return text width plus CSS padding, borders, and an italic-font margin."""
    return max(1, int(text_width) + 2 * int(horizontal_padding) + 2 * int(border) + int(slack))


def fit_full_editor_title_label(label):
    """Constrain a styled QLabel to its actual text width.

    Call after the editor stylesheet has been installed. Qt's
    effective font metrics then reflect the user's saved font scale.
    No animations or layouts are replaced.
    """
    from PyQt5.QtWidgets import QSizePolicy

    try:
        label.ensurePolished()
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        label.setFixedWidth(title_button_width(label.fontMetrics().horizontalAdvance(label.text())))
    except (RuntimeError, AttributeError, TypeError, ValueError):
        pass
