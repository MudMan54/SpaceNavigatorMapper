"""The rebound settle guard (v108.177; "Rebound" in the editor): the spring's bounce is not a new push.

Let go of the puck from a high band and its spring throws it back past the
centre and out again for a moment. To the binds that bounce looks like a new
push: a lower bind's NoBack is rearmed the moment the axis centres, and a
lower Tick is crossed going out again, so the spring sends the lower key.

The guard, kept for one bind on one axis side: once a band higher than the
bind was reached, the bind may not start again until the axis has rested
below the bind's own start (or at the centre, or on the other side) for the
bind's Rebound time (`settle_ms`) without a break. A hand takes longer than that to come
back; the spring does not. Only the way back from a higher band arms it: the
way out is never held, and neither is a bind with nothing above it.
"""

SETTLE_MS_DEFAULT = 0  # v108.179: off until a time is chosen (it was 150 in the v108.177/178 tests)
SETTLE_MS_RECOMMENDED = 150  # the starting point the editor recommends
SETTLE_MS_MAX = 500
# The Bind button's right-click menu offers these (0: Off).
SETTLE_MS_CHOICES = (0, 50, 100, 150, 200, 250, 300, 400, 500)


def clamp_settle_ms(value, default=SETTLE_MS_DEFAULT):
    """A Rebound time in ms, 0 (off) to 500 (`default` for one that is not a number)."""
    try:
        return max(0, min(SETTLE_MS_MAX, int(value)))
    except (TypeError, ValueError):
        return max(0, min(SETTLE_MS_MAX, int(default)))


def settle_text(ms):
    """'150 ms', or 'Off' for 0."""
    return f"{int(ms)} ms" if int(ms) > 0 else "Off"


class SettleGuard:
    """One bind's guard on one axis side."""

    __slots__ = ("armed", "below_since")

    def __init__(self):
        """Nothing higher reached yet."""
        self.armed = False  # a higher band was reached and the axis has not settled since
        self.below_since = None  # when the axis came to rest below the bind's start

    def sample(self, now, magnitude, start, higher_reached, settle_ms):
        """Take a new axis sample; True while the bind may not start.

        `magnitude` is the axis's distance from centre on this side in percent
        (0 at the centre or on the other side), `start` where the bind's band
        starts (its Tick%), `higher_reached` whether the axis is in a band
        that starts higher, `now` in seconds.

        The answer is the state before this sample: a higher band reached on
        this very sample (a fast push through both) does not hold the bind on
        its way out. The rest is measured up to this sample, so it counts
        whether samples kept coming while the axis rested or not.
        """
        if self.armed and self.below_since is not None and (now - self.below_since) * 1000.0 >= settle_ms:
            self.armed = False  # rested long enough: the next push is a hand's
        held = self.armed
        if magnitude <= 0 or magnitude < start:
            if self.below_since is None:
                self.below_since = now
        else:
            self.below_since = None  # at or beyond the bind's start: the rest starts over
            if higher_reached:
                self.armed = True
        return held
