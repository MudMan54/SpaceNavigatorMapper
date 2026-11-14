"""3Dconnexion six-axis HID devices: finding, reading and decoding reports, and the LED."""

import struct
import time

try:
    import hid
except Exception:
    hid = None

try:
    import pywinusb.hid as hidwin

    _PWIN_OK = True
    _PWIN_ERR = None
except Exception as e:
    hidwin = None
    _PWIN_OK = False
    _PWIN_ERR = e

VENDOR_ID = 0x046D
PRODUCT_ID = 0xC626  # Original SpaceNavigator; retained for compatibility.
# Legacy Logitech/3Dconnexion USB product IDs. Device selection is automatic;
# if multiple supported devices are connected, the existing SpaceNavigator
# remains the first preference to preserve prior behaviour.
SUPPORTED_PRODUCT_NAMES = {
    0xC623: "SpaceTraveler",
    0xC625: "SpacePilot",
    0xC626: "SpaceNavigator",
    0xC627: "SpaceExplorer",
    0xC628: "SpaceNavigator for Notebooks",
    0xC629: "SpacePilot Pro",
}
PREFERRED_DEVICE_ORDER = (0xC626, 0xC628, 0xC623, 0xC625, 0xC627, 0xC629)


def _spnav_interface_priority(info):
    """Prefer the USB multi-axis controller HID interface over button/LCD interfaces.

    hidapi exposes `usage_page`/`usage` on Windows. Many older devices have
    only one interface and some backends leave these fields unset.
    """
    try:
        page = int(info.get("usage_page") or 0)
        usage = int(info.get("usage") or 0)
        if page == 0x01 and usage == 0x08:  # Generic Desktop / Multi-axis Controller
            return 0
        if page == 0x01:
            return 1
        if page == 0:
            return 2
        return 3
    except (TypeError, ValueError, AttributeError):
        return 3


# --- SpaceNavigator parse helpers ---
def _sat(v: float) -> float:
    """Clamp a normalized axis value to the range -1.0 to +1.0."""
    if v > 1.0:
        return 1.0
    if v < -1.0:
        return -1.0
    return v


def _parse_sn_report(report):
    """Decode a HID report into translation, rotation or button data."""
    if not report or len(report) < 2:
        return None
    rid = report[0]
    if rid == 1 and len(report) >= 7:
        x = struct.unpack("<h", bytes(report[1:3]))[0]
        y = struct.unpack("<h", bytes(report[3:5]))[0]
        z = struct.unpack("<h", bytes(report[5:7]))[0]
        return ("translation", (x, y, z))
    if rid == 2 and len(report) >= 7:
        p = struct.unpack("<h", bytes(report[1:3]))[0]
        r = struct.unpack("<h", bytes(report[3:5]))[0]
        yaw = struct.unpack("<h", bytes(report[5:7]))[0]
        return ("rotation", (p, r, yaw))
    if rid == 3 and len(report) >= 2:
        # Button reports are 16 bits (Navigator/Explorer/Traveler), 24 bits
        # (SpacePilot), or 32 bits (SpacePilot Pro). Preserve the whole mask;
        # the existing UI intentionally maps only button #1/#2 at present.
        return ("buttons", int.from_bytes(bytes(report[1:5]), "little"))
    return None


# How often tick() checks that the opened device is still plugged in, in seconds.
PRESENCE_CHECK_S = 1.0


