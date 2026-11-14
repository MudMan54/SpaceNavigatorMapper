"""Timestamped configuration recovery, independent of Qt and hardware."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


def _snapshot(directory, stem, data):
    """Write bytes into a folder under a unique time-stamped file name."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
    for suffix in range(1000):
        tail = f'_{suffix}' if suffix else ''
        path = directory / f'{stem}_{stamp}{tail}.json'
        try:
            with path.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            return path
        except FileExistsError:
            continue
        except OSError:
            path.unlink(missing_ok=True)
            raise
    raise OSError('Could not allocate a unique backup filename')


def save_with_backup(path, config, directory):
    """Preserve the previous bytes, then atomically replace the live profile.

    First-time saves back up the new configuration because no prior file exists.
    A backup failure aborts the save. Backups are never pruned automatically.
    """
    path = Path(path)
    data = json.dumps(config, indent=2, ensure_ascii=False).encode('utf-8')
    previous = path.read_bytes() if path.exists() else data
    backup = _snapshot(directory, path.stem, previous)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix='.spnav-', suffix='.tmp', delete=False
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return backup


def list_backups(directory):
    """The backup files in the backups folder, newest first."""
    root = Path(directory)
    if not root.exists():
        return []
    return sorted(root.glob('*.json'), key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)


def restore_backup(backup, config_directory):
    """Create a separate editable profile; leave the recovery copy untouched."""
    backup = Path(backup)
    data = backup.read_bytes()
    config = json.loads(data)
    if not isinstance(config, dict) or not isinstance(config.get('axes'), dict):
        raise ValueError('This file is not a SpaceNavigator configuration')
    return _snapshot(config_directory, backup.stem + '_restored', data)
