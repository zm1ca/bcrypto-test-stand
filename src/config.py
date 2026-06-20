"""Discovery and loading of sample configuration files.

A sample is one program under test, described by an INI file in `samples/`.
The file's name (without extension) is the sample's name.

    [sample]
    path         = path/to/binary   ; relative to project root, or absolute (required)
    modes        = cfb, ctr, mac    ; comma-separated list of supported modes (required)
    cmd          = wine             ; interpreter/wrapper for all platforms (optional)
    cmd_win      = ...              ; Windows (optional, overrides cmd)
    cmd_linux    = ...              ; Linux x86-64 (optional, overrides cmd)
    cmd_linux_arm = ...             ; Linux ARM64 (optional, overrides cmd)
    cmd_mac      = ...              ; macOS Intel (optional, overrides cmd)
    cmd_mac_arm  = ...              ; macOS Apple Silicon (optional, overrides cmd)
    tag          = My label         ; log label; defaults to the filename (optional)
"""

import configparser
import os
import platform
import sys

from src.util import new_ini_parser, split_csv


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
        self.modes = modes      # list[str] of supported mode names (ASN.1 names)
        self.cmd = cmd          # optional interpreter, or None
        self.tag = tag          # log label
        self.mode_aliases = mode_aliases or {}  # ASN.1 name -> token the executable expects

    def argv(self, mode, params):
        """Build the argument vector for one invocation."""
        effective_mode = self.mode_aliases.get(mode, mode)
        if self.cmd:
            return [self.cmd, self.path, effective_mode, *params]
        return [self.path, effective_mode, *params]


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

    raw_aliases = section.get("mode_aliases", "").strip()
    mode_aliases = {}
    for item in split_csv(raw_aliases):
        if ":" in item:
            asn1_name, _, alias = item.partition(":")
            mode_aliases[asn1_name.strip()] = alias.strip()

    platform_key = _platform_cmd_key()
    cmd = (
        (section.get(platform_key, "").strip() if platform_key else "") or
        section.get("cmd", "").strip() or
        None
    )
    tag = section.get("tag", "").strip() or os.path.basename(resolved)

    return Sample(name=name, path=resolved, modes=modes, cmd=cmd, tag=tag,
                  mode_aliases=mode_aliases)
