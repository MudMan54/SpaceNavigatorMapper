"""The README: right-click the "SpaceNavigator Mapper" title (v108.146).

The README is a PDF reference manual, SpaceNavigator_Mapper_README.pdf, built
from SpaceNavigator_Mapper_README.md by tools/build_readme_pdf.py. Both live
in the package's resources (the EXE build includes that folder) or, for the
single-file edition, inside the script.

A right-click on the title shows a drop-down with two choices:

* Open README (PDF): copies the PDF to the log folder
  (%LOCALAPPDATA%\\SpaceNavigatorMapper), where it outlives the EXE's
  temporary files, and opens it in the default PDF viewer. When there is no
  PDF or no viewer opens it, the README window opens instead.
* Open README in a window: the same README, from its Markdown, in a window
  of the Mapper, with a Text size choice from 100% to 250% (v108.150).
"""

import os
import re
import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCursor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from ..display_preferences import numeric_choice, update_preference
from ..paths import APP_DIR, RESOURCE_DIR
from ..version import VERSION
from .scaling import S

README_PDF = "SpaceNavigator_Mapper_README.pdf"
README_MD = "SpaceNavigator_Mapper_README.md"
TITLE = "SpaceNavigator Mapper — README"
PDF_CHOICE = "Open README (PDF)"
WINDOW_CHOICE = "Open README in a window"


def readme_candidates(name):
    """Where a README file may be: the package's resources, then the app's folder."""
    for folder in dict.fromkeys((RESOURCE_DIR, os.path.join(APP_DIR, "resources"), APP_DIR)):
        yield os.path.join(folder, name)


def _read(name, mode):
    """The first README file of that name that can be read, or None."""
    for path in readme_candidates(name):
        try:
            with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as stream:
                return stream.read()
        except OSError:
            continue
    return None


def readme_pdf_bytes():
    """The README PDF's bytes, or None when it cannot be found."""
    embedded = globals().get("_single_file_readme_pdf")  # set by the single-file loader
    return embedded or _read(README_PDF, "rb")


def readme_pdf_available():
    """True when the README PDF is inside the script or on disk."""
    if globals().get("_single_file_readme_pdf"):
        return True
    return any(os.path.isfile(path) for path in readme_candidates(README_PDF))


def readme_text():
    """The README's Markdown, or a short note when it cannot be found."""
    embedded = globals().get("_single_file_readme")  # set by the single-file loader
    text = embedded or _read(README_MD, "r")
    if text:
        return text
    return f"# {TITLE}\n\nThe README ({README_MD}) was not found beside the app."


def readme_copy_name():
    """The copy's file name: one per version, so an open older copy is never in the way."""
    return f"SpaceNavigator_Mapper_README_{VERSION}.pdf"


def readme_copy_dir():
    """The log folder, which outlives the EXE's temporary extraction folder."""
    from ..bootstrap import log_path

    return log_path().parent


def readme_pdf_path():
    """A PDF of the README that stays on disk, or None.

    The copy in the log folder is written when missing or different; copies
    of other versions there are removed. When the copy cannot be written, the
    PDF in the resources folder is used directly, if it is on disk.
    """
    data = readme_pdf_bytes()
    if not data:
        return None
    try:
        folder = readme_copy_dir()
        target = folder / readme_copy_name()
        if not target.is_file() or target.read_bytes() != data:
            temporary = target.with_name(target.name + ".tmp")
            temporary.write_bytes(data)
            os.replace(temporary, target)
        for old in folder.glob("SpaceNavigator_Mapper_README_*.pdf"):
            if old.name != target.name:
                try:
                    old.unlink()
                except OSError:
                    pass  # open in a viewer: removed next time
        return str(target)
    except OSError:
        for path in readme_candidates(README_PDF):
            if os.path.isfile(path):
                return path
        return None


def open_pdf(path):
    """Open `path` in the default PDF viewer; True when the request was accepted."""
    if sys.platform == "win32":
        try:
            os.startfile(path)  # type: ignore[attr-defined]
            return True
        except OSError:  # no program is associated with PDF files
            return False
    try:
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QDesktopServices

        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path)))))
    except Exception:
        return False


def window_text(markdown):
    """The Markdown without the HTML lines that only shape the PDF (comments, divs)."""
    return re.sub(r"(?m)^[ \t]*(<!--.*?-->|</?div\b[^>]*>)[ \t]*\n", "", markdown)


# The README window's text sizes (v108.150), remembered in ui_preferences.json.
TEXT_SIZES = (1.0, 1.25, 1.5, 1.75, 2.0, 2.5)
TEXT_SIZE_PREFERENCE = "readme_text_size"


