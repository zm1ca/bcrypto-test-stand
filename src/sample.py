"""Discovery and loading of sample configuration files.

A sample is one program under test, described by a JSON file in `samples/`.
The file's name (without extension) is the sample's name.

    {
      "path":          "path/to/binary",
      "modes":         [
        {"name": "belt-cfb", "alias": "cfb"},
        {"name": "belt-ctr"}
      ],
      "cmd":           "wine",
      "cmd_win":       "...",
      "cmd_linux":     "...",
      "cmd_linux_arm": "...",
      "cmd_mac":       "...",
      "cmd_mac_arm":   "...",
      "tag":           "My label"
    }

Each mode entry is an object with a required "name" and an optional "alias"
(the token the executable expects instead of the mode name).
"""

import json
import os
import platform
import sys


def _platform_cmd_key():
    p = sys.platform
    m = platform.machine().lower()
    if p == "win32":
        return "cmd_win"
    if p == "darwin":
        return "cmd_mac_arm" if m == "arm64" else "cmd_mac"
    if p.startswith("linux"):
        return "cmd_linux_arm" if m == "aarch64" else "cmd_linux"
    return None


class ConfigError(Exception):
    """Raised for any problem with a config file or a requested name."""


class Sample:
    def __init__(self, name, path, modes, cmd=None, tag=None, mode_aliases=None):
        self.name = name        # registration name (config file stem)
        self.path = path        # resolved, absolute path to the executable/script
        self.modes = modes      # list[str] of supported mode names
        self.cmd = cmd          # optional interpreter, or None
        self.tag = tag          # log label
        self.mode_aliases = mode_aliases or {}  # mode name -> alias the executable expects

    def argv(self, mode, params):
        """Build the argument vector for one invocation."""
        effective_mode = self.mode_aliases.get(mode, mode)
        if self.cmd:
            return [self.cmd, self.path, effective_mode, *params]
        return [self.path, effective_mode, *params]


def load_sample(name, configs_dir, project_root):
    """Load and validate a single sample by name. Raises ConfigError on problems."""
    cfg_path = os.path.join(configs_dir, name + ".json")
    if not os.path.exists(cfg_path):
        raise ConfigError(f"sample '{name}': config not found ({cfg_path})")

    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"sample '{name}': cannot parse {cfg_path}: {exc}")

    if not isinstance(data, dict):
        raise ConfigError(f"sample '{name}': expected a JSON object in {cfg_path}")

    raw_path = str(data.get("path", "")).strip()
    if not raw_path:
        raise ConfigError(f"sample '{name}': 'path' is required in {cfg_path}")

    resolved = raw_path if os.path.isabs(raw_path) else os.path.join(project_root, raw_path)
    resolved = os.path.normpath(resolved)
    if not os.path.exists(resolved):
        raise ConfigError(f"sample '{name}': executable not found: {resolved}")

    modes_raw = data.get("modes", [])
    if not isinstance(modes_raw, list) or not modes_raw:
        raise ConfigError(
            f"sample '{name}': 'modes' must be a non-empty array in {cfg_path}")
    modes = []
    mode_aliases = {}
    for i, entry in enumerate(modes_raw):
        if isinstance(entry, str):
            mode_name = entry.strip()
        elif isinstance(entry, dict):
            mode_name = str(entry.get("name", "")).strip()
            alias = str(entry.get("alias", "")).strip()
            if alias:
                mode_aliases[mode_name] = alias
        else:
            raise ConfigError(
                f"sample '{name}': modes[{i}] must be a string or object in {cfg_path}")
        if not mode_name:
            raise ConfigError(
                f"sample '{name}': modes[{i}] has an empty name in {cfg_path}")
        modes.append(mode_name)
    if not modes:
        raise ConfigError(f"sample '{name}': 'modes' is empty in {cfg_path}")

    platform_key = _platform_cmd_key()
    cmd = (
        (str(data.get(platform_key, "")).strip() if platform_key else "") or
        str(data.get("cmd", "")).strip() or
        None
    )
    tag = str(data.get("tag", "")).strip() or os.path.basename(resolved)

    return Sample(name=name, path=resolved, modes=modes, cmd=cmd, tag=tag,
                  mode_aliases=mode_aliases)
