"""Auto-Profiles rules: pick a profile for the foreground program (no Qt).

configs/auto_profiles.json holds groups. Each group has a match (exe, title
or product-name wildcards) and profiles with priorities; the first enabled
profile by ascending priority wins when a group matches. The file is created
from the existing profiles on first use and hot-reloaded when edited.

v108.170: a profile saved or loaded with a target program is listed in that
program's group (a group made for it when there is none), so Switch to… and
Auto Load know it. Before, only the profiles that existed when the file was
first made were in it.
"""

import fnmatch
import json
import ntpath
import os

from .paths import CONFIG_DIR
from .settings import ensure_dir

AUTO_PROFILES_FILE = os.path.join(CONFIG_DIR, "auto_profiles.json")
AUTO_PROFILE_POLL_MS = 1500
# The copy of the loaded profile kept for the next start: never a profile of a rule.
NOT_PROFILES = ("last_config.json",)


def _lower(s):
    """Stripped, lower-case text; empty for anything that is not text."""
    try:
        return (s or "").strip().lower()
    except Exception:
        return ""


def profile_abs_path(path, config_dir=None):
    """Resolve a profile path relative to the configs folder."""
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(config_dir or CONFIG_DIR, path)


def file_exists(path):
    """True when the path is an existing file (never raises)."""
    try:
        return os.path.isfile(path)
    except Exception:
        return False


def open_in_os(path: str, select: bool = False) -> None:
    """Open a file or folder with the operating system (Explorer on Windows)."""
    if not path:
        return
    try:
        import subprocess as subprocess
        import sys as sys

        if sys.platform.startswith("win"):
            if select and os.path.exists(path):
                subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
            else:
                os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


def _same_file(a, b):
    """True when two paths name the same file."""
    try:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))
    except (TypeError, ValueError):
        return False


def _rule_path(profile_path, config_dir=None):
    """How a rule names a profile: its file name in the configs folder, else its full path."""
    full = os.path.abspath(profile_path)
    folder = os.path.abspath(config_dir or CONFIG_DIR)
    if os.path.normcase(os.path.dirname(full)) == os.path.normcase(folder):
        return os.path.basename(full)
    return full


def _plain_exe_group(group, exe_base):
    """True for a group that matches the program by its exe only (no title or product patterns)."""
    match = (group or {}).get("match") or {}
    patterns = [p for p in match.get("exe", []) if p]
    if not patterns or any(match.get(key) for key in ("title", "product")):
        return False
    return any(fnmatch.fnmatch(exe_base, _lower(p)) for p in patterns)


def link_profile_to_program(profile_path, exe_path, program_name="", cfg_path=AUTO_PROFILES_FILE):
    """List `profile_path` in the Auto-Profiles group of the program `exe_path` (v108.170).

    The group is the first one that matches the program by its exe name
    alone; one is made (named `program_name`) when there is none. The profile
    goes last, with the next priority. Returns "added", "present" (it was
    there, enabled or not) or "" (nothing to do, or the rules file could not
    be read: a file being edited by hand is never overwritten).
    """
    exe_name = ntpath.basename(exe_path or "")  # a Windows path: "/" or "\\"
    exe_base = _lower(exe_name)
    if not exe_base or not profile_path or os.path.basename(profile_path).lower() in NOT_PROFILES:
        return ""
    data = {"groups": []}
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return ""
        if not isinstance(data, dict) or not isinstance(data.get("groups", []), list):
            return ""
    groups = data.setdefault("groups", [])
    folder = os.path.dirname(cfg_path)
    group = next((g for g in groups if _plain_exe_group(g, exe_base)), None)
    if group is None:
        name = str(program_name or "").strip() or os.path.splitext(exe_name)[0]
        group = {
            "name": name,
            "enabled": True,
            "match": {"exe": [exe_name]},
            "profiles": [],
        }
        groups.append(group)
    profiles = group.setdefault("profiles", [])
    for p in profiles:
        if p and _same_file(profile_abs_path(p.get("path", ""), folder), profile_path):
            return "present"
    priorities = []
    for p in profiles:
        try:
            priorities.append(int((p or {}).get("priority", 0)))
        except (TypeError, ValueError):
            pass
    priority = max(priorities) + 1 if priorities else 1
    profiles.append({"path": _rule_path(profile_path, folder), "priority": priority, "enabled": True})
    ensure_dir(folder)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return "added"


def unlink_profile_from_program(profile_path, exe_path, cfg_path=AUTO_PROFILES_FILE):
    """Take `profile_path` out of every Auto-Profiles group that matches the program `exe_path`.

    A group matches when one of its exe patterns fits the program's file
    name. Other groups, and the rest of the file, are left as they are.
    Returns how many entries were removed (0 when the file is missing).
    """
    exe_base = _lower(os.path.basename(exe_path or ""))
    if not exe_base or not os.path.isfile(cfg_path):
        return 0
    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return 0
    removed = 0
    for group in data.get("groups", []) if isinstance(data, dict) else []:
        patterns = [p for p in ((group or {}).get("match") or {}).get("exe", []) if p]
        if not any(fnmatch.fnmatch(exe_base, _lower(p)) for p in patterns):
            continue
        profiles = group.get("profiles", [])
        keep = [
            p for p in profiles if not (p and _same_file(profile_abs_path(p.get("path", "")), profile_path))
        ]
        removed += len(profiles) - len(keep)
        group["profiles"] = keep
    if removed:
        ensure_dir(os.path.dirname(cfg_path))
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    return removed


