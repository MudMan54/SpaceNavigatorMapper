"""A recording stand-in for PyQt5, Win32, the registry and a HID SpaceNavigator.

It lets the whole Mapper start, run and be driven from tests on any OS, with
virtual time. It is not a Qt emulator: layouts do not lay anything out and
sizes are fixed, deterministic numbers. What it keeps is *state* (texts,
check marks, styles, sizes, menus, timers, the widget tree) and *effects*
(keys sent through SendInput, LED reports, message boxes, launched
processes, registry writes), so two versions of the app can be compared.

Use:  env = fakeqt.install(); ...import the app...; env.advance(500)
"""

import builtins
import ctypes
import inspect
import sys
import types
import zlib

# --------------------------------------------------------------------------
# Virtual time
# --------------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.ms = 0.0
        self.calls = []  # (due_ms, seq, fn)
        self.seq = 0
        self.timers = []  # live QTimer objects

    def perf_counter(self):
        return self.ms / 1000.0

    def time(self):
        return 1_800_000_000.0 + self.ms / 1000.0

    def sleep(self, seconds):
        self.ms += max(0.0, float(seconds)) * 1000.0

    def later(self, ms, fn):
        self.seq += 1
        self.calls.append((self.ms + max(0, int(ms)), self.seq, fn))

    def advance(self, ms, step=1.0):
        end = self.ms + ms
        while True:
            nxt = self._next_due()
            if nxt is None or nxt > end:
                break
            self.ms = max(self.ms, nxt)
            self._fire_due()
        self.ms = end

    def _next_due(self):
        dues = [c[0] for c in self.calls]
        dues += [t._due for t in self.timers if t._active]
        return min(dues) if dues else None

    def _fire_due(self):
        due = [c for c in self.calls if c[0] <= self.ms]
        due.sort(key=lambda c: (c[0], c[1]))
        for c in due:
            self.calls.remove(c)
        for _, _, fn in due:
            _guard(fn)
        for t in sorted(
            (t for t in self.timers if t._active and t._due <= self.ms), key=lambda t: (t._due, t._oid)
        ):
            if not t._active or t._due > self.ms:
                continue
            if t._single:
                t._active = False
            else:
                t._due = self.ms + max(1, t._interval)
            t.timeout.emit()


CLOCK = Clock()
EFFECTS = []  # external effects, in order
ERRORS = []  # exceptions escaping Qt callbacks (would print in real Qt)


def effect(kind, *details):
    EFFECTS.append((round(CLOCK.ms), kind) + tuple(details))


def _guard(fn, *args):
    try:
        return fn(*args)
    except SystemExit:
        raise
    except BaseException as exc:  # PyQt prints and continues; record it.
        import traceback

        ERRORS.append(
            "".join(traceback.format_exception_only(type(exc), exc)).strip()
            + " @ "
            + traceback.extract_tb(exc.__traceback__)[-1].name
        )
        return None


# --------------------------------------------------------------------------
# Enums and plain value types
# --------------------------------------------------------------------------


class Enum(int):
    def __new__(cls, name):
        obj = int.__new__(cls, zlib.crc32(name.encode()) & 0x7FFFFFFF)
        obj._name = name
        return obj

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Enum(self._name + "." + name)

    def __or__(self, other):
        return Flag(int(self) | int(other))

    __ror__ = __or__

    def __and__(self, other):
        return int(self) & int(other)

    def __repr__(self):
        return self._name


class Flag(int):
    def __or__(self, other):
        return Flag(int(self) | int(other))

    __ror__ = __or__


class EnumSpace:
    def __init__(self, prefix=""):
        self._prefix = prefix

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Enum(self._prefix + name)


class QPoint:
    def __init__(self, x=0, y=0):
        self._x, self._y = int(x), int(y)

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __add__(self, o):
        return QPoint(self._x + o.x(), self._y + o.y())

    def __sub__(self, o):
        return QPoint(self._x - o.x(), self._y - o.y())

    def __eq__(self, o):
        return isinstance(o, QPoint) and (self._x, self._y) == (o._x, o._y)

    def __repr__(self):
        return f"QPoint({self._x},{self._y})"


class QSize:
    def __init__(self, w=0, h=0):
        self._w, self._h = int(w), int(h)

    def width(self):
        return self._w

    def height(self):
        return self._h

    def setWidth(self, v):
        self._w = int(v)

    def setHeight(self, v):
        self._h = int(v)

    def isValid(self):
        return self._w >= 0 and self._h >= 0

    def expandedTo(self, o):
        return QSize(max(self._w, o.width()), max(self._h, o.height()))

    def boundedTo(self, o):
        return QSize(min(self._w, o.width()), min(self._h, o.height()))

    def __eq__(self, o):
        return isinstance(o, QSize) and (self._w, self._h) == (o._w, o._h)

    def __repr__(self):
        return f"QSize({self._w},{self._h})"


class QMargins:
    def __init__(self, l=0, t=0, r=0, b=0):
        self._m = (int(l), int(t), int(r), int(b))

    def left(self):
        return self._m[0]

    def top(self):
        return self._m[1]

    def right(self):
        return self._m[2]

    def bottom(self):
        return self._m[3]


