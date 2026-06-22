"""Turn a mode config into a runnable parameter generator.

A mode is described by a JSON file in `modes/`; the file's name (without
extension) is the mode token passed as the first argument to every sample.

Declarative form (random hex of fixed sizes):

    {
      "docs":   "STB 34.101.31-2020 (7.5)",
      "params": [
        {"name": "msg", "bytes": 2048},
        {"name": "key", "bytes": 32}
      ]
    }

Scripted form (irregular generation, e.g. merge):

    {
      "docs":      "STB 34.101.60-2014 (7.4)",
      "generator": "merge",
      "options": {
        "size":     32,
        "slots":    5,
        "fill_min": 2,
        "fill_max": 5
      }
    }
"""

import importlib.util
import json
import os

from src.config import ConfigError
from src.util import rng_hex


class Mode:
    def __init__(self, name, generate, param_names, docs="", description=""):
        self.name = name
        self.docs = docs
        self.description = description
        self._generate = generate
        self.param_names = param_names

    def generate(self, rng, index=0):
        return self._generate(rng, index)

    def label_for(self, index):
        """Human-readable label for the parameter at position `index` (0-based)."""
        if self.param_names and index < len(self.param_names):
            name = self.param_names[index]
            if name:
                return name
        return f"Param{index + 1}"


def mode_definition_exists(name, modes_dir):
    return os.path.exists(os.path.join(modes_dir, name + ".json"))


def load_mode(name, modes_dir, generators_dir):
    """Load and build a Mode by name. Raises ConfigError on problems."""
    cfg_path = os.path.join(modes_dir, name + ".json")
    if not os.path.exists(cfg_path):
        raise ConfigError(f"mode '{name}': definition not found ({cfg_path})")

    try:
        with open(cfg_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"mode '{name}': cannot parse {cfg_path}: {exc}")

    if not isinstance(data, dict):
        raise ConfigError(f"mode '{name}': expected a JSON object in {cfg_path}")

    description = str(data.get("description", "")).strip()
    docs = str(data.get("docs", "")).strip()

    has_params = "params" in data
    has_generator = "generator" in data
    if has_params and has_generator:
        raise ConfigError(
            f"mode '{name}': specify either 'params' or 'generator', not both")
    if not has_params and not has_generator:
        raise ConfigError(f"mode '{name}': must define 'params' or 'generator'")

    meta = dict(docs=docs, description=description)
    if has_params:
        return _build_declarative(name, data["params"], meta)
    return _build_scripted(name, data, generators_dir, meta)


def _build_declarative(name, params_list, meta=None):
    meta = meta or {}
    specs = _parse_params(name, params_list)
    names = [pname for (pname, _) in specs]
    sizes = [nbytes for (_, nbytes) in specs]

    def generate(rng, index=0):
        return [rng_hex(rng, nbytes) for nbytes in sizes]

    return Mode(name=name, generate=generate, param_names=names, **meta)


def _build_scripted(name, data, generators_dir, meta=None):
    meta = meta or {}
    gen_name = str(data.get("generator", "")).strip()
    if not gen_name:
        raise ConfigError(f"mode '{name}': 'generator' is empty")
    options_raw = data.get("options", {})
    if not isinstance(options_raw, dict):
        raise ConfigError(f"mode '{name}': 'options' must be an object")
    options = {str(k): v for k, v in options_raw.items()}
    gen_func = _load_generator(name, gen_name, generators_dir)

    param_names_raw = data.get("param_names")
    if param_names_raw is not None:
        if not isinstance(param_names_raw, list):
            raise ConfigError(f"mode '{name}': 'param_names' must be an array")
        param_names = [str(n).strip() or None for n in param_names_raw]
    else:
        param_names = None

    def generate(rng, index=0):
        result = gen_func(rng, options, index)
        if not isinstance(result, list) or not all(isinstance(x, str) for x in result):
            raise ConfigError(
                f"mode '{name}': generator '{gen_name}' must return a list of strings")
        return result

    return Mode(name=name, generate=generate, param_names=param_names, **meta)


def _parse_params(name, params_list):
    if not params_list:
        raise ConfigError(f"mode '{name}': 'params' is empty")
    specs = []
    for i, item in enumerate(params_list):
        if not isinstance(item, dict) or "bytes" not in item:
            raise ConfigError(
                f"mode '{name}': params[{i}] must be an object with a 'bytes' key")
        nbytes = item["bytes"]
        if not isinstance(nbytes, int) or nbytes < 1:
            raise ConfigError(
                f"mode '{name}': params[{i}].bytes must be a positive integer")
        pname = str(item["name"]).strip() if "name" in item else None
        specs.append((pname, nbytes))
    return specs


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
