"""Taps that do not stop the Mapper, with time for the key to be seen up (v108.167).

Before v108.167 a tap pressed its key, slept for its Tap Dwell on the GUI
thread and released it. While it slept nothing else ran: the SpaceNavigator
was not read, the other axes and binds waited, and a Press/Repeat bind with a
short Repeat every and a long Tap Dwell kept the Mapper asleep most of the
time. And the key was up only for what was left of Repeat every after the
dwell (with Repeat every 60 ms and a 45 ms dwell, 15 ms; none at all when
Repeat every was shorter than the dwell), so a game reading its keys once a
frame could miss the release, and see one long press.

Now a tap presses its key and schedules the release after its dwell; the
Mapper keeps running. A key that has just been tapped stays up at least
MIN_UP_MS before it is pressed again: a tap of it asked for meanwhile (the same
bind re-entering its band, another bind with the same key) waits, and taps
asked for while one waits make one tap, not a queue that goes on after the
axis has left the band. release_all() releases every tap still down at once
(output switched off, the Mapper exiting) and drops the ones waiting.
"""

from ..settings import MIN_KEY_UP_MS

# The shortest time a tapped key is up before it is pressed again: a game that
# reads its keys at 60 frames a second (16.7 ms a frame) sees the release.
MIN_UP_MS = MIN_KEY_UP_MS


def tap_key(combo):
    """What identifies a combination: its keys, lower-cased, in order."""
    return tuple(str(t).strip().lower() for t in (combo or ()) if str(t).strip())


def repeat_interval_ms(repeat_ms, dwell_ms):
    """Press/Repeat's time from one tap to the next: Repeat every, but never
    less than the Tap Dwell plus MIN_UP_MS (the key must be seen up)."""
    return max(int(repeat_ms), int(dwell_ms) + MIN_UP_MS)


class TapSender:
    """Sends taps for every axis of a window (one per window, shared by its panels).

    send(combo, down) presses or releases a combination; schedule(ms,
    callback) calls back later without blocking; clock() is the time in
    seconds.
    """

    def __init__(self, send, schedule, clock):
        """Taps through `send`, timed with `schedule` and `clock`."""
        self._send, self._schedule, self._clock = send, schedule, clock
        self._keys = {}  # tap_key -> state of that combination

    def _state(self, key):
        """The state of one combination's taps (made the first time)."""
        return self._keys.setdefault(
            key, {"combo": None, "down": False, "free_at": 0.0, "waiting": None, "run": 0}
        )

    def tap(self, combo, dwell_ms):
        """Tap `combo` for `dwell_ms`: now, or once the same keys have been up MIN_UP_MS.

        Returns "sent", "waiting" (it starts later) or "joined" (one was already
        waiting: it stands for both).
        """
        key = tap_key(combo)
        if not key:
            return "none"
        state = self._state(key)
        wait_ms = (state["free_at"] - self._clock()) * 1000.0
        if state["down"] or wait_ms > 0:
            joined = state["waiting"] is not None
            state["waiting"] = (list(combo), int(dwell_ms))
            if not joined and not state["down"]:
                run = state["run"]
                self._schedule(int(wait_ms) + 1, lambda k=key, r=run: self._start_waiting(k, r))
            return "joined" if joined else "waiting"
        self._press(key, list(combo), int(dwell_ms))
        return "sent"

    def _press(self, key, combo, dwell_ms):
        """Press now; the release is scheduled after the dwell."""
        state = self._state(key)
        state.update(combo=combo, down=True, waiting=None)
        state["run"] += 1
        run = state["run"]
        self._send(combo, True)
        self._schedule(max(0, dwell_ms), lambda k=key, r=run: self._release(k, r))

    def _release(self, key, run):
        """The dwell is over: release, then start a tap that waited (after MIN_UP_MS)."""
        state = self._keys.get(key)
        if state is None or state["run"] != run or not state["down"]:
            return  # released already (release_all)
        state["down"] = False
        self._send(state["combo"], False)
        state["free_at"] = self._clock() + MIN_UP_MS / 1000.0
        if state["waiting"] is not None:
            self._schedule(MIN_UP_MS, lambda k=key, r=run: self._start_waiting(k, r))

    def _start_waiting(self, key, run):
        """Start the tap that waited for the keys to have been up long enough."""
        state = self._keys.get(key)
        if state is None or state["run"] != run or state["down"] or state["waiting"] is None:
            return
        if self._clock() < state["free_at"] - 0.0005:  # called a little early
            self._schedule(1, lambda k=key, r=run: self._start_waiting(k, r))
            return
        combo, dwell_ms = state["waiting"]
        self._press(key, combo, dwell_ms)

    def held(self):
        """The combinations a tap has down now."""
        return [state["combo"] for state in self._keys.values() if state["down"]]

    def release_all(self):
        """Release every tap still down, at once, and drop the taps waiting."""
        now = self._clock()
        for state in self._keys.values():
            # Kept (not forgotten): a release or waiting tap scheduled for it
            # sees the new run and does nothing.
            state["run"] += 1
            state["waiting"] = None
            if state["down"]:
                state["down"] = False
                self._send(state["combo"], False)
                state["free_at"] = now + MIN_UP_MS / 1000.0