# --- Logitech / 3Dconnexion legacy six-axis HID devices ---
class SpaceNavigator:
    """Read any of the listed legacy USB 6-DOF models using the HID protocol.

    Axis reports 1 and 2 share the original SpaceNavigator layout. Button
    reports vary in width, but this app continues to bind the first two bits.
    No drivers, kernel modifications, or INF edits are made by this program.
    """

    def __init__(self):
        """Start with six zero axes, no buttons pressed and no device open."""
        self.dev = None
        self.axes = [0.0] * 6
        self.buttons = 0
        self._requested_led = False
        self.led_supported = True
        self._device_path = None
        self.product_id = None
        self.device_name = None
        self._pwin_dev = None
        self._disconnected = False
        self._next_presence_check = 0.0
        self._next_reopen_ts = 0.0

    def open(self):
        """Find and open the first supported 3Dconnexion HID device."""
        if hid is None:
            self.dev = None
            self._disconnected = True
            return False
        try:
            # Some products expose several HID interfaces (including LCD or
            # media buttons). Prefer the multi-axis controller interface.
            candidates = [
                i
                for i in hid.enumerate()
                if i.get("vendor_id") == VENDOR_ID
                and i.get("product_id") in SUPPORTED_PRODUCT_NAMES
                and i.get("path")
            ]
            candidates.sort(
                key=lambda i: (
                    PREFERRED_DEVICE_ORDER.index(i.get("product_id")),
                    _spnav_interface_priority(i),
                    int(i.get("interface_number") or 0)
                    if str(i.get("interface_number") or '0').lstrip('-').isdigit()
                    else 0,
                )
            )
            for info in candidates:
                path = info["path"]
                try:
                    if hasattr(hid, "Device"):
                        d = hid.Device(path=path)
                    else:
                        d = hid.device()
                        d.open_path(path)
                    try:
                        d.nonblocking = True
                    except Exception:
                        try:
                            d.set_nonblocking(1)
                        except Exception:
                            pass
                except Exception:
                    # An LCD-only/locked interface may be inaccessible. Try
                    # the next interface or next supported model.
                    continue
                self.dev = d
                self._device_path = path
                self.product_id = int(info["product_id"])
                self.device_name = SUPPORTED_PRODUCT_NAMES[self.product_id]
                self._disconnected = False
                self.led_supported = self.product_id == PRODUCT_ID
                if self.led_supported:
                    self.set_led(self._requested_led)
                return True
            self.dev = None
            self._device_path = None
            self.product_id = None
            self.device_name = None
            self._disconnected = True
            return False
        except Exception:
            self.dev = None
            self._device_path = None
            self.product_id = None
            self.device_name = None
            self._disconnected = True
            return False

    def close(self):
        """Close the HID handle and the LED fallback device."""
        try:
            if self.dev:
                try:
                    self.dev.close()
                except Exception:
                    pass
        finally:
            self.dev = None
            self._device_path = None
            self.product_id = None
            self.device_name = None
            # Unplugging a device must release any held axis/button inputs.
            self.axes = [0.0] * 6
            self.buttons = 0
        if self._pwin_dev:
            try:
                self._pwin_dev.close()
            except Exception:
                pass
            self._pwin_dev = None

    def _device_still_present(self):
        """True while the opened HID path is still enumerated."""
        if hid is None or not self._device_path or self.product_id is None:
            return False
        try:
            for i in hid.enumerate(VENDOR_ID, self.product_id):
                if i.get("path") == self._device_path:
                    return True
        except Exception:
            pass
        return False

    def tick(self):
        """Detect a disconnect (checked once a second) and try to reconnect at a timed interval.

        Called every GUI tick; listing the HID devices is slow, so the device's
        presence is checked at most every PRESENCE_CHECK_S seconds. A read
        error closes the device at once anyway.
        """
        now = time.perf_counter()
        if self.dev and now >= self._next_presence_check:
            self._next_presence_check = now + PRESENCE_CHECK_S
            if not self._device_still_present():
                self.close()
                self._disconnected = True
                self._next_reopen_ts = now
        if (self._disconnected or not self.dev) and now >= self._next_reopen_ts:
            if self.open():
                self._disconnected = False
            else:
                self._next_reopen_ts = now + 1.0

    def read(self):
        """Read pending HID reports into the six axes and two button bits."""
        if not self.dev:
            return
        try:
            for _ in range(5):
                data = self.dev.read(64)
                if not data:
                    break
                parsed = _parse_sn_report(data)
                if not parsed:
                    continue
                kind, val = parsed
                if kind == "translation":
                    x, y, z = val
                    self.axes[0] = _sat(float(x) / 350.0)
                    self.axes[1] = _sat(float(y) / 350.0)
                    self.axes[2] = _sat(float(z) / 350.0)
                elif kind == "rotation":
                    p, r, yaw = val
                    self.axes[3] = _sat(float(p) / 350.0)
                    self.axes[4] = _sat(float(r) / 350.0)
                    self.axes[5] = _sat(float(yaw) / 350.0)
                elif kind == "buttons":
                    self.buttons = val
        except OSError:
            self.close()
            self._disconnected = True
            self._next_reopen_ts = time.perf_counter() + 0.25
        except Exception:
            self.close()
            self._disconnected = True
            self._next_reopen_ts = time.perf_counter() + 0.5

    def _ensure_pwin_device(self):
        """Open the pywinusb device used for the LED fallback."""
        if self.product_id != PRODUCT_ID:
            return False, "LED control is limited to the original SpaceNavigator"
        if not _PWIN_OK:
            return False, f"pywinusb not available: {_PWIN_ERR!r}"
        try:
            dev = None
            for d in hidwin.find_all_hid_devices():
                if d.vendor_id == VENDOR_ID and d.product_id == self.product_id:
                    dev = d
                    break
            if dev is None:
                return False, "pywinusb: device not found"
            dev.open()
            self._pwin_dev = dev
            return True, "pywinusb: device opened"
        except Exception as e:
            self._pwin_dev = None
            return False, f"pywinusb open exception: {e}"

    def _set_led_pywinusb(self, on: bool):
        """Switch the device LED through pywinusb."""
        ok, info = self._ensure_pwin_device()
        if not ok:
            return False, info
        try:
            LED_USAGE = hidwin.get_full_usage_id(0x08, 0x4B)
            reports = self._pwin_dev.find_output_reports()
            for rpt in reports:
                try:
                    if LED_USAGE in rpt:
                        rpt[LED_USAGE] = bool(on)
                        rpt.send()
                        return True, "pywinusb: sent"
                except Exception:
                    pass
            for rpt in reports:
                wrote = False
                try:
                    for item in rpt:
                        try:
                            if hidwin.get_usage_page(item) == 0x08:
                                rpt[item] = bool(on)
                                wrote = True
                        except Exception:
                            pass
                    if wrote:
                        rpt.send()
                        return True, "pywinusb: page fallback"
                except Exception:
                    pass
            return False, "pywinusb: no LED usage"
        except Exception as e:
            return False, f"pywinusb exception: {e}"
        finally:
            try:
                if self._pwin_dev:
                    self._pwin_dev.close()
            except Exception:
                pass
            self._pwin_dev = None

    def _set_led_hidapi(self, on: bool):
        """Switch the device LED through hidapi."""
        if not self.dev or self.product_id != PRODUCT_ID:
            return False, "hidapi: LED control not supported on this device"
        val = 0x01 if on else 0x00
        candidate_report_ids = [0x06, 0x07, 0x08, 0x05]
        payload_lengths = [2, 8, 16, 32, 64]
        for rid in candidate_report_ids:
            for ln in payload_lengths:
                try:
                    buf = [0x00] * ln
                    buf[0] = rid
                    buf[1] = val
                    sent = self.dev.send_feature_report(buf)
                    if sent and sent > 0:
                        return True, f"feature {hex(rid)} len={ln}"
                except Exception:
                    pass
        for rid in candidate_report_ids:
            for ln in payload_lengths:
                try:
                    buf = [0x00] * ln
                    buf[0] = rid
                    buf[1] = val
                    written = self.dev.write(bytes(buf))
                    if written == ln:
                        return True, f"output {hex(rid)} len={ln}"
                except Exception:
                    pass
        return False, "hidapi: no variant accepted"

    def set_led(self, on: bool, status_callback=None):
        """Switch the device LED with the first backend that works."""
        self._requested_led = bool(on)
        if not self.dev:
            if status_callback:
                status_callback("No SpaceNavigator device connected")
            return False
        # Do not send speculative feature/output reports to hardware with
        # screens, many buttons, or different LED control protocols.
        if self.product_id != PRODUCT_ID:
            self.led_supported = False
            if status_callback:
                status_callback("LED control is unavailable for this device")
            return False
        if _PWIN_OK:
            ok, _ = self._set_led_pywinusb(on)
            if ok:
                self.led_supported = True
                return True
        ok2, _ = self._set_led_hidapi(on)
        if ok2:
            self.led_supported = True
            return True
        self.led_supported = False
        if status_callback:
            status_callback("Device LED not controllable")
        return False