class QRect:
    def __init__(self, *a):
        if len(a) == 4:
            self._r = tuple(int(v) for v in a)
        elif len(a) == 2 and isinstance(a[0], QPoint):
            self._r = (a[0].x(), a[0].y(), a[1].width(), a[1].height())
        else:
            self._r = (0, 0, 0, 0)

    def x(self):
        return self._r[0]

    def y(self):
        return self._r[1]

    def left(self):
        return self._r[0]

    def top(self):
        return self._r[1]

    def width(self):
        return self._r[2]

    def height(self):
        return self._r[3]

    def right(self):
        return self._r[0] + self._r[2] - 1

    def bottom(self):
        return self._r[1] + self._r[3] - 1

    def size(self):
        return QSize(self._r[2], self._r[3])

    def topLeft(self):
        return QPoint(self._r[0], self._r[1])

    def center(self):
        return QPoint(self._r[0] + self._r[2] // 2, self._r[1] + self._r[3] // 2)

    def isValid(self):
        return self._r[2] > 0 and self._r[3] > 0

    def isEmpty(self):
        return not self.isValid()

    def setLeft(self, v):
        self._r = (int(v), self._r[1], self._r[2] + self._r[0] - int(v), self._r[3])

    def setWidth(self, v):
        self._r = (self._r[0], self._r[1], int(v), self._r[3])

    def contains(self, *a):
        p = a[0] if len(a) == 1 else QPoint(*a)
        return self._r[0] <= p.x() < self._r[0] + self._r[2] and self._r[1] <= p.y() < self._r[1] + self._r[3]

    def adjusted(self, dl, dt, dr, db):
        x, y, w, h = self._r
        return QRect(x + dl, y + dt, w - dl + dr, h - dt + db)

    def intersected(self, o):
        x1, y1 = max(self.x(), o.x()), max(self.y(), o.y())
        x2 = min(self.x() + self.width(), o.x() + o.width())
        y2 = min(self.y() + self.height(), o.y() + o.height())
        return QRect(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def translated(self, *a):
        p = a[0] if len(a) == 1 else QPoint(*a)
        return QRect(self._r[0] + p.x(), self._r[1] + p.y(), self._r[2], self._r[3])

    def __eq__(self, o):
        return isinstance(o, QRect) and self._r == o._r

    def __repr__(self):
        return "QRect(%d,%d,%d,%d)" % self._r


QRectF = QRect
QPointF = QPoint


class QFont:
    def __init__(self, family="Segoe UI", size=9, *a):
        if isinstance(family, QFont):
            self.__dict__.update(family.__dict__)
            return
        self._family, self._pt, self._px = str(family), float(size), -1
        self._italic = self._bold = False
        self._weight = 50

    def family(self):
        return self._family

    def setFamily(self, f):
        self._family = str(f)

    def pointSize(self):
        return int(round(self._pt)) if self._pt > 0 else -1

    def pointSizeF(self):
        return self._pt if self._pt > 0 else -1.0

    def setPointSize(self, v):
        self._pt, self._px = float(int(v)), -1

    def setPointSizeF(self, v):
        self._pt, self._px = float(v), -1

    def pixelSize(self):
        return self._px

    def setPixelSize(self, v):
        self._px, self._pt = int(v), -1

    def italic(self):
        return self._italic

    def setItalic(self, v):
        self._italic = bool(v)

    def bold(self):
        return self._bold

    def setBold(self, v):
        self._bold = bool(v)

    def weight(self):
        return self._weight

    def setWeight(self, v):
        self._weight = int(v)

    def setStyleStrategy(self, *a):
        pass

    def setLetterSpacing(self, *a):
        pass

    def _px_height(self):
        return self._px if self._px > 0 else max(1, round(self._pt * 96 / 72))

    def key(self):
        return (self._family, round(self._pt, 2), self._px, self._italic, self._bold, self._weight)


class QFontMetrics:
    def __init__(self, font, *a):
        self._f = font if isinstance(font, QFont) else QFont()

    def height(self):
        return int(self._f._px_height() * 1.25) + 1

    def lineSpacing(self):
        return self.height() + 1

    def ascent(self):
        return int(self._f._px_height())

    def descent(self):
        return self.height() - self.ascent()

    def averageCharWidth(self):
        return max(1, int(self._f._px_height() * 0.55))

    def horizontalAdvance(self, text, *a):
        return int(len(str(text)) * self._f._px_height() * 0.55 + 0.5)

    width = horizontalAdvance

    def boundingRect(self, *a):
        text = a[-1] if a and isinstance(a[-1], str) else ""
        return QRect(0, 0, self.horizontalAdvance(text), self.height())

    def elidedText(self, text, mode, width, *a):
        return text


QFontMetricsF = QFontMetrics


class QColor:
    def __init__(self, *a):
        self._v = a

    @staticmethod
    def fromHsv(*a):
        return QColor(*a)

    def name(self):
        return "#%s" % (self._v,)

    def setAlpha(self, *a):
        pass

    def lighter(self, *a):
        return self

    def darker(self, *a):
        return self


class QKeySequence(str):
    pass


# --------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------


def _accepted_args(fn, args):
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return args
    n = 0
    for p in sig.parameters.values():
        if p.kind == p.VAR_POSITIONAL:
            return args
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
            n += 1
    return args[:n]


class Signal:
    def __init__(self, owner=None, name=""):
        self._owner, self._name, self._slots = owner, name, []

    def connect(self, fn, *a, **k):
        self._slots.append(fn)

    def disconnect(self, fn=None):
        if fn is None:
            if not self._slots:
                raise TypeError("disconnect() failed between '%s' and all its connections" % self._name)
            self._slots.clear()
        else:
            try:
                self._slots.remove(fn)
            except ValueError:
                raise TypeError("not connected")

    def emit(self, *args):
        if self._owner is not None and getattr(self._owner, "_blocked", False):
            return
        for fn in list(self._slots):
            _guard(fn, *_accepted_args(fn, args))

    def __getitem__(self, key):  # sig[int].connect(...)
        return self


class pyqtSignal:
    def __init__(self, *types_, **k):
        self._types = types_

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        store = obj.__dict__.setdefault("_signals", {})
        if self._name not in store:
            store[self._name] = Signal(obj, self._name)
        return store[self._name]


def pyqtSlot(*a, **k):
    return lambda fn: fn


# --------------------------------------------------------------------------
# Object / widget base
# --------------------------------------------------------------------------

_SIGNAL_NAMES = {
    "clicked",
    "pressed",
    "released",
    "toggled",
    "triggered",
    "textChanged",
    "textEdited",
    "editingFinished",
    "returnPressed",
    "currentIndexChanged",
    "currentTextChanged",
    "activated",
    "timeout",
    "valueChanged",
    "stateChanged",
    "aboutToShow",
    "aboutToHide",
    "screenChanged",
    "modeChanged",
    "doubleClicked",
    "applicationStateChanged",
    "hovered",
    "destroyed",
    "currentChanged",
    "messageClicked",
    "screenAdded",
    "screenRemoved",
    "primaryScreenChanged",
    "geometryChanged",
    "logicalDotsPerInchChanged",
    "currentRowChanged",
    "itemDoubleClicked",
}

_OIDS = [0]


class _Meta(type):
    def __getattr__(cls, name):
        if name[:1].isupper() or name.startswith(("PM_", "SH_", "SE_", "CC_", "SC_", "PE_", "CE_")):
            return Enum(cls.__name__ + "." + name)
        raise AttributeError(name)


class QObject(metaclass=_Meta):
    def __init__(self, *args, **kwargs):
        _OIDS[0] += 1
        self._oid = _OIDS[0]
        self._blocked = False
        self._props = {}
        self._filters = []
        self._name = ""
        self._qparent = None
        self._kids = []
        parent = kwargs.get("parent")
        if parent is None:
            for a in args:
                if isinstance(a, QObject):
                    parent = a
                    break
        if parent is not None:
            self.setParent(parent)

    def __getattr__(self, name):
        if name in _SIGNAL_NAMES:
            store = self.__dict__.setdefault("_signals", {})
            if name not in store:
                store[name] = Signal(self, name)
            return store[name]
        raise AttributeError("%s has no attribute %r" % (type(self).__name__, name))

    def setParent(self, parent, *a):
        old = self.__dict__.get("_qparent")
        if old is not None and self in old._kids:
            old._kids.remove(self)
        self._qparent = parent
        if parent is not None and self not in parent._kids:
            parent._kids.append(self)

    def parent(self):
        return self._qparent

    def children(self):
        return list(self._kids)

    def blockSignals(self, b):
        old, self._blocked = self._blocked, bool(b)
        return old

    def signalsBlocked(self):
        return self._blocked

    def setObjectName(self, n):
        self._name = str(n)

    def objectName(self):
        return self._name

    def setProperty(self, k, v):
        self._props[k] = v
        return True

    def property(self, k):
        return self._props.get(k)

    def installEventFilter(self, f):
        self._filters.append(f)

    def removeEventFilter(self, f):
        if f in self._filters:
            self._filters.remove(f)

    def deleteLater(self):
        self._deleted = True

    def thread(self):
        return None

    def startTimer(self, *a):
        return 1

    def killTimer(self, *a):
        pass

    def findChildren(self, cls, *a):
        out = []
        for k in self._kids:
            if isinstance(k, cls):
                out.append(k)
            out.extend(k.findChildren(cls))
        return out

    def findChild(self, cls, name=""):
        for k in self.findChildren(cls):
            if not name or k.objectName() == name:
                return k
        return None

    def event(self, e):
        return False

    def eventFilter(self, o, e):
        return False


class QEvent(metaclass=_Meta):
    def __init__(self, kind=None):
        self._type = kind
        self._accepted = True

    def type(self):
        return self._type

    def accept(self):
        self._accepted = True

    def ignore(self):
        self._accepted = False

    def isAccepted(self):
        return self._accepted

    def setAccepted(self, v):
        self._accepted = bool(v)

    def spontaneous(self):
        return False


QCloseEvent = QEvent


def send_event(obj, kind_name):
    """Deliver an event of QEvent.<kind_name> to obj's event filters."""
    ev = QEvent(getattr(QEvent, kind_name))
    for f in list(getattr(obj, "_filters", [])):
        _guard(f.eventFilter, obj, ev)
    return ev


class QWidget(QObject):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._layout = None
        self._visible_flag = None  # None = not explicitly shown/hidden
        self._enabled = True
        self._geom = QRect(0, 0, 640, 480)
        self._min = QSize(0, 0)
        self._max = QSize(16777215, 16777215)
        self._style = ""
        self._tip = ""
        self._font = None
        self._title = ""
        self._policy = None
        self._attrs = {}
        self._flags = Flag(0)
        self._cursor = None
        self._focus = None
        self._icon = None
        self._margins = QMargins()
        self._handle = None
        self._palette = QPalette()

    # visibility
    def show(self):
        self._visible_flag = True
        if self.isWindow():
            send_event(self, "Show")

    def hide(self):
        self._visible_flag = False

    def setVisible(self, v):
        (self.show if v else self.hide)()

    def setHidden(self, v):
        self.setVisible(not v)

    def isHidden(self):
        return self._visible_flag is False or (self.isWindow() and not self._visible_flag)

    def isVisible(self):
        if self._visible_flag is False:
            return False
        if self.isWindow():
            return bool(self._visible_flag)
        p = self._qparent
        while p is not None and not isinstance(p, QWidget):
            p = p._qparent
        return bool(p.isVisible()) if p is not None else False

    def isVisibleTo(self, *a):
        return self._visible_flag is not False

    def isWindow(self):
        return self._qparent is None or isinstance(self, (QMainWindow, QDialog))

    def window(self):
        w = self
        while w._qparent is not None and not w.isWindow():
            w = w._qparent
        return w

    def parentWidget(self):
        p = self._qparent
        return p if isinstance(p, QWidget) else None

    def close(self):
        ev = QEvent(QEvent.Close)
        handler = getattr(self, "closeEvent", None)
        if handler is not None:
            _guard(handler, ev)
        if ev.isAccepted():
            self.hide()
            effect("window-closed", type(self).__name__)
        return ev.isAccepted()

    def closeEvent(self, ev):
        ev.accept()

    # enabled / style / text-ish
    def setEnabled(self, v):
        self._enabled = bool(v)

    def setDisabled(self, v):
        self._enabled = not v

    def isEnabled(self):
        return self._enabled

    def setStyleSheet(self, s):
        self._style = str(s)

    def styleSheet(self):
        return self._style

    def setToolTip(self, s):
        self._tip = str(s)

    def toolTip(self):
        return self._tip

    def setWindowTitle(self, s):
        self._title = str(s)

    def windowTitle(self):
        return self._title

    def setFont(self, f):
        self._font = QFont(f)

    def font(self):
        if self._font is not None:
            return QFont(self._font)
        p = self.parentWidget()
        if p is not None:
            return p.font()
        return QFont(QApplication._app_font)

    def fontMetrics(self):
        return QFontMetrics(self.font())

    def setPalette(self, p):
        self._palette = p

    def palette(self):
        return self._palette

    def setCursor(self, c):
        self._cursor = c

    def setFocusPolicy(self, p):
        self._focus = p

    def focusPolicy(self):
        return self._focus

    def setAttribute(self, a, on=True):
        self._attrs[int(a)] = bool(on)

    def testAttribute(self, a):
        return self._attrs.get(int(a), False)

    def setWindowFlags(self, f):
        self._flags = f

    def overrideWindowFlags(self, f):
        self._flags = f
        FLAG_CHANGES.append((self, int(f)))

    def nativeEvent(self, event_type, message):
        return False, 0

    def windowFlags(self):
        return self._flags

    def setWindowIcon(self, i):
        self._icon = i

    def windowIcon(self):
        return self._icon if self._icon is not None else QIcon()

    def setMouseTracking(self, *a):
        pass

    def setAutoFillBackground(self, *a):
        pass

    def setAccessibleName(self, *a):
        pass

    def setAccessibleDescription(self, *a):
        pass

    def setContextMenuPolicy(self, *a):
        pass

    def setAcceptDrops(self, *a):
        pass

    def setFocus(self, *a):
        pass

    def clearFocus(self):
        pass

    def hasFocus(self):
        return False

    def grabMouse(self):
        pass

    def releaseMouse(self):
        pass

    # geometry
    def setGeometry(self, *a):
        self._geom = a[0] if len(a) == 1 else QRect(*a)
        effect_geom(self)

    def geometry(self):
        return QRect(*self._geom._r)

    def frameGeometry(self):
        g = self._geom
        return (
            QRect(g.x() - 8, g.y() - 31, g.width() + 16, g.height() + 39)
            if self.isWindow()
            else self.geometry()
        )

    def normalGeometry(self):
        return self.geometry()

    def rect(self):
        return QRect(0, 0, self._geom.width(), self._geom.height())

    def width(self):
        return self._geom.width()

    def height(self):
        return self._geom.height()

    def x(self):
        return self._geom.x()

    def y(self):
        return self._geom.y()

    def pos(self):
        return QPoint(self._geom.x(), self._geom.y())

    def size(self):
        return QSize(self._geom.width(), self._geom.height())

    def resize(self, *a):
        s = a[0] if len(a) == 1 else QSize(*a)
        w = max(self._min.width(), min(self._max.width(), s.width()))
        h = max(self._min.height(), min(self._max.height(), s.height()))
        self._geom = QRect(self._geom.x(), self._geom.y(), w, h)
        effect_geom(self)

    def move(self, *a):
        p = a[0] if len(a) == 1 else QPoint(*a)
        self._geom = QRect(p.x(), p.y(), self._geom.width(), self._geom.height())

    def adjustSize(self):
        pass

    def updateGeometry(self):
        pass

    def update(self, *a):
        pass

    def repaint(self, *a):
        pass

    def raise_(self):
        pass

    def lower(self):
        pass

    def activateWindow(self):
        pass

    def isActiveWindow(self):
        return False

    def mapToGlobal(self, p):
        return QPoint(p.x() + self.x(), p.y() + self.y())

    def mapFromGlobal(self, p):
        return QPoint(p.x() - self.x(), p.y() - self.y())

    def mapTo(self, w, p):
        return QPoint(p.x(), p.y())

    def mapFrom(self, w, p):
        return QPoint(p.x(), p.y())

    def childAt(self, *a):
        return None

    def setMinimumSize(self, *a):
        s = a[0] if len(a) == 1 else QSize(*a)
        self._min = QSize(s.width(), s.height())

    def setMaximumSize(self, *a):
        s = a[0] if len(a) == 1 else QSize(*a)
        self._max = QSize(s.width(), s.height())

    def setMinimumWidth(self, v):
        self._min = QSize(int(v), self._min.height())

    def setMinimumHeight(self, v):
        self._min = QSize(self._min.width(), int(v))

    def setMaximumWidth(self, v):
        self._max = QSize(int(v), self._max.height())

    def setMaximumHeight(self, v):
        self._max = QSize(self._max.width(), int(v))

    def setFixedWidth(self, v):
        self.setMinimumWidth(v)
        self.setMaximumWidth(v)

    def setFixedHeight(self, v):
        self.setMinimumHeight(v)
        self.setMaximumHeight(v)

    def setFixedSize(self, *a):
        s = a[0] if len(a) == 1 else QSize(*a)
        self.setMinimumSize(s)
        self.setMaximumSize(s)

    def minimumSize(self):
        return QSize(self._min.width(), self._min.height())

    def maximumSize(self):
        return QSize(self._max.width(), self._max.height())

    def minimumWidth(self):
        return self._min.width()

    def minimumHeight(self):
        return self._min.height()

    def maximumWidth(self):
        return self._max.width()

    def maximumHeight(self):
        return self._max.height()

    def setSizePolicy(self, *a):
        self._policy = tuple(a)

    def sizePolicy(self):
        return QSizePolicy(*(self._policy or ()))

    def setContentsMargins(self, *a):
        self._margins = a[0] if len(a) == 1 else QMargins(*a)

    def contentsMargins(self):
        return self._margins

    def sizeHint(self):
        if self._layout is not None:
            return self._layout.sizeHint()
        return QSize(max(self._min.width(), 80), max(self._min.height(), 24))

    def minimumSizeHint(self):
        return QSize(self._min.width(), self._min.height())

    # layout / tree
    def setLayout(self, lay):
        self._layout = lay
        lay._owner = self
        for w in lay._widgets():
            w.setParent(self)

    def layout(self):
        return self._layout

    def ensurePolished(self):
        pass

    def style(self):
        return QStyle()

    def winId(self):
        self.windowHandle()
        return 0x1000 + self._oid

    def effectiveWinId(self):
        return self.winId()

    def windowHandle(self):
        if self.isWindow() and self._handle is None:
            self._handle = QWindow(self)
        return self._handle

    def screen(self):
        h = self.windowHandle()
        return h.screen() if h else QApplication._screens[0]

    def grab(self, *a):
        return QPixmap()

    def render(self, *a):
        pass

    def setUpdatesEnabled(self, *a):
        pass

    def mousePressEvent(self, e):
        pass

    def mouseReleaseEvent(self, e):
        pass

    def mouseDoubleClickEvent(self, e):
        pass

    def enterEvent(self, e):
        pass

    def leaveEvent(self, e):
        pass

    def paintEvent(self, e):
        pass

    def resizeEvent(self, e):
        pass

    def showEvent(self, e):
        pass

    def hideEvent(self, e):
        pass

    def moveEvent(self, e):
        pass

    def changeEvent(self, e):
        pass

    def keyPressEvent(self, e):
        pass

    def wheelEvent(self, e):
        pass

    def contextMenuEvent(self, e):
        pass

    def focusInEvent(self, e):
        pass

    def focusOutEvent(self, e):
        pass

    def initPainter(self, *a):
        pass


def effect_geom(w):
    pass  # geometry is captured in snapshots, not as an effect


class QWindow(QObject):
    def __init__(self, widget=None):
        super().__init__()
        self._widget = widget
        self._screen = QApplication._screens[0]

    def screen(self):
        return self._screen

    def setScreen(self, s):
        if s is not self._screen:
            self._screen = s
            self.screenChanged.emit(s)

    def setFlags(self, f):
        self._flags = f

    def flags(self):
        return getattr(self, "_flags", Flag(0))

    def frameMargins(self):
        return QMargins(8, 31, 8, 8)

    def devicePixelRatio(self):
        return self._screen.devicePixelRatio()


class QScreen(QObject):
    def __init__(self, name, geom, avail, dpi=96.0, dpr=1.0, serial=""):
        super().__init__()
        self._n, self._g, self._a, self._dpi, self._dpr, self._serial = name, geom, avail, dpi, dpr, serial

    def name(self):
        return self._n

    def geometry(self):
        return QRect(*self._g._r)

    def availableGeometry(self):
        return QRect(*self._a._r)

    def virtualGeometry(self):
        return QRect(*self._g._r)

    def logicalDotsPerInch(self):
        return self._dpi

    def physicalDotsPerInch(self):
        return 96.0

    def devicePixelRatio(self):
        return self._dpr

    def serialNumber(self):
        return self._serial

    def manufacturer(self):
        return "Fake"

    def model(self):
        return self._n

    def size(self):
        return self._g.size()


class QPalette(metaclass=_Meta):
    def __init__(self, *a):
        self._c = {}

    def setColor(self, *a):
        self._c[a[-2] if len(a) > 1 else 0] = a[-1]

    def color(self, *a):
        return QColor()

    def setBrush(self, *a):
        pass

    def brush(self, *a):
        return QBrush()


class QIcon:
    def __init__(self, *a):
        self._src = a[0] if a and isinstance(a[0], str) else None

    def isNull(self):
        return False

    def pixmap(self, *a):
        return QPixmap()

    def addPixmap(self, *a):
        pass

    def addFile(self, *a):
        pass


class QPixmap(QIcon):
    def loadFromData(self, *a):
        return True

    def load(self, *a):
        return True

    def width(self):
        return 32

    def height(self):
        return 32

    def scaled(self, *a, **k):
        return self

    def fill(self, *a):
        pass

    def save(self, *a):
        return True

    def setDevicePixelRatio(self, *a):
        pass


QImage = QPixmap


class QBrush:
    def __init__(self, *a):
        pass


class QPen:
    def __init__(self, *a):
        pass

    def setWidth(self, *a):
        pass

    def setStyle(self, *a):
        pass

    def setWidthF(self, *a):
        pass

    def setCapStyle(self, *a):
        pass

    def setJoinStyle(self, *a):
        pass

    def setColor(self, *a):
        pass

    def setCosmetic(self, *a):
        pass


class _Gradient:
    def __init__(self, *a):
        pass

    def setColorAt(self, *a):
        pass

    def setAngle(self, *a):
        pass

    def setCenter(self, *a):
        pass


QConicalGradient = QLinearGradient = QRadialGradient = _Gradient


class QPainterPath:
    def __init__(self, *a):
        pass

    def addRoundedRect(self, *a):
        pass

    def addRect(self, *a):
        pass

    def moveTo(self, *a):
        pass

    def lineTo(self, *a):
        pass

    def arcTo(self, *a):
        pass

    def closeSubpath(self):
        pass

    def pointAtPercent(self, *a):
        return QPoint()

    def length(self):
        return 100.0

    def percentAtLength(self, *a):
        return 0.0


class QPainter(metaclass=_Meta):
    def __init__(self, *a):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return lambda *a, **k: None

    def isActive(self):
        return True


class QStylePainter(QPainter):
    pass


class QStyleOption(metaclass=_Meta):
    def __init__(self, *a):
        self.rect = QRect()
        self.state = 0
        self.palette = QPalette()
        self.currentText = ""
        self.text = ""

    def initFrom(self, *a):
        pass


QStyleOptionComboBox = QStyleOptionFrame = QStyleOptionButton = QStyleOption


class QStyle(QObject):
    def pixelMetric(self, *a):
        return 16

    def polish(self, *a):
        pass

    def unpolish(self, *a):
        pass

    def drawComplexControl(self, *a):
        pass

    def drawPrimitive(self, *a):
        pass

    def drawControl(self, *a):
        pass

    def subControlRect(self, *a):
        return QRect(0, 0, 60, 20)

    def subElementRect(self, *a):
        return QRect(0, 0, 60, 20)

    def sizeFromContents(self, kind, opt, size, *a):
        return QSize(size.width() + 12, size.height() + 6)

    def styleHint(self, *a):
        return 0

    def standardIcon(self, *a):
        return QIcon()

    def objectName(self):
        return "windowsvista"


class QSizePolicy(metaclass=_Meta):
    def __init__(self, *a):
        self._a = a

    def setHorizontalStretch(self, *a):
        pass

    def setVerticalStretch(self, *a):
        pass

    def setRetainSizeWhenHidden(self, *a):
        pass

    def horizontalPolicy(self):
        return self._a[0] if self._a else 0

    def verticalPolicy(self):
        return self._a[1] if len(self._a) > 1 else 0


# --------------------------------------------------------------------------
# Layouts
# --------------------------------------------------------------------------


class _Item:
    def __init__(self, kind, obj=None, stretch=0, extra=None):
        self.kind, self.obj, self.stretch, self.extra = kind, obj, stretch, extra

    def widget(self):
        return self.obj if self.kind == "w" else None

    def layout(self):
        return self.obj if self.kind == "l" else None

    def spacerItem(self):
        return self if self.kind in ("stretch", "space") else None

    def sizeHint(self):
        if self.kind == "w":
            return self.obj.sizeHint()
        if self.kind == "l":
            return self.obj.sizeHint()
        return QSize(int(self.extra or 0), int(self.extra or 0))

    def minimumSize(self):
        return self.sizeHint()

    def geometry(self):
        return QRect()


class QLayout(QObject):
    def __init__(self, *args, **kwargs):
        parent = args[0] if args and isinstance(args[0], QWidget) else None
        super().__init__()
        self._items = []
        self._spacing = 6
        self._margins = QMargins(9, 9, 9, 9)
        self._owner = None
        self._align = 0
        self._constraint = None
        if parent is not None:
            parent.setLayout(self)

    def _widgets(self):
        for it in self._items:
            if it.kind == "w":
                yield it.obj
            elif it.kind == "l":
                yield from it.obj._widgets()

    def _adopt(self, w):
        owner = self._owner
        if owner is not None:
            w.setParent(owner)

    def addWidget(self, w, *a, **k):
        stretch = a[0] if a and isinstance(a[0], int) and not isinstance(a[0], Enum) else 0
        self._items.append(_Item("w", w, stretch, a[1:] if len(a) > 1 else None))
        self._adopt(w)

    def insertWidget(self, index, w, *a, **k):
        self._items.insert(index if index >= 0 else len(self._items), _Item("w", w))
        self._adopt(w)

    def addLayout(self, lay, *a, **k):
        self._items.append(_Item("l", lay, a[0] if a else 0))
        lay._parent_layout = self
        lay._owner = self._owner
        for w in lay._widgets():
            self._adopt(w)

    def insertLayout(self, index, lay, *a):
        self._items.insert(index if index >= 0 else len(self._items), _Item("l", lay))
        lay._owner = self._owner

    def addStretch(self, s=0):
        self._items.append(_Item("stretch", None, s))

    def addSpacing(self, s):
        self._items.append(_Item("space", None, 0, s))

    def insertSpacing(self, i, s):
        self._items.insert(i, _Item("space", None, 0, s))

    def insertStretch(self, i, s=0):
        self._items.insert(i, _Item("stretch", None, s))

    def addSpacerItem(self, sp):
        self._items.append(_Item("space", None, 0, 0))

    def addItem(self, it, *a):
        self._items.append(_Item("space", None, 0, 0))

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def indexOf(self, w):
        for i, it in enumerate(self._items):
            if it.obj is w:
                return i
        return -1

    def removeWidget(self, w):
        self._items = [it for it in self._items if it.obj is not w]

    def setSpacing(self, s):
        self._spacing = int(s)

    def spacing(self):
        return self._spacing

    def setHorizontalSpacing(self, s):
        self._hs = int(s)

    def setVerticalSpacing(self, s):
        self._vs = int(s)

    def horizontalSpacing(self):
        return getattr(self, "_hs", self._spacing)

    def verticalSpacing(self):
        return getattr(self, "_vs", self._spacing)

    def setContentsMargins(self, *a):
        self._margins = a[0] if len(a) == 1 else QMargins(*a)

    def contentsMargins(self):
        return self._margins

    def setMargin(self, m):
        self._margins = QMargins(m, m, m, m)

    def setAlignment(self, *a):
        self._align = a[-1]

    def setStretch(self, i, s):
        if 0 <= i < len(self._items):
            self._items[i].stretch = s

    def setStretchFactor(self, *a):
        return True

    def setSizeConstraint(self, c):
        self._constraint = c

    def setColumnStretch(self, *a):
        pass

    def setRowStretch(self, *a):
        pass

    def setColumnMinimumWidth(self, *a):
        pass

    def activate(self):
        return True

    def invalidate(self):
        pass

    def update(self):
        pass

    def parentWidget(self):
        return self._owner

    def geometry(self):
        return QRect()

    def sizeHint(self):
        m = self._margins
        hints = [it.sizeHint() for it in self._items]
        horizontal = isinstance(self, QHBoxLayout)
        gaps = self._spacing * max(0, len(hints) - 1)
        if horizontal:
            w = sum(h.width() for h in hints) + gaps
            h = max([x.height() for x in hints] or [0])
        else:
            w = max([x.width() for x in hints] or [0])
            h = sum(x.height() for x in hints) + gaps
        return QSize(w + m.left() + m.right(), h + m.top() + m.bottom())

    def minimumSize(self):
        return self.sizeHint()


class QBoxLayout(QLayout):
    pass


class QVBoxLayout(QBoxLayout):
    pass


class QHBoxLayout(QBoxLayout):
    pass


class QGridLayout(QLayout):
    def addWidget(self, w, *a, **k):
        super().addWidget(w)
        self._items[-1].extra = a


class QFormLayout(QLayout):
    def addRow(self, *a):
        for x in a:
            if isinstance(x, QWidget):
                self.addWidget(x)


class QSpacerItem:
    def __init__(self, *a):
        pass


# --------------------------------------------------------------------------
# Concrete widgets
# --------------------------------------------------------------------------


class _Textual(QWidget):
    def __init__(self, text="", *a, **k):
        if isinstance(text, QWidget):
            a = (text,) + a
            text = ""
        super().__init__(*a, **k)
        # Like Qt: QLineEdit(None) / QLabel(None) means "no parent", not the text "None".
        self._text = "" if text is None else str(text)
        self._align = 0

    def setText(self, t):
        t = "" if t is None else str(t)
        self._text = t

    def text(self):
        return self._text

    def setAlignment(self, a):
        self._align = a

    def alignment(self):
        return self._align

    def sizeHint(self):
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self._text) + 16
        return QSize(max(w, self._min.width()), max(fm.height() + 8, self._min.height()))


class QLabel(_Textual):
    def setWordWrap(self, *a):
        pass

    def setTextFormat(self, *a):
        pass

    def setOpenExternalLinks(self, *a):
        pass

    def setTextInteractionFlags(self, *a):
        pass

    def setPixmap(self, *a):
        pass

    def setMargin(self, *a):
        pass

    def setIndent(self, *a):
        pass

    def setBuddy(self, *a):
        pass

    def setScaledContents(self, *a):
        pass


class QAbstractButton(_Textual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._checkable = False
        self._checked = False
        self._flat = False
        self._shortcut = None
        self._auto_repeat = False

    def setCheckable(self, v):
        self._checkable = bool(v)

    def isCheckable(self):
        return self._checkable

    def setChecked(self, v):
        v = bool(v)
        if not self._checkable or v == self._checked:
            self._checked = v if self._checkable else self._checked
            return
        self._checked = v
        self.toggled.emit(v)

    def isChecked(self):
        return self._checked

    def click(self):
        if not self._enabled:
            return
        self.pressed.emit()
        self.released.emit()
        if self._checkable:
            self.setChecked(not self._checked)
        self.clicked.emit(self._checked)

    def toggle(self):
        self.setChecked(not self._checked)

    def setFlat(self, v):
        self._flat = bool(v)

    def setShortcut(self, s):
        self._shortcut = s

    def setAutoRepeat(self, v):
        self._auto_repeat = bool(v)

    def setAutoRepeatDelay(self, *a):
        pass

    def setAutoRepeatInterval(self, *a):
        pass

    def setIcon(self, *a):
        pass

    def setIconSize(self, *a):
        pass

    def setAutoDefault(self, *a):
        pass

    def setDefault(self, *a):
        pass

    def setMenu(self, m):
        self._menu = m

    def menu(self):
        return getattr(self, "_menu", None)

    def isDown(self):
        return False

    def setDown(self, *a):
        pass

    def initStyleOption(self, opt):
        pass


class QPushButton(QAbstractButton):
    pass


class QToolButton(QAbstractButton):
    def setPopupMode(self, *a):
        pass

    def setToolButtonStyle(self, *a):
        pass

    def setDefaultAction(self, *a):
        pass


class QCheckBox(QAbstractButton):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._checkable = True

    def setTristate(self, *a):
        pass

    def checkState(self):
        return 2 if self._checked else 0

    def setCheckState(self, s):
        self.setChecked(bool(s))


QRadioButton = QCheckBox


class QLineEdit(_Textual):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._maxlen = 32767
        self._ro = False
        self._ph = ""
        self._cursor_pos = 0

    def setText(self, t):
        t = "" if t is None else str(t)[: self._maxlen]
        changed = t != self._text
        self._text = t
        if changed:
            self.textChanged.emit(t)

    def setMaxLength(self, n):
        self._maxlen = int(n)

    def maxLength(self):
        return self._maxlen

    def setReadOnly(self, v):
        self._ro = bool(v)

    def isReadOnly(self):
        return self._ro

    def setPlaceholderText(self, t):
        self._ph = str(t)

    def placeholderText(self):
        return self._ph

    def displayText(self):
        return self._text

    def setCursorPosition(self, p):
        self._cursor_pos = int(p)

    def cursorPosition(self):
        return self._cursor_pos

    def setFrame(self, *a):
        pass

    def setClearButtonEnabled(self, *a):
        pass

    def textMargins(self):
        return QMargins()

    def setTextMargins(self, *a):
        pass

    def hasSelectedText(self):
        return False

    def selectAll(self):
        pass

    def deselect(self):
        pass

    def setValidator(self, *a):
        pass

    def setEchoMode(self, *a):
        pass

    def clear(self):
        self.setText("")

    def setSelection(self, *a):
        pass

    def end(self, *a):
        pass

    def home(self, *a):
        pass

    def initStyleOption(self, opt):
        pass

    def type_text(self, t):  # harness helper: user typing
        self.setText(t)
        self.textEdited.emit(self._text)
        self.editingFinished.emit()


class QComboBox(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._items = []  # [text, data, {role: value}]
        self._cur = -1
        self._editable = False
        self._min_contents = 0
        self._view = QWidget()

    def _changed(self, old):
        if self._cur != old:
            self.currentIndexChanged.emit(self._cur)
            self.currentTextChanged.emit(self.currentText())

    def addItem(self, *a):
        text = a[0] if a and isinstance(a[0], str) else (a[1] if len(a) > 1 and isinstance(a[1], str) else "")
        data = a[1] if len(a) > 1 and isinstance(a[0], str) else (a[2] if len(a) > 2 else None)
        self._items.append([text, data, {}])
        if self._cur < 0:
            old = self._cur
            self._cur = 0
            self._changed(old)

    def addItems(self, items):
        for t in items:
            self.addItem(t)

    def insertItem(self, i, *a):
        text = a[0] if a and isinstance(a[0], str) else ""
        data = a[1] if len(a) > 1 else None
        i = max(0, min(int(i), len(self._items)))
        self._items.insert(i, [text, data, {}])
        if self._cur < 0:
            old = self._cur
            self._cur = 0
            self._changed(old)
        elif i <= self._cur:
            self._cur += 1

    def insertSeparator(self, i):
        self.insertItem(i, "")

    def removeItem(self, i):
        if 0 <= i < len(self._items):
            old = self._cur
            del self._items[i]
            if self._cur >= len(self._items):
                self._cur = len(self._items) - 1
            self._changed(old)

    def clear(self):
        old = self._cur
        self._items = []
        self._cur = -1
        self._changed(old)

    def count(self):
        return len(self._items)

    def currentIndex(self):
        return self._cur

    def currentText(self):
        return self._items[self._cur][0] if 0 <= self._cur < len(self._items) else ""

    def currentData(self, *a):
        return self._items[self._cur][1] if 0 <= self._cur < len(self._items) else None

    def itemText(self, i):
        return self._items[i][0] if 0 <= i < len(self._items) else ""

    def itemData(self, i, role=None):
        if not (0 <= i < len(self._items)):
            return None
        if role is None or role == 256:
            return self._items[i][1]
        return self._items[i][2].get(int(role))

    def setItemData(self, i, value, role=None):
        if 0 <= i < len(self._items):
            if role is None or role == 256:
                self._items[i][1] = value
            else:
                self._items[i][2][int(role)] = value

    def setItemText(self, i, t):
        if 0 <= i < len(self._items):
            self._items[i][0] = str(t)

    def setCurrentIndex(self, i):
        i = int(i)
        if i < -1 or i >= len(self._items):
            return
        old = self._cur
        self._cur = i
        self._changed(old)

    def setCurrentText(self, t):
        i = self.findText(t)
        if i >= 0:
            self.setCurrentIndex(i)

    def findText(self, t, *a):
        for i, it in enumerate(self._items):
            if it[0] == t:
                return i
        return -1

    def findData(self, d, *a):
        for i, it in enumerate(self._items):
            if it[1] == d:
                return i
        return -1

    def setEditable(self, v):
        self._editable = bool(v)

    def isEditable(self):
        return self._editable

    def setMinimumContentsLength(self, n):
        self._min_contents = int(n)

    def minimumContentsLength(self):
        return self._min_contents

    def setSizeAdjustPolicy(self, *a):
        pass

    def setMaxVisibleItems(self, *a):
        pass

    def setInsertPolicy(self, *a):
        pass

    def setDuplicatesEnabled(self, *a):
        pass

    def view(self):
        return self._view

    def setView(self, v):
        self._view = v

    def showPopup(self):
        pass

    def hidePopup(self):
        pass

    def lineEdit(self):
        return None

    def setLineEdit(self, *a):
        pass

    def setItemDelegate(self, *a):
        pass

    def setFrame(self, *a):
        pass

    def setIconSize(self, *a):
        pass

    def initStyleOption(self, opt):
        pass

    def sizeHint(self):
        fm = self.fontMetrics()
        longest = max([fm.horizontalAdvance(it[0]) for it in self._items] or [0])
        return QSize(max(longest + 40, self._min.width()), max(fm.height() + 10, self._min.height()))

    def choose(self, text):  # harness helper: user picks an item
        i = self.findText(text)
        if i < 0:
            raise LookupError(text)
        self.setCurrentIndex(i)
        self.activated.emit(i)


class QSpinBox(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._v, self._lo, self._hi = 0, 0, 99

    def setRange(self, lo, hi):
        self._lo, self._hi = int(lo), int(hi)

    def setMinimum(self, v):
        self._lo = int(v)

    def setMaximum(self, v):
        self._hi = int(v)

    def setSingleStep(self, *a):
        pass

    def setSuffix(self, *a):
        pass

    def setValue(self, v):
        v = max(self._lo, min(self._hi, int(v)))
        if v != self._v:
            self._v = v
            self.valueChanged.emit(v)

    def value(self):
        return self._v

    def setButtonSymbols(self, *a):
        pass


class QTextBrowser(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._doc, self._markdown = "", False

    def setMarkdown(self, text):
        self._doc, self._markdown = str(text), True

    def setPlainText(self, text):
        self._doc, self._markdown = str(text), False

    def toPlainText(self):
        return self._doc

    def isMarkdown(self):  # harness helper
        return self._markdown

    def setOpenExternalLinks(self, on):
        self._external_links = bool(on)


class QListWidgetItem:
    def __init__(self, text=""):
        self._text = str(text)

    def text(self):
        return self._text

    def setText(self, text):
        self._text = str(text)


class QListWidget(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._rows, self._row = [], -1

    def addItem(self, item):
        self._rows.append(item if isinstance(item, QListWidgetItem) else QListWidgetItem(item))

    def clear(self):
        self._rows = []
        self.setCurrentRow(-1)

    def count(self):
        return len(self._rows)

    def item(self, i):
        return self._rows[i] if 0 <= i < len(self._rows) else None

    def currentRow(self):
        return self._row

    def setCurrentRow(self, i):
        i = int(i) if 0 <= int(i) < len(self._rows) else -1
        if i != self._row:
            self._row = i
            self.currentRowChanged.emit(i)

    def texts(self):  # harness helper
        return [r.text() for r in self._rows]


class QFrame(QWidget):
    def setFrameShape(self, *a):
        pass

    def setFrameShadow(self, *a):
        pass

    def setLineWidth(self, *a):
        pass

    def frameWidth(self):
        return 0


class QGroupBox(QWidget):
    def __init__(self, title="", *a, **k):
        if isinstance(title, QWidget):
            a = (title,) + a
            title = ""
        super().__init__(*a, **k)
        self._gtitle = str(title)

    def setTitle(self, t):
        self._gtitle = str(t)

    def title(self):
        return self._gtitle

    def setFlat(self, *a):
        pass

    def setCheckable(self, *a):
        pass


class QScrollArea(QFrame):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._w = None
        self._vp = QWidget(self)
        self._resizable = False

    def setWidget(self, w):
        self._w = w
        w.setParent(self._vp)

    def widget(self):
        return self._w

    def takeWidget(self):
        w, self._w = self._w, None
        return w

    def viewport(self):
        return self._vp

    def setWidgetResizable(self, v):
        self._resizable = bool(v)

    def widgetResizable(self):
        return self._resizable

    def setVerticalScrollBarPolicy(self, p):
        self._vpol = p

    def setHorizontalScrollBarPolicy(self, p):
        self._hpol = p

    def verticalScrollBar(self):
        return QWidget()

    def horizontalScrollBar(self):
        return QWidget()

    def setAlignment(self, *a):
        pass

    def sizeHint(self):
        return QSize(256, 192)


class QStackedWidget(QFrame):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._pages = []
        self._cur = -1

    def addWidget(self, w):
        self._pages.append(w)
        w.setParent(self)
        if self._cur < 0:
            self._cur = 0
        return len(self._pages) - 1

    def insertWidget(self, i, w):
        self._pages.insert(i, w)
        w.setParent(self)
        return i

    def removeWidget(self, w):
        if w in self._pages:
            self._pages.remove(w)

    def setCurrentWidget(self, w):
        if w in self._pages:
            self._cur = self._pages.index(w)
            self.currentChanged.emit(self._cur)

    def setCurrentIndex(self, i):
        self._cur = int(i)
        self.currentChanged.emit(self._cur)

    def currentWidget(self):
        return self._pages[self._cur] if 0 <= self._cur < len(self._pages) else None

    def currentIndex(self):
        return self._cur

    def count(self):
        return len(self._pages)

    def widget(self, i):
        return self._pages[i] if 0 <= i < len(self._pages) else None

    def indexOf(self, w):
        return self._pages.index(w) if w in self._pages else -1

    def sizeHint(self):
        cur = self.currentWidget()
        return cur.sizeHint() if cur is not None else QSize(0, 0)


class QTabWidget(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._tabs = []
        self._bar = QWidget(self)

    def addTab(self, w, label):
        self._tabs.append((w, str(label)))
        w.setParent(self)
        return len(self._tabs) - 1

    def tabBar(self):
        return self._bar

    def setTabBarAutoHide(self, *a):
        pass

    def setDocumentMode(self, *a):
        pass

    def setCurrentIndex(self, *a):
        pass

    def count(self):
        return len(self._tabs)


class QMenu(QWidget):
    def __init__(self, title="", *a, **k):
        if isinstance(title, QWidget):
            a = (title,) + a
            title = ""
        super().__init__(*a, **k)
        self._mtitle = str(title)
        self._actions = []
        self._menu_action = None

    def title(self):
        return self._mtitle

    def setTitle(self, t):
        self._mtitle = str(t)
        if self._menu_action is not None:  # Qt: the menu's action shows the new title
            self._menu_action.setText(self._mtitle)

    def addAction(self, *a, **k):
        if a and isinstance(a[0], QAction):
            act = a[0]
        else:
            text = next((x for x in a if isinstance(x, str)), "")
            act = QAction(text, self)
            fn = next((x for x in a if callable(x) and not isinstance(x, str)), None)
            if fn is not None:
                act.triggered.connect(fn)
        self._actions.append(act)
        return act

    def addMenu(self, m, *a):
        if isinstance(m, QMenu):
            menu = m
        else:
            menu = QMenu(str(m), self)
        act = QAction(menu.title(), self)
        act._submenu = menu
        menu._menu_action = act
        self._actions.append(act)
        return menu

    def addSeparator(self):
        act = QAction("", self)
        act._sep = True
        self._actions.append(act)
        return act

    def insertAction(self, before, act):
        i = self._actions.index(before) if before in self._actions else len(self._actions)
        self._actions.insert(i, act)

    def insertMenu(self, before, menu):
        act = QAction(menu.title(), self)
        act._submenu = menu
        menu._menu_action = act
        self.insertAction(before, act)
        return act

    def insertSeparator(self, before):
        act = QAction("", self)
        act._sep = True
        self.insertAction(before, act)
        return act

    def removeAction(self, act):
        if act in self._actions:
            self._actions.remove(act)

    def actions(self):
        return list(self._actions)

    def clear(self):
        self._actions = []

    def menuAction(self):
        if self._menu_action is None:
            self._menu_action = QAction(self._mtitle, self)
            self._menu_action._submenu = self
        return self._menu_action

    CHOICES = []  # harness: text prefixes to pick from the next exec_()

    def exec_(self, *a):
        self.exec_pos = a[0] if a else None  # where it was opened (screen coordinates)
        self.aboutToShow.emit()
        if not QMenu.CHOICES:
            return None
        want = QMenu.CHOICES.pop(0)
        for act in self._actions:
            if not act._sep and act._text.startswith(want):
                act.trigger()
                return act
        effect("menu-choice-missing", want)
        return None

    exec = exec_

    def popup(self, *a):
        self.aboutToShow.emit()

    def setToolTipsVisible(self, on=True):
        self._tips_visible = bool(on)

    def toolTipsVisible(self):
        return getattr(self, "_tips_visible", False)

    def setSeparatorsCollapsible(self, *a):
        pass

    def isEmpty(self):
        return not self._actions

    def setIcon(self, *a):
        pass


class QMenuBar(QMenu):
    def __init__(self, *a, **k):
        super().__init__("", *a, **k)
        self._corners = {}

    def setCornerWidget(self, w, corner=None):
        self._corners[int(corner) if corner is not None else 0] = w
        w.setParent(self)

    def cornerWidget(self, corner=None):
        return self._corners.get(int(corner) if corner is not None else 0)

    def setNativeMenuBar(self, *a):
        pass

    def sizeHint(self):
        return QSize(400, 24)


class QAction(QObject):
    def __init__(self, *a, **k):
        super().__init__(*[x for x in a if isinstance(x, QObject)], **k)
        self._text = next((x for x in a if isinstance(x, str)), "")
        self._checkable = False
        self._checked = False
        self._enabled = True
        self._visible = True
        self._shortcut = None
        self._data = None
        self._tip = ""
        self._submenu = None
        self._sep = False
        self._group = None

    def text(self):
        return self._text

    def setText(self, t):
        self._text = str(t)

    def setCheckable(self, v):
        self._checkable = bool(v)

    def isCheckable(self):
        return self._checkable

    def setChecked(self, v):
        v = bool(v)
        if not self._checkable or v == self._checked:
            self._checked = v if self._checkable else self._checked
            return
        if v and self._group is not None and self._group._exclusive:
            for other in self._group._actions:
                if other is not self and other._checked:
                    other._checked = False
                    other.toggled.emit(False)
        self._checked = v
        self.toggled.emit(v)

    def isChecked(self):
        return self._checked

    def setEnabled(self, v):
        self._enabled = bool(v)

    def isEnabled(self):
        return self._enabled

    def setVisible(self, v):
        self._visible = bool(v)

    def isVisible(self):
        return self._visible

    def setShortcut(self, s):
        self._shortcut = str(s)

    def shortcut(self):
        return self._shortcut

    def setData(self, d):
        self._data = d

    def data(self):
        return self._data

    def setToolTip(self, t):
        self._tip = str(t)

    def toolTip(self):
        return self._tip

    def setStatusTip(self, *a):
        pass

    def setIcon(self, *a):
        pass

    def setMenu(self, m):
        self._submenu = m

    def menu(self):
        return self._submenu

    def isSeparator(self):
        return self._sep

    def setSeparator(self, v):
        self._sep = bool(v)

    def setActionGroup(self, g):
        g.addAction(self)

    def setMenuRole(self, *a):
        pass

    def setFont(self, *a):
        pass

    def setShortcutContext(self, *a):
        pass

    def setIconVisibleInMenu(self, *a):
        pass

    def trigger(self):
        if not self._enabled:
            return
        if self._checkable:
            if not (self._group is not None and self._group._exclusive and self._checked):
                self.setChecked(not self._checked)
        self.triggered.emit(self._checked)


class QActionGroup(QObject):
    def __init__(self, *a):
        super().__init__(*a)
        self._actions = []
        self._exclusive = True

    def addAction(self, act):
        if isinstance(act, str):
            act = QAction(act, self)
        act._group = self
        self._actions.append(act)
        return act

    def setExclusive(self, v):
        self._exclusive = bool(v)

    def actions(self):
        return list(self._actions)

    def checkedAction(self):
        return next((a for a in self._actions if a._checked), None)


class QStatusBar(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._msg = ""
        self._perm = []

    def showMessage(self, m, timeout=0):
        self._msg = str(m)
        if timeout:
            msg = self._msg
            CLOCK.later(timeout, lambda: self._msg == msg and self.clearMessage())

    def currentMessage(self):
        return self._msg

    def clearMessage(self):
        self._msg = ""

    def addPermanentWidget(self, w, *a):
        self._perm.append(w)
        w.setParent(self)

    def addWidget(self, w, *a):
        self._perm.append(w)
        w.setParent(self)

    def setSizeGripEnabled(self, *a):
        pass

    def sizeHint(self):
        return QSize(400, 22)


class QMainWindow(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._central = None
        self._menubar = None
        self._statusbar = None
        self._state = "normal"
        self._geom = QRect(100, 100, 800, 600)
        # As in Qt: a top-level window starts with minimize, maximize and close buttons.
        self._flags = Flag(
            int(Qt.Window)
            | int(Qt.WindowMinimizeButtonHint)
            | int(Qt.WindowMaximizeButtonHint)
            | int(Qt.WindowCloseButtonHint)
        )
        QApplication._top.append(self)

    def menuBar(self):
        if self._menubar is None:
            self._menubar = QMenuBar(self)
        return self._menubar

    def setMenuBar(self, mb):
        self._menubar = mb
        mb.setParent(self)

    def statusBar(self):
        if self._statusbar is None:
            self._statusbar = QStatusBar(self)
        return self._statusbar

    def setStatusBar(self, sb):
        self._statusbar = sb

    def setCentralWidget(self, w):
        if self._central is not None and self._central is not w:
            self._central._deleted = True  # Qt deletes the old one
        self._central = w
        if w is not None:
            w.setParent(self)

    def centralWidget(self):
        return self._central

    def takeCentralWidget(self):
        w, self._central = self._central, None
        if w is not None:
            w.setParent(None)
        return w

    def isMinimized(self):
        return self._state == "min"

    def isMaximized(self):
        return self._state == "max"

    def isFullScreen(self):
        return self._state == "full"

    def showMinimized(self):
        self._state = "min"
        self.show()

    def showMaximized(self):
        self._state = "max"
        self.show()

    def showNormal(self):
        self._state = "normal"
        self.show()

    def showFullScreen(self):
        self._state = "full"
        self.show()

    def windowState(self):
        return self._state

    def setWindowState(self, s):
        pass

    def addToolBar(self, *a):
        return QWidget(self)

    def addDockWidget(self, *a):
        pass

    def setUnifiedTitleAndToolBarOnMac(self, *a):
        pass

    def setDocumentMode(self, *a):
        pass

    def sizeHint(self):
        return QSize(800, 600)


class QDialog(QWidget):
    RESULT = 0

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._result = 0

    def exec_(self):
        effect("dialog", type(self).__name__, self._title)
        return QDialog.RESULT

    exec = exec_

    def accept(self):
        self._result = 1
        self.hide()

    def reject(self):
        self._result = 0
        self.hide()

    def done(self, r):
        self._result = r
        self.hide()

    def setModal(self, *a):
        pass

    def open(self):
        self.show()

    def result(self):
        return self._result

    def setSizeGripEnabled(self, *a):
        pass


class QSystemTrayIcon(QObject):
    AVAILABLE = True

    def __init__(self, *a):
        super().__init__(*[x for x in a if isinstance(x, QObject)])
        self._visible = False
        self._tip = ""
        self._menu = None
        self._icon = None

    @staticmethod
    def isSystemTrayAvailable():
        return QSystemTrayIcon.AVAILABLE

    @staticmethod
    def supportsMessages():
        return True

    def setIcon(self, i):
        self._icon = i

    def icon(self):
        return self._icon

    def setToolTip(self, t):
        self._tip = str(t)

    def toolTip(self):
        return self._tip

    def setContextMenu(self, m):
        self._menu = m

    def contextMenu(self):
        return self._menu

    def show(self):
        self._visible = True

    def hide(self):
        self._visible = False

    def setVisible(self, v):
        self._visible = bool(v)

    def isVisible(self):
        return self._visible

    def showMessage(self, *a):
        effect("tray-message", *[str(x) for x in a[:2]])


class QTimer(QObject):
    def __init__(self, *a):
        super().__init__(*a)
        self._interval = 0
        self._active = False
        self._single = False
        self._due = 0.0
        CLOCK.timers.append(self)

    def setInterval(self, ms):
        self._interval = int(ms)

    def interval(self):
        return self._interval

    def setSingleShot(self, v):
        self._single = bool(v)

    def isSingleShot(self):
        return self._single

    def setTimerType(self, *a):
        pass

    def isActive(self):
        return self._active

    def remainingTime(self):
        return max(0, int(self._due - CLOCK.ms)) if self._active else -1

    def start(self, ms=None):
        if ms is not None:
            self._interval = int(ms)
        self._active = True
        self._due = CLOCK.ms + max(0, self._interval)

    def stop(self):
        self._active = False

    @staticmethod
    def singleShot(ms, *a):
        fn = a[-1]
        if hasattr(fn, "emit") and not callable(getattr(fn, "__call__", None)):
            fn = fn.emit
        CLOCK.later(ms, fn)


class QElapsedTimer:
    def __init__(self):
        self._t = CLOCK.ms

    def start(self):
        self._t = CLOCK.ms

    def restart(self):
        e = self.elapsed()
        self._t = CLOCK.ms
        return e

    def elapsed(self):
        return int(CLOCK.ms - self._t) if self._t is not None else 0

    def isValid(self):
        return self._t is not None

    def invalidate(self):
        self._t = None

    def hasExpired(self, ms):
        return self.isValid() and self.elapsed() > ms


class QCursor:
    _pos = QPoint(500, 300)

    def __init__(self, *a):
        pass

    @staticmethod
    def pos(*a):
        return QPoint(QCursor._pos.x(), QCursor._pos.y())

    @staticmethod
    def setPos(*a):
        pass


class QCoreApplication(QObject):
    _attrs = {}
    _app = None
    _app_font = QFont("Segoe UI", 9)
    _screens = []
    _top = []
    _policy = None

    def __init__(self, argv=None, *a):
        super().__init__()
        QCoreApplication._app = self
        self._qss = ""
        self._name = ""

    @staticmethod
    def setAttribute(a, on=True):
        QCoreApplication._attrs[int(a)] = bool(on)

    @staticmethod
    def testAttribute(a):
        return QCoreApplication._attrs.get(int(a), False)

    @staticmethod
    def instance():
        return QCoreApplication._app

    @staticmethod
    def processEvents(*a):
        pass

    @staticmethod
    def applicationDirPath():
        return ""

    @staticmethod
    def setHighDpiScaleFactorRoundingPolicy(p):
        QCoreApplication._policy = p

    @staticmethod
    def screens():
        return list(QCoreApplication._screens)

    @staticmethod
    def primaryScreen():
        return QCoreApplication._screens[0]

    @staticmethod
    def screenAt(p):
        for s in QCoreApplication._screens:
            if s.geometry().contains(p):
                return s
        return None

    @staticmethod
    def font(*a):
        return QFont(QCoreApplication._app_font)

    @staticmethod
    def setFont(f, *a):
        QCoreApplication._app_font = QFont(f)

    @staticmethod
    def topLevelWidgets():
        return list(QCoreApplication._top)

    @staticmethod
    def activeWindow():
        return None

    @staticmethod
    def widgetAt(*a):
        return None

    @staticmethod
    def mouseButtons():
        return 0

    @staticmethod
    def keyboardModifiers():
        return 0

    @staticmethod
    def desktop():
        return QWidget()

    @staticmethod
    def setStyle(*a):
        pass

    @staticmethod
    def style():
        return QStyle()

    @staticmethod
    def setQuitOnLastWindowClosed(v):
        QCoreApplication._quit_last = bool(v)

    @staticmethod
    def quitOnLastWindowClosed():
        return getattr(QCoreApplication, "_quit_last", True)

    @staticmethod
    def setWindowIcon(i):
        QCoreApplication._icon = i

    @staticmethod
    def windowIcon():
        return getattr(QCoreApplication, "_icon", QIcon())

    @staticmethod
    def setPalette(*a):
        pass

    @staticmethod
    def palette(*a):
        return QPalette()

    @staticmethod
    def beep():
        pass

    @staticmethod
    def quit():
        effect("app-quit")

    @staticmethod
    def exit(code=0):
        effect("app-exit", code)

    @staticmethod
    def clipboard():
        return QObject()

    def setStyleSheet(self, s):
        self._qss = str(s)

    def styleSheet(self):
        return self._qss

    def setApplicationName(self, n):
        self._name = str(n)

    def applicationName(self):
        return self._name

    def setApplicationDisplayName(self, n):
        self._display = str(n)

    def setOrganizationName(self, *a):
        pass

    def setApplicationVersion(self, *a):
        pass

    def setDesktopFileName(self, *a):
        pass

    def exec_(self):
        hook = ENV.session
        if hook is not None:
            hook(self)
        return 0

    exec = exec_


QGuiApplication = QApplication = QCoreApplication


class QFileDialog(QDialog):
    ANSWERS = []

    @staticmethod
    def _answer(kind, *a):
        ans = QFileDialog.ANSWERS.pop(0) if QFileDialog.ANSWERS else ""
        effect("file-dialog", kind, ans)
        return ans

    @staticmethod
    def getSaveFileName(*a, **k):
        return (QFileDialog._answer("save", *a), "")

    @staticmethod
    def getOpenFileName(*a, **k):
        return (QFileDialog._answer("open", *a), "")

    @staticmethod
    def getExistingDirectory(*a, **k):
        return QFileDialog._answer("dir", *a)


class QMessageBox(QDialog):
    ANSWER = None

    @staticmethod
    def _box(kind, parent, title, text, *a):
        effect("message-box", kind, str(title), str(text))
        if QMessageBox.ANSWER is not None:
            return QMessageBox.ANSWER
        return QMessageBox.Yes if kind == "question" else QMessageBox.Ok

    @staticmethod
    def warning(*a, **k):
        return QMessageBox._box("warning", *a[:3])

    @staticmethod
    def information(*a, **k):
        return QMessageBox._box("information", *a[:3])

    @staticmethod
    def critical(*a, **k):
        return QMessageBox._box("critical", *a[:3])

    @staticmethod
    def question(*a, **k):
        return QMessageBox._box("question", *a[:3])

    @staticmethod
    def about(*a, **k):
        return QMessageBox._box("about", *a[:3])

    def setText(self, *a):
        pass

    def setInformativeText(self, *a):
        pass

    def setIcon(self, *a):
        pass

    def setStandardButtons(self, *a):
        pass

    def setDefaultButton(self, *a):
        pass

    def addButton(self, *a):
        return QPushButton()

    def clickedButton(self):
        return None


class QInputDialog(QDialog):
    ANSWERS = []

    @staticmethod
    def _pop(kind, *a):
        ans = QInputDialog.ANSWERS.pop(0) if QInputDialog.ANSWERS else None
        effect("input-dialog", kind, str(a[1:3]))
        return ans

    @staticmethod
    def getText(*a, **k):
        ans = QInputDialog._pop("text", *a)
        return (ans, True) if ans is not None else ("", False)

    @staticmethod
    def getInt(*a, **k):
        ans = QInputDialog._pop("int", *a)
        return (int(ans), True) if ans is not None else (0, False)

    @staticmethod
    def getItem(*a, **k):
        ans = QInputDialog._pop("item", *a)
        return (ans, True) if ans is not None else ("", False)


# --------------------------------------------------------------------------
# Win32 / registry / HID / process fakes
# --------------------------------------------------------------------------


class Win32State:
    def __init__(self):
        self.windows = []  # [(hwnd, title, pid, exe)]
        self.classes = {}  # hwnd -> window class name (default "FakeWindowClass")
        self.foreground = 0
        self.monitors = [  # (device, x, y, w, h, work_h, dpi, primary)
            (r"\\.\DISPLAY1", 0, 0, 2560, 1440, 1400, 96, True),
        ]
        self.my_pid = 4242
        # Device name MonitorFromWindow reports for a window (or a callable
        # taking the hwnd). None: no answer, so placement falls back to Qt.
        self.window_monitor = None
        # Physical client-area origin ClientToScreen reports (or a callable
        # taking the hwnd). None: the call fails.
        self.client_origin = None
        # The DPI Windows was signed in with (0: GetDpiForSystem not answered),
        # and Windows' default GUI font as (lfHeight, face) (None: no font).
        self.system_dpi = 0
        self.gui_font = None

    def pid_of(self, hwnd):
        for h, _t, pid, _e in self.windows:
            if h == hwnd:
                return pid
        return 0

    def exe_of_pid(self, pid):
        for _h, _t, p, exe in self.windows:
            if p == pid:
                return exe
        return ""

    def title_of(self, hwnd):
        for h, t, _p, _e in self.windows:
            if h == hwnd:
                return t
        return ""


W32 = Win32State()


def _deref(arg):
    return getattr(arg, "_obj", arg)


def _set_value(arg, value):
    target = _deref(arg)
    try:
        target.value = value
    except (AttributeError, TypeError):
        pass


class _Func:
    def __init__(self, dll, name, impl):
        self._dll, self.__name__, self._impl = dll, name, impl
        self.argtypes = None
        self.restype = None
        self.errcheck = None

    def __call__(self, *args):
        return self._impl(*args)


def _decode_inputs(n, arr_ref):
    arr = _deref(arr_ref)
    out = []
    for i in range(int(n)):
        try:
            ki = arr[i].ki
            out.append(
                (int(ki.wScan), "up" if ki.dwFlags & 0x0002 else "down", "ext" if ki.dwFlags & 0x0001 else "")
            )
        except (AttributeError, IndexError, TypeError):
            out.append(("?",))
    return out


def _user32(name):
    s = W32

    def enum_windows(cb, lparam=0):
        for h, *_rest in list(s.windows):
            if not cb(h, lparam):
                break
        return 1

    def get_text_len(h):
        return len(s.title_of(h))

    def get_text(h, buf, n):
        _set_value(buf, s.title_of(h)[: max(0, int(n) - 1)])
        return len(s.title_of(h))

    def get_class(h, buf, n):
        name = s.classes.get(h, "FakeWindowClass")
        _set_value(buf, name)
        return len(name)

    def get_pid(h, pid_ref):
        _set_value(pid_ref, s.pid_of(h))
        return 1 if s.pid_of(h) else 0

    def send_input(n, arr_ref, size):
        effect("keys", tuple(_decode_inputs(n, arr_ref)))
        return int(n)

    def keybd_event(vk, sc, flags, extra):
        effect("keybd_event", int(getattr(sc, "value", sc)), int(flags))

    def message_box(h, text, title, flags):
        effect("win32-message-box", str(title), str(text))
        return 1

    def enum_monitors(hdc, clip, cb, lparam):
        for i, _m in enumerate(s.monitors):
            if not cb(1000 + i, 0, None, lparam):
                break
        return 1

    def monitor_info(hmon, info_ref):
        info = _deref(info_ref)
        dev, x, y, w, h, work_h, _dpi, primary = s.monitors[int(hmon) - 1000]
        for rect, height in ((info.rcMonitor, h), (info.rcWork, work_h)):
            rect.left, rect.top, rect.right, rect.bottom = x, y, x + w, y + height
        info.dwFlags = 1 if primary else 0
        try:
            info.szDevice = dev
        except AttributeError:
            pass
        return 1

    def monitor_from_window(hwnd, flags):
        dev = s.window_monitor(hwnd) if callable(s.window_monitor) else s.window_monitor
        for i, m in enumerate(s.monitors):
            if m[0] == dev:
                return 1000 + i
        return 0

    def client_to_screen(hwnd, point_ref):
        origin = s.client_origin(hwnd) if callable(s.client_origin) else s.client_origin
        if origin is None:
            return 0
        point = _deref(point_ref)
        point.x, point.y = point.x + origin[0], point.y + origin[1]
        return 1

    table = {
        "EnumWindows": enum_windows,
        "MonitorFromWindow": monitor_from_window,
        "ClientToScreen": client_to_screen,
        "IsWindowVisible": lambda h: 1,
        "IsWindow": lambda h: 1 if any(w[0] == h for w in s.windows) else 0,
        "GetWindowTextLengthW": get_text_len,
        "GetWindowTextW": get_text,
        "GetClassNameW": get_class,
        "GetWindowThreadProcessId": get_pid,
        "GetForegroundWindow": lambda: s.foreground,
        "SendInput": send_input,
        "keybd_event": keybd_event,
        "MessageBoxW": message_box,
        "EnumDisplayMonitors": enum_monitors,
        "GetMonitorInfoW": monitor_info,
        "GetAsyncKeyState": lambda vk: 0,
        "ShowWindow": lambda *a: effect("ShowWindow", *a[1:]) or 1,
        "SetForegroundWindow": lambda *a: effect("SetForegroundWindow", *a) or 1,
        "GetSystemMetrics": lambda i: 0,
        "GetDpiForSystem": lambda: s.system_dpi,
        "RegisterWindowMessageW": lambda name: 0xC1A6 if str(name).endswith(".Exit") else 0xC1A5,
        "PostMessageW": lambda h, msg, w, l: effect("PostMessage", int(h), int(msg)) or 1,
        "AllowSetForegroundWindow": lambda pid: effect("AllowSetForegroundWindow", int(pid)) or 1,
    }
    return table.get(name, lambda *a: 0)


def _kernel32(name):
    s = W32
    handles = {}

    def open_process(access, inherit, pid):
        if not pid:
            return 0
        handles[5000 + int(pid)] = int(pid)
        return 5000 + int(pid)

    def query_image(h, flags, buf, size_ref):
        exe = s.exe_of_pid(int(h) - 5000)
        if not exe:
            return 0
        _set_value(buf, exe)
        _set_value(size_ref, len(exe))
        return 1

    table = {
        "OpenProcess": open_process,
        "QueryFullProcessImageNameW": query_image,
        "CloseHandle": lambda h: 1,
        "GetCurrentProcessId": lambda: s.my_pid,
        "CreateMutexW": lambda *a: 77,
        "GetLastError": lambda: 0,
        "ReleaseMutex": lambda *a: 1,
    }
    return table.get(name, lambda *a: 0)


def _shcore(name):
    def dpi_for_monitor(hmon, kind, x_ref, y_ref):
        dpi = W32.monitors[int(hmon) - 1000][6]
        _set_value(x_ref, dpi)
        _set_value(y_ref, dpi)
        return 0

    return {"GetDpiForMonitor": dpi_for_monitor}.get(name, lambda *a: 0)


def _gdi32(name):
    def get_object(handle, size, ref):
        if int(handle or 0) != 900 or W32.gui_font is None:
            return 0
        font = _deref(ref)
        font.lfHeight, font.lfFaceName = W32.gui_font
        return int(size)

    table = {
        "GetStockObject": lambda index: 900 if W32.gui_font is not None and int(index) == 17 else 0,
        "GetObjectW": get_object,
    }
    return table.get(name, lambda *a: 0)


class _DLL:
    def __init__(self, name):
        self._dllname = name.lower().replace(".dll", "")
        self._funcs = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self._funcs:
            maker = {"user32": _user32, "kernel32": _kernel32, "shcore": _shcore, "gdi32": _gdi32}.get(
                self._dllname
            )
            impl = maker(name) if maker else (lambda *a: 0)
            self._funcs[name] = _Func(self, name, impl)
        return self._funcs[name]


class _DLLLoader:
    def __init__(self):
        self._dlls = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in self._dlls:
            self._dlls[name] = _DLL(name)
        return self._dlls[name]


class FakeRegistry(types.ModuleType):
    def __init__(self):
        super().__init__("winreg")
        self.HKEY_CURRENT_USER = 0x80000001
        self.KEY_READ, self.KEY_WRITE, self.KEY_SET_VALUE, self.KEY_QUERY_VALUE = 1, 2, 2, 1
        self.KEY_ALL_ACCESS = 3
        self.REG_SZ = 1
        self.values = {}

    class _Key:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def Close(self):
            pass

    def OpenKey(self, root, path, *a):
        return self._Key(path)

    def CreateKey(self, root, path):
        return self._Key(path)

    def OpenKeyEx(self, root, path, *a):
        return self._Key(path)

    def CreateKeyEx(self, root, path, *a):
        return self._Key(path)

    def CloseKey(self, k):
        pass

    def SetValueEx(self, key, name, reserved, kind, value):
        self.values[(key.path, name)] = value
        effect("registry-set", key.path, name, value)

    def QueryValueEx(self, key, name):
        if (key.path, name) not in self.values:
            raise FileNotFoundError(name)
        return self.values[(key.path, name)], 1

    def DeleteValue(self, key, name):
        if (key.path, name) not in self.values:
            raise FileNotFoundError(name)
        del self.values[(key.path, name)]
        effect("registry-delete", key.path, name)


class FakeHidDevice:
    def __init__(self, path=None):
        self.path = path
        self.nonblocking = True
        self.reports = []

    def read(self, n, *a):
        return self.reports.pop(0) if self.reports else []

    def send_feature_report(self, buf):
        effect("hid-feature", tuple(buf[:2]), len(buf))
        return len(buf)

    def write(self, data):
        effect("hid-write", tuple(data[:2]), len(data))
        return len(data)

    def close(self):
        pass

    def set_nonblocking(self, v):
        self.nonblocking = bool(v)

    def open_path(self, p):
        self.path = p


class FakeHid(types.ModuleType):
    def __init__(self):
        super().__init__("hid")
        self.present = True
        self.device_obj = FakeHidDevice(b"fake-path")

    def enumerate(self, vid=0, pid=0):
        if not self.present:
            return []
        return [
            {
                "vendor_id": 0x046D,
                "product_id": 0xC626,
                "path": b"fake-path",
                "usage_page": 1,
                "usage": 8,
                "interface_number": 0,
                "product_string": "SpaceNavigator",
            }
        ]

    def Device(self, path=None, **k):
        self.device_obj.path = path
        return self.device_obj

    def device(self):
        return self.device_obj

    def push_axes(self, tx=0, ty=0, tz=0, rx=0, ry=0, rz=0):
        """Queue translation+rotation reports in device units (-350..350)."""
        import struct

        dev = self.device_obj
        dev.reports.append(list(bytes([1]) + struct.pack("<hhh", int(tx), int(ty), int(tz))))
        dev.reports.append(list(bytes([2]) + struct.pack("<hhh", int(rx), int(ry), int(rz))))

    def push_buttons(self, mask):
        self.device_obj.reports.append([3, mask & 0xFF, (mask >> 8) & 0xFF])


class FakePopen:
    def __init__(self, cmd, *a, **k):
        effect("process", tuple(str(c) for c in cmd) if isinstance(cmd, (list, tuple)) else str(cmd))
        self.pid = 999
        self.returncode = 0

    def wait(self, *a, **k):
        return 0

    def poll(self):
        return 0

    def communicate(self, *a, **k):
        return (b"", b"")


# --------------------------------------------------------------------------
# Installation
# --------------------------------------------------------------------------


class Env:
    def __init__(self):
        self.session = None
        self.clock = CLOCK
        self.effects = EFFECTS
        self.errors = ERRORS
        self.win32 = W32
        self.hid = None
        self.registry = None

    def advance(self, ms):
        CLOCK.advance(ms)

    def main_window(self):
        for w in QCoreApplication._top:
            if type(w).__name__ == "MainWindow":
                return w
        return None


ENV = Env()

_QT_NAMES = [
    n for n, v in list(globals().items()) if n.startswith("Q") or n in ("Qt", "pyqtSignal", "pyqtSlot")
]

Qt = EnumSpace("Qt.")
# (widget, flags) for each overrideWindowFlags call
FLAG_CHANGES = []
QT_VERSION = 0x050F0A
QT_VERSION_STR = "5.15.10"
PYQT_VERSION_STR = "5.15.10"


def _module(name, attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)

    def __getattr__(attr):  # unknown Qt class: a plain widget
        if attr.startswith("Q"):
            cls = _Meta(attr, (QWidget,), {})
            setattr(mod, attr, cls)
            return cls
        raise AttributeError(attr)

    mod.__getattr__ = __getattr__
    return mod


def install(screens=None):
    """Install fake PyQt5 / Win32 / winreg / hid / Popen and virtual time."""
    import subprocess
    import time as time_mod

    g = globals()
    qt = {n: g[n] for n in _QT_NAMES if n in g}
    qt.update(Qt=Qt, QT_VERSION=QT_VERSION, QT_VERSION_STR=QT_VERSION_STR, PYQT_VERSION_STR=PYQT_VERSION_STR)
    core = _module("PyQt5.QtCore", qt)
    gui = _module("PyQt5.QtGui", qt)
    widgets = _module("PyQt5.QtWidgets", qt)
    pkg = types.ModuleType("PyQt5")
    pkg.QtCore, pkg.QtGui, pkg.QtWidgets = core, gui, widgets
    pkg.__path__ = []
    sys.modules.update(
        {
            "PyQt5": pkg,
            "PyQt5.QtCore": core,
            "PyQt5.QtGui": gui,
            "PyQt5.QtWidgets": widgets,
            "PyQt5.sip": types.ModuleType("PyQt5.sip"),
        }
    )

    QCoreApplication._screens = screens or [
        QScreen(r"\\.\DISPLAY1", QRect(0, 0, 2560, 1440), QRect(0, 0, 2560, 1400))
    ]

    # Win32
    ctypes.windll = _DLLLoader()
    ctypes.WinDLL = lambda name, *a, **k: getattr(ctypes.windll, name.replace(".dll", ""))
    ctypes.oledll = ctypes.windll
    if not hasattr(ctypes, "WINFUNCTYPE"):
        ctypes.WINFUNCTYPE = ctypes.CFUNCTYPE
    ctypes.get_last_error = lambda: 0
    ctypes.set_last_error = lambda v: 0
    from ctypes import wintypes  # noqa: F401  (works on every OS since 3.x)

    sys.platform = "win32"

    reg = FakeRegistry()
    sys.modules["winreg"] = reg
    ENV.registry = reg
    hidmod = FakeHid()
    sys.modules["hid"] = hidmod
    ENV.hid = hidmod

    subprocess.Popen = FakePopen
    import os

    os.startfile = lambda *a, **k: effect("startfile", *[str(x) for x in a])

    # virtual time
    time_mod.perf_counter = CLOCK.perf_counter
    time_mod.monotonic = CLOCK.perf_counter
    time_mod.time = CLOCK.time
    time_mod.sleep = CLOCK.sleep
    builtins.__dict__.setdefault("_fakeqt_installed", True)
    return ENV


# --------------------------------------------------------------------------
# Snapshots
# --------------------------------------------------------------------------


def _font_desc(w):
    f = w._font
    return None if f is None else f.key()


def describe(w, seen=None):
    """Deterministic description of a widget and everything below it."""
    if seen is None:
        seen = set()
    if id(w) in seen:
        return {"ref": type(w).__name__}
    seen.add(id(w))
    d = {"cls": type(w).__name__}
    for key, val in (
        ("name", w._name),
        ("text", getattr(w, "_text", None)),
        ("title", getattr(w, "_gtitle", None) or getattr(w, "_mtitle", None) or w._title),
        ("style", w._style),
        ("tip", w._tip),
        ("font", _font_desc(w)),
        ("enabled", w._enabled),
        ("shown", w._visible_flag),
        ("min", (w._min.width(), w._min.height())),
        ("max", (w._max.width(), w._max.height())),
        ("policy", repr(w._policy) if w._policy else None),
        ("margins", w._margins._m if w._margins._m != (0, 0, 0, 0) else None),
    ):
        if val not in (None, "", ()):
            d[key] = val
    if isinstance(w, QAbstractButton):
        d.update(checkable=w._checkable, checked=w._checked)
    if isinstance(w, QLineEdit):
        d.update(maxlen=w._maxlen, ro=w._ro, ph=w._ph)
    if isinstance(w, QComboBox):
        d.update(items=[(t, repr(dt)) for t, dt, _r in w._items], cur=w._cur)
    if isinstance(w, QStackedWidget):
        d["pages"] = [describe(p, seen) for p in w._pages]
        d["current"] = w._cur
    if isinstance(w, QScrollArea) and w._w is not None:
        d["content"] = describe(w._w, seen)
    if w._layout is not None:
        d["layout"] = describe_layout(w._layout, seen)
    loose = [
        k
        for k in w._kids
        if isinstance(k, QWidget)
        and id(k) not in seen
        and not isinstance(k, (QMenuBar, QStatusBar, QMenu))
        and not getattr(k, "_deleted", False)
        and k is not getattr(w, "_vp", None)
    ]
    if loose:
        d["children"] = sorted((describe(k, seen) for k in loose), key=repr)
    return d


def describe_layout(lay, seen):
    d = {"cls": type(lay).__name__, "spacing": lay._spacing, "margins": lay._margins._m}
    items = []
    for it in lay._items:
        if it.kind == "w":
            items.append(("w", it.stretch, describe(it.obj, seen)))
        elif it.kind == "l":
            items.append(("l", it.stretch, describe_layout(it.obj, seen)))
        else:
            items.append((it.kind, it.stretch, it.extra))
    d["items"] = items
    return d


def describe_menu(menu, depth=0):
    out = []
    for a in menu._actions:
        if a._sep:
            out.append("---")
            continue
        entry = {"text": a._text, "enabled": a._enabled, "visible": a._visible}
        if a._checkable:
            entry["checked"] = a._checked
        if a._shortcut:
            entry["shortcut"] = a._shortcut
        if a._tip:
            entry["tip"] = a._tip
        if a._submenu is not None and depth < 4:
            entry["menu"] = describe_menu(a._submenu, depth + 1)
        out.append(entry)
    return out


def snapshot(win):
    """Everything a user could see or that later behaviour depends on."""
    if win is None:
        return None
    mb = win._menubar
    sb = win._statusbar
    snap = {
        "title": win._title,
        "geometry": win._geom._r,
        "min": (win._min.width(), win._min.height()),
        "max": (win._max.width(), win._max.height()),
        "visible": win._visible_flag,
        "state": win._state,
        "style_len": len(win._style),
        "style_hash": zlib.crc32(win._style.encode()),
        "central": describe(win._central) if win._central is not None else None,
        "menu": describe_menu(mb) if mb else None,
        "corner": {k: describe(v) for k, v in mb._corners.items()} if mb else None,
        "status": sb._msg if sb else None,
        "status_widgets": [describe(w) for w in sb._perm] if sb else None,
        "timers": sorted((t._interval, t._single) for t in CLOCK.timers if t._active),
        "app_font": QCoreApplication._app_font.key(),
        "app_qss_hash": zlib.crc32(getattr(QCoreApplication._app, "_qss", "").encode()),
    }
    trays = [k for k in _all_objects(win) if isinstance(k, QSystemTrayIcon)]
    snap["tray"] = [
        {"visible": t._visible, "tip": t._tip, "menu": describe_menu(t._menu) if t._menu else None}
        for t in trays
    ]
    return snap


def _all_objects(root):
    out, stack = [], [root]
    while stack:
        o = stack.pop()
        out.append(o)
        stack.extend(getattr(o, "_kids", []))
    return out


def find_action(win, *path):
    """Find a menu action by its visible text path, e.g. ("View", "Show Full Editor")."""
    menu = win.menuBar()
    act = None
    for i, label in enumerate(path):
        act = next((a for a in menu._actions if a._text.replace("&", "") == label), None)
        if act is None:
            raise LookupError(" > ".join(path[: i + 1]))
        if i < len(path) - 1:
            menu = act._submenu
    return act


def find_widget(root, cls=None, text=None, name=None):
    for o in _all_objects(root):
        if cls is not None and not isinstance(o, cls):
            continue
        if text is not None and getattr(o, "_text", None) != text:
            continue
        if name is not None and getattr(o, "_name", None) != name:
            continue
        if getattr(o, "_deleted", False):
            continue
        return o
    raise LookupError((cls, text, name))
