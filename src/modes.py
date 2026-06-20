"""Turn a mode config into a runnable parameter generator.

A mode is described by an INI file in `modes/`; the file's name (without
extension) is the mode token passed as the first argument to every sample.

Declarative form (random hex of fixed sizes):

    [mode]
    params = x:2048, key:32, s:16      ; "name:bytes"; the name is optional

Scripted form (irregular generation, e.g. merge):

    [mode]
    generator = merge                  ; -> generators/merge.py
    size      = 32                     ; any extra keys are passed as `options`
    slots     = 5
    fill_min  = 2
    fill_max  = 5
"""

import configparser
import importlib.util
import os

from src.config import ConfigError
from src.util import new_ini_parser, rng_hex


class Mode:
    def __init__(self, name, generate, param_names):
        self.name = name                # token passed to executables
        self._generate = generate       # callable(rng) -> list[str]
        self.param_names = param_names  # list[str|None] or None

    def generate(self, rng):
        return self._generate(rng)

    def label_for(self, index):
        """Human-readable label for the parameter at position `index` (0-based)."""
        if self.param_names and index < len(self.param_names):
            name = self.param_names[index]
            if name:
                return name
        return f"Param{index + 1}"


def mode_definition_exists(name, modes_dir):
    return os.path.exists(os.path.join(modes_dir, name + ".cfg"))


def load_mode(name, modes_dir, generators_dir):
    """Load and build a Mode by name. Raises ConfigError on problems."""
    cfg_path = os.path.join(modes_dir, name + ".cfg")
    if not os.path.exists(cfg_path):
        raise ConfigError(f"mode '{name}': definition not found ({cfg_path})")

    parser = new_ini_parser()
    try:
        parser.read(cfg_path, encoding="utf-8")
    except configparser.Error as exc:
        raise ConfigError(f"mode '{name}': cannot parse {cfg_path}: {exc}")

    if not parser.has_section("mode"):
        raise ConfigError(f"mode '{name}': missing [mode] section in {cfg_path}")
    section = parser["mode"]

    has_params = "params" in section
    has_generator = "generator" in section
    if has_params and has_generator:
        raise ConfigError(
            f"mode '{name}': specify either 'params' or 'generator', not both")
    if not has_params and not has_generator:
        raise ConfigError(f"mode '{name}': must define 'params' or 'generator'")

    if has_params:
        return _build_declarative(name, section["params"])
    return _build_scripted(name, section, generators_dir)


def _build_declarative(name, raw_params):
    specs = _parse_params(name, raw_params)        # list of (name|None, n_bytes)
    names = [pname for (pname, _) in specs]
    sizes = [nbytes for (_, nbytes) in specs]

    def generate(rng):
        return [rng_hex(rng, nbytes) for nbytes in sizes]

    return Mode(name=name, generate=generate, param_names=names)


def _build_scripted(name, section, generators_dir):
    gen_name = section["generator"].strip()
    if not gen_name:
        raise ConfigError(f"mode '{name}': 'generator' is empty")
    options = {key: value for key, value in section.items() if key != "generator"}
    gen_func = _load_generator(name, gen_name, generators_dir)

    def generate(rng):
        result = gen_func(rng, options)
        if not isinstance(result, list) or not all(isinstance(x, str) for x in result):
            raise ConfigError(
                f"mode '{name}': generator '{gen_name}' must return a list of strings")
        return result

    # Scripted generators don't declare param names; fall back to Param{i}.
    return Mode(name=name, generate=generate, param_names=None)


def _parse_params(name, raw):
    tokens = split_tokens(raw)
    if not tokens:
        raise ConfigError(f"mode '{name}': 'params' is empty")
    specs = []
    for token in tokens:
        if ":" in token:
            pname, _, size_str = token.partition(":")
            pname = pname.strip() or None
        else:
            pname, size_str = None, token
        size_str = size_str.strip()
        try:
            nbytes = int(size_str)
        except ValueError:
            raise ConfigError(
                f"mode '{name}': invalid byte size '{size_str}' in params")
        if nbytes < 1:
            raise ConfigError(
                f"mode '{name}': byte size must be >= 1 (got {nbytes}) in params")
        specs.append((pname, nbytes))
    return specs


def split_tokens(raw):
    return [item.strip() for item in raw.split(",") if item.strip()]


def _load_generator(mode_name, gen_name, generators_dir):
    gen_path = os.path.join(generators_dir, gen_name + ".py")
    if not os.path.exists(gen_path):
        raise ConfigError(f"mode '{mode_name}': generator not found ({gen_path})")

    spec = importlib.util.spec_from_file_location(f"_stand_generator_{gen_name}", gen_path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - report any import-time failure cleanly
        raise ConfigError(
            f"mode '{mode_name}': failed to import generator '{gen_name}': {exc}")

    if not hasattr(module, "generate") or not callable(module.generate):
        raise ConfigError(
            f"mode '{mode_name}': generator '{gen_name}' must define "
            "generate(rng, options)")
    return module.generate