class ReadmeBrowser(QTextBrowser):
    """The README text; Ctrl + plus / minus / 0 and Ctrl + wheel go to the window's Text size."""

    def __init__(self, viewer):
        """A browser whose zoom keys and Ctrl + wheel step the text size of `viewer`."""
        super().__init__(viewer)
        self.viewer = viewer

    def keyPressEvent(self, event):
        """Ctrl + plus / minus: next or previous text size; Ctrl + 0: 100%."""
        if event.modifiers() & Qt.ControlModifier:
            key = event.key()
            if key in (Qt.Key_Plus, Qt.Key_Equal):
                self.viewer.step_text_size(+1)
                return
            if key in (Qt.Key_Minus, Qt.Key_Underscore):
                self.viewer.step_text_size(-1)
                return
            if key == Qt.Key_0:
                self.viewer.set_text_size(1.0)
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Ctrl + wheel steps the text size; the wheel alone scrolls."""
        if event.modifiers() & Qt.ControlModifier:
            self.viewer.step_text_size(+1 if event.angleDelta().y() > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)


class ReadmeViewer(QDialog):
    """The README's Markdown in a window, with a choice of text sizes."""

    def __init__(self, parent=None):
        """Build the README window: Text size, the README, Close."""
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        try:  # no "?" button in the title bar
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        except (AttributeError, TypeError):
            pass
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Text size:"))
        self.size_box = QComboBox()
        self.size_box.addItems([f"{round(size * 100)}%" for size in TEXT_SIZES])
        self.size_box.setToolTip(
            "Larger or smaller README text. Ctrl + plus / minus and Ctrl + wheel work too."
        )
        top.addWidget(self.size_box)
        smaller = QPushButton("A−")
        smaller.setToolTip("Smaller text (Ctrl + minus)")
        smaller.clicked.connect(lambda _checked=False: self.step_text_size(-1))
        larger = QPushButton("A+")
        larger.setToolTip("Larger text (Ctrl + plus)")
        larger.clicked.connect(lambda _checked=False: self.step_text_size(+1))
        top.addWidget(smaller)
        top.addWidget(larger)
        top.addStretch(1)
        layout.addLayout(top)
        self.browser = ReadmeBrowser(self)
        self.browser.setOpenExternalLinks(True)
        self._base_font = QFont(self.browser.font())
        text = window_text(readme_text())
        try:
            self.browser.setMarkdown(text)
        except AttributeError:  # Qt before 5.14
            self.browser.setPlainText(text)
        layout.addWidget(self.browser)
        foot = QHBoxLayout()
        foot.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(lambda _checked=False: self.close())
        foot.addWidget(close)
        layout.addLayout(foot)
        self.setStyleSheet(
            "QDialog{background-color:#111827;color:#e2e8f0;}"
            "QTextBrowser{background:#0f172a;color:#e5e7eb;border:1px solid #334155;padding:8px;}"
        )
        self.resize(S(980), S(820))
        self.text_size = 1.0
        self.set_text_size(numeric_choice(TEXT_SIZE_PREFERENCE, TEXT_SIZES), remember=False)
        self.size_box.currentIndexChanged.connect(lambda index: self.set_text_size(TEXT_SIZES[index]))

    def set_text_size(self, size, remember=True):
        """Show the README text at `size` (1.0 = 100%), one of TEXT_SIZES; remembered for next time."""
        size = min(TEXT_SIZES, key=lambda choice: abs(choice - float(size)))
        self.text_size = size
        font = QFont(self._base_font)
        if self._base_font.pointSizeF() > 0:
            font.setPointSizeF(self._base_font.pointSizeF() * size)
        elif self._base_font.pixelSize() > 0:
            font.setPixelSize(max(1, round(self._base_font.pixelSize() * size)))
        self.browser.setFont(font)
        index = TEXT_SIZES.index(size)
        if self.size_box.currentIndex() != index:
            self.size_box.blockSignals(True)
            self.size_box.setCurrentIndex(index)
            self.size_box.blockSignals(False)
        if remember:
            try:
                update_preference(TEXT_SIZE_PREFERENCE, size)
            except OSError:
                pass  # still shown; just not remembered

    def step_text_size(self, steps):
        """The next larger (+1) or smaller (-1) text size."""
        index = TEXT_SIZES.index(self.text_size) + int(steps)
        self.set_text_size(TEXT_SIZES[max(0, min(len(TEXT_SIZES) - 1, index))])


def show_readme_window(win):
    """Open the README window, or bring it forward if it is already open."""
    viewer = getattr(win, "_readme_viewer", None)
    if viewer is None:
        viewer = win._readme_viewer = ReadmeViewer(win)
    viewer.show()
    viewer.raise_()
    viewer.activateWindow()
    return viewer


def _status(win, message):
    """Show a message in the status bar for a few seconds."""
    try:
        win.statusBar().showMessage(message, 4000)
    except (AttributeError, RuntimeError):
        pass


def show_readme_pdf(win):
    """Open the README PDF in the PDF viewer, else the README window."""
    path = readme_pdf_path()
    if path and open_pdf(path):
        win._readme_pdf = path
        _status(win, "README opened in your PDF viewer")
        return path
    _status(win, "The README PDF could not be opened; showing it here")
    return show_readme_window(win)


def readme_menu(win):
    """The title's drop-down: the README as a PDF, or in a window."""
    menu = QMenu(win)
    menu.setToolTipsVisible(True)
    pdf = menu.addAction(PDF_CHOICE)
    available = readme_pdf_available()
    pdf.setEnabled(available)
    pdf.setToolTip(
        "Open the README in your PDF viewer." if available else "The README PDF was not found beside the app."
    )
    pdf.triggered.connect(lambda _checked=False: show_readme_pdf(win))
    window = menu.addAction(WINDOW_CHOICE)
    window.setToolTip("Read the same README here, in a window of the Mapper.")
    window.triggered.connect(lambda _checked=False: show_readme_window(win))
    return menu


def show_readme_menu(win, pos=None):
    """Right-click on the title: show the README drop-down at the pointer."""
    menu = win._readme_menu = readme_menu(win)  # kept alive while it is open
    menu.exec_(pos if pos is not None else QCursor.pos())
    return menu