class AutoProfileManager:
    """
    Load groups from configs/auto_profiles.json and pick first enabled profile
    by ascending 'priority' when a group's match passes.
    """

    def __init__(self, cfg_path: str = AUTO_PROFILES_FILE):
        """Remember the rules file path and start with no rules loaded."""
        self.cfg_path = cfg_path
        self._groups = []
        self._mtime = 0.0

    def _read_json(self, path: str):
        """Read a JSON file, or None when it is missing or invalid."""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write_json(self, path: str, data: dict):
        """Write the rules file as indented UTF-8 JSON."""
        ensure_dir(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _bootstrap_from_existing_profiles(self) -> dict:
        """Build first-use rules from the target programs saved in existing profiles."""
        groups = []
        by_app = {}

        try:
            for fname in sorted(os.listdir(CONFIG_DIR)):
                if not fname.lower().endswith(".json"):
                    continue
                fpath = os.path.join(CONFIG_DIR, fname)
                try:
                    with open(fpath, encoding="utf-8") as f:
                        raw = json.load(f)
                except Exception:
                    raw = {}
                # v108.170: profiles with a target program only. Before, every
                # .json file (last_config.json and the settings files too) made
                # a group, and one without a program matched every program.
                if (
                    not isinstance(raw, dict)
                    or not isinstance(raw.get("axes"), dict)
                    or not raw.get("target_exe")
                    or fname.lower() in NOT_PROFILES
                ):
                    continue

                app = (
                    raw.get("target_app_name") or raw.get("target_product_name") or os.path.splitext(fname)[0]
                )
                exe = raw.get("target_exe") or ""
                app_norm = app.strip() if isinstance(app, str) else str(app)
                by_app.setdefault(app_norm, []).append(fname)
        except Exception:
            pass

        for app_name, files in by_app.items():
            exe_bases = set()
            for fname in files:
                try:
                    with open(os.path.join(CONFIG_DIR, fname), encoding="utf-8") as f:
                        raw = json.load(f)
                    exe = raw.get("target_exe") or ""
                    if exe:
                        exe_bases.add(os.path.basename(exe))
                except Exception:
                    continue
            match = {"exe": sorted(exe_bases)} if exe_bases else {}

            profiles = []
            for i, fname in enumerate(sorted(files), start=1):
                profiles.append({"path": fname, "priority": i, "enabled": True})

            groups.append(
                {
                    "name": app_name,
                    "enabled": True,
                    "match": match,
                    "profiles": profiles,
                }
            )

        return {"groups": groups}

    def load(self):
        """Load the rules file, creating it from existing profiles when missing."""
        need_bootstrap = not os.path.exists(self.cfg_path)
        if need_bootstrap:
            try:
                self._write_json(self.cfg_path, self._bootstrap_from_existing_profiles())
            except Exception:
                self._write_json(self.cfg_path, {"groups": []})
        self._reload()

    def _reload(self):
        """Re-read the rules file and remember its modification time."""
        try:
            st = os.stat(self.cfg_path)
            self._mtime = float(st.st_mtime)
        except Exception:
            self._mtime = 0.0

        try:
            data = self._read_json(self.cfg_path)
            self._groups = list(data.get("groups", []))
        except Exception:
            self._groups = []

    def reload(self):
        """Re-read the rules file now (after the Mapper wrote it)."""
        self._reload()

    def reload_if_changed(self):
        """Re-read the rules file when it was edited since the last read."""
        try:
            st = os.stat(self.cfg_path)
            if float(st.st_mtime) > self._mtime:
                self._reload()
        except Exception:
            pass

    def _match_group(self, exe_base: str, title: str, product_name: str):
        """Find the first enabled group whose exe, title or product pattern matches."""
        eb = _lower(exe_base)
        tt = _lower(title)
        pn = _lower(product_name)

        for g in self._groups:
            if not g or not g.get("enabled", True):
                continue
            m = g.get("match", {}) or {}
            ok = True

            exe_pats = [p for p in m.get("exe", []) if p]
            if not exe_pats and not any(m.get(key) for key in ("title", "product")):
                continue  # v108.170: no pattern at all matches nothing (it matched every program)
            if exe_pats:
                ok = any(fnmatch.fnmatch(eb, _lower(p)) for p in exe_pats)

            title_pats = [p for p in m.get("title", []) if p]
            if ok and title_pats:
                ok = any(fnmatch.fnmatch(tt, _lower(p)) for p in title_pats)

            prod_pats = [p for p in m.get("product", []) if p]
            if ok and prod_pats:
                ok = any(fnmatch.fnmatch(pn, _lower(p)) for p in prod_pats)

            if ok:
                return g
        return None

    def pick_profile_for(self, exe_base: str, title: str, product_name: str) -> str:
        """The profile to load for a program: the matching group's top-priority entry."""
        g = self._match_group(exe_base, title, product_name)
        if not g:
            return ""
        profs = [p for p in g.get("profiles", []) if p and p.get("enabled", True)]
        if not profs:
            return ""
        profs.sort(key=lambda p: (int(p.get("priority", 9999)), str(p.get("path", ""))))
        for p in profs:
            path = profile_abs_path(p.get("path", ""), os.path.dirname(self.cfg_path))
            if file_exists(path) and os.path.basename(path).lower() not in NOT_PROFILES:
                return path
        return ""

    def candidates_for_current(self, exe_base: str, title: str, product_name: str):
        """Every enabled profile of the matching group, by priority (for Switch to…)."""
        g = self._match_group(exe_base, title, product_name)
        if not g:
            return []
        profs = [p for p in g.get("profiles", []) if p and p.get("enabled", True)]
        profs.sort(key=lambda p: (int(p.get("priority", 9999)), str(p.get("path", ""))))
        out = []
        for p in profs:
            abs_path = profile_abs_path(p.get("path", ""), os.path.dirname(self.cfg_path))
            if file_exists(abs_path) and os.path.basename(abs_path).lower() not in NOT_PROFILES:
                out.append((abs_path, int(p.get("priority", 9999))))
        return out
