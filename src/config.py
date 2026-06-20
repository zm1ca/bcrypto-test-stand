"""Discovery and loading of sample configuration files.

A sample is one program under test, described by an INI file in `configs/`.
The file's name (without extension) is the sample's name.

    [sample]
    cmd   = luajit                 ; optional interpreter; omit to run directly
    path  = PAZL/pazl-cmd.lua      ; relative to project root, or absolute
    modes = cfb, ctr, mac, hsh     ; comma-separated list of supported modes
    tag   = PAZL reference         ; optional log label; defaults to the basename
"""

import configparser
import os

from src.util import new_ini_parser, split_csv


class ConfigError(Exception):
    """Raised for any problem with a config file or a requested name."""


class Sample:
    def __init__(self, name, path, modes, cmd=None, tag=None):
        self.name = name        # registration name (config file stem)
        self.path = path        # resolved, absolute path to the executable/script
        self.modes = modes      # list[str] of supported mode names
        self.cmd = cmd          # optional interpreter, or None
        self.tag = tag          # log label

    def argv(self, mode, params):
        """Build the argument vector for one invocation."""
        if self.cmd:
            return [self.cmd, self.path, mode, *params]
        return [self.path, mode, *params]


def load_sample(name, configs_dir, project_root):
    """Load and validate a single sample by name. Raises ConfigError on problems."""
    cfg_path = os.path.join(configs_dir, name + ".cfg")
    if not os.path.exists(cfg_path):
        raise ConfigError(f"sample '{name}': config not found ({cfg_path})")

    parser = new_ini_parser()
    try:
        parser.read(cfg_path, encoding="utf-8")
    except configparser.Error as exc:
        raise ConfigError(f"sample '{name}': cannot parse {cfg_path}: {exc}")

    if not parser.has_section("sample"):
        raise ConfigError(f"sample '{name}': missing [sample] section in {cfg_path}")
    section = parser["sample"]

    raw_path = section.get("path", "").strip()
    if not raw_path:
        raise ConfigError(f"sample '{name}': 'path' is required in {cfg_path}")

    resolved = raw_path if os.path.isabs(raw_path) else os.path.join(project_root, raw_path)
    resolved = os.path.normpath(resolved)
    if not os.path.exists(resolved):
        raise ConfigError(f"sample '{name}': executable not found: {resolved}")

    modes = split_csv(section.get("modes", ""))
    if not modes:
        raise ConfigError(
            f"sample '{name}': 'modes' is required (comma-separated) in {cfg_path}")

    cmd = section.get("cmd", "").strip() or None
    tag = section.get("tag", "").strip() or os.path.basename(resolved)

    return Sample(name=name, path=resolved, modes=modes, cmd=cmd, tag=tag)
