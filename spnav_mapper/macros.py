"""Bind macros: the step format and a non-blocking player (v108.141).

A macro is a list of steps, saved with the bind in the profile:

    {"tap": ["ctrl", "s"]}   press and release a key or combo
    {"down": ["shift"]}      press and keep holding
    {"up": ["shift"]}        release
    {"delay": 100}           wait, in milliseconds

MacroRun plays one macro without blocking: waits are scheduled (the caller
passes a ``schedule(ms, callback)`` such as QTimer.singleShot), so reading the
SpaceNavigator never pauses. A run that is stopped, or that ends with keys
still held by a Down step, releases them, so a macro never leaves a key stuck.
"""

MAX_STEPS = 50
MAX_DELAY_MS = 10_000
KINDS = ("tap", "down", "up", "delay")


def _tokens(value):
    """Key tokens of a macro step value, lower-cased."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(t).strip().lower() for t in value if str(t).strip()]


def normalize_step(step):
    """A valid step dict, or None."""
    if not isinstance(step, dict):
        return None
    for kind in KINDS:
        if kind not in step:
            continue
        if kind == "delay":
            try:
                ms = int(step[kind])
            except (TypeError, ValueError):
                return None
            return {"delay": max(0, min(MAX_DELAY_MS, ms))}
        tokens = _tokens(step[kind])
        return {kind: tokens} if tokens else None
    return None


def normalize_macro(steps):
    """The valid steps of `steps` (at most MAX_STEPS); [] for anything else."""
    if not isinstance(steps, (list, tuple)):
        return []
    out = []
    for step in steps:
        clean = normalize_step(step)
        if clean is not None:
            out.append(clean)
        if len(out) >= MAX_STEPS:
            break
    return out


def step_text(step):
    """How a step reads in the editor and tooltips, e.g. "Tap CTRL+S" or "Delay 100 ms"."""
    step = normalize_step(step) or {}
    if "delay" in step:
        return f"Delay {step['delay']} ms"
    for kind, word in (("tap", "Tap"), ("down", "Down"), ("up", "Up")):
        if kind in step:
            return f"{word} {'+'.join(t.upper() for t in step[kind])}"
    return "?"


MODIFIERS = ("ctrl", "shift", "alt")


def _keys_up_long_enough(actions, min_up_ms):
    """Insert waits so a key released is up `min_up_ms` before it is pressed again (v108.167).

    Two Tap steps of the same key in a row released it and pressed it again at
    once, so a game could see one press. A Delay between them counts towards
    the time; modifiers (Ctrl, Shift, Alt) are not waited for.
    """
    out, up_for = [], {}  # a key released -> ms since its release
    for kind, value in actions:
        if kind == "wait":
            up_for = {key: ms + int(value) for key, ms in up_for.items()}
        elif kind == "down":
            again = [min_up_ms - up_for[t] for t in value if t in up_for and t not in MODIFIERS]
            if again and max(again) > 0:
                out.append(("wait", max(again)))
                up_for = {key: ms + max(again) for key, ms in up_for.items()}
            for t in value:
                up_for.pop(t, None)
        else:  # up
            up_for.update({t: 0 for t in value})
        out.append((kind, value))
    return out


def expand(steps, tap_ms=45, min_up_ms=0):
    """The key events and waits of one run: [("down", tokens) | ("up", tokens) | ("wait", ms)].

    `min_up_ms`: the shortest time a released key is up before it is pressed again.
    """
    actions = []
    for step in normalize_macro(steps):
        if "tap" in step:
            actions += [("down", step["tap"]), ("wait", tap_ms), ("up", step["tap"])]
        elif "down" in step:
            actions.append(("down", step["down"]))
        elif "up" in step:
            actions.append(("up", step["up"]))
        elif step["delay"] > 0:
            actions.append(("wait", step["delay"]))
    return _keys_up_long_enough(actions, min_up_ms) if min_up_ms > 0 else actions


class MacroRun:
    """One playing of a macro.

    send(tokens, down) presses or releases a key or combo; schedule(ms,
    callback) calls back later without blocking; on_done() is called once,
    when the run ends or is stopped.
    """

    def __init__(self, steps, send, schedule, tap_ms=45, on_done=None, min_up_ms=0):
        """Prepare a run of a macro with the key sender and scheduler to use."""
        self._actions = expand(steps, max(0, min(200, int(tap_ms))), max(0, int(min_up_ms)))
        self._send, self._schedule, self._on_done = send, schedule, on_done
        self._next = 0
        self._held = []  # tokens pressed and not yet released, in press order
        self.running = False

    def start(self):
        """Start playing the macro from its first step."""
        if self.running or self._next:
            return
        self.running = True
        self._advance()

    def _advance(self):
        """Play steps until the next delay, then schedule the rest."""
        while self.running and self._next < len(self._actions):
            kind, value = self._actions[self._next]
            self._next += 1
            if kind == "wait":
                self._schedule(int(value), self._resume)
                return
            tokens = list(value)
            if kind == "down":
                self._send(tokens, True)
                self._held.append(tokens)
            else:
                self._send(tokens, False)
                for i in range(len(self._held) - 1, -1, -1):
                    if self._held[i] == tokens:
                        del self._held[i]
                        break
        if self.running:
            self._finish()

    def _resume(self):
        """Continue after a delay unless the run was stopped."""
        if self.running:
            self._advance()

    def stop(self):
        """Stop now and release whatever this run still holds down."""
        if self.running:
            self._finish()

    def _finish(self):
        """End the run, release held keys and report completion."""
        self.running = False
        held, self._held = self._held, []
        for tokens in reversed(held):
            self._send(tokens, False)
        if self._on_done is not None:
            self._on_done()
