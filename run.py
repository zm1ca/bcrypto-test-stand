#!/usr/bin/env python3
"""
Differential test harness.

Compare the stdout of two or more programs ("samples") on the same randomly
generated inputs. Samples and input recipes ("modes") are each defined by small
INI files under samples/ and modes/. See README.md for details.

Usage:
    python run.py SAMPLE SAMPLE [SAMPLE ...] [--modes M ...] [-n N] [--verbose]
    python run.py list-samples
    python run.py list-modes

Exit codes:
    0  every comparison passed
    1  at least one comparison failed, or a mode errored out
    2  usage / configuration problem (also used by argparse for bad arguments)
"""

import argparse
import datetime
import io
import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import ConfigError, load_sample          # noqa: E402
from src.modes import load_mode, mode_definition_exists  # noqa: E402
from src.runner import run_mode                          # noqa: E402

SAMPLES_DIR    = os.path.join(PROJECT_ROOT, "samples")
MODES_DIR      = os.path.join(PROJECT_ROOT, "modes")
GENERATORS_DIR = os.path.join(PROJECT_ROOT, "generators")
REPORTS_DIR    = os.path.join(PROJECT_ROOT, "reports")


class _Tee:
    """Writes to the real stdout and accumulates a copy in a buffer."""
    def __init__(self, real):
        self._real = real
        self._buf = io.StringIO()

    def write(self, s):
        self._real.write(s)
        self._buf.write(s)

    def flush(self):
        self._real.flush()

    def getvalue(self):
        return self._buf.getvalue()


def _save_report(content, sample_names):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{'_'.join(sample_names)}_{ts}.txt"
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Report saved: {os.path.relpath(path, PROJECT_ROOT)}", file=sys.stderr)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare stdout of 2+ programs on identical random inputs.",
        epilog=(
            "Subcommands:\n"
            "  list-samples    list registered samples and their supported modes\n"
            "  list-modes      list available mode definitions"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "samples", nargs="+",
        help="names of registered samples (samples/<name>.cfg)")
    parser.add_argument(
        "--modes", nargs="+", default=["all"], metavar="MODE",
        help='modes to run, or "all" for the modes supported by every sample '
             "(default: all)")
    parser.add_argument(
        "-n", "--iterations", dest="n", type=int, default=500,
        help="iterations per mode (default: 500)")
    parser.add_argument(
        "--verbose", action="store_true",
        help="print params and outputs for every test, not just failures")
    return parser.parse_args(argv)


def cmd_list_samples():
    entries = sorted(
        f for f in os.listdir(SAMPLES_DIR) if f.endswith(".json")
    )
    if not entries:
        print("No samples found in samples/")
        return 0
    for filename in entries:
        name = filename[:-5]
        cfg_path = os.path.join(SAMPLES_DIR, filename)
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
            mode_names = []
            for entry in data.get("modes", []):
                if isinstance(entry, str):
                    mode_names.append(entry)
                elif isinstance(entry, dict):
                    n = str(entry.get("name", "")).strip()
                    if n:
                        mode_names.append(n)
            modes_str = ", ".join(mode_names) if mode_names else "(no modes listed)"
        except (OSError, json.JSONDecodeError):
            modes_str = "(could not parse config)"
        print(f"  {name:<20} {modes_str}")
    return 0


def _mode_param_names(data):
    if "params" in data:
        return [str(p["name"]).strip() for p in data["params"]
                if "name" in p and str(p.get("name", "")).strip()]
    if "param_names" in data:
        return [str(n).strip() for n in data["param_names"] if str(n).strip()]
    return []


def cmd_list_modes():
    entries = sorted(
        f for f in os.listdir(MODES_DIR) if f.endswith(".json")
    )
    if not entries:
        print("No modes found in modes/")
        return 0

    rows = []
    for filename in entries:
        name = filename[:-5]
        cfg_path = os.path.join(MODES_DIR, filename)
        try:
            with open(cfg_path, encoding="utf-8") as f:
                data = json.load(f)
            docs = str(data.get("docs", "")).strip()
            desc = str(data.get("description", "")).strip()
            params = _mode_param_names(data)
            generator = str(data.get("generator", "")).strip() if not params else ""
        except (OSError, json.JSONDecodeError):
            docs = desc = ""
            params = []
            generator = ""
        rows.append((name, docs, desc, params, generator))

    rows.sort(key=lambda r: (r[1] == "", r[1].lower(), r[0]))
    w_name = max(len(r[0]) for r in rows)

    for name, docs, desc, params, generator in rows:
        parts = [f"  {name:<{w_name}}"]
        label = docs or desc
        if label:
            parts.append(f"  {label}")
        if params:
            parts.append(f"  ({', '.join(params)})")
        elif generator:
            parts.append(f"  [param generator: {generator}.py]")
        print("".join(parts))
    return 0


def select_modes(requested, samples):
    """Return the ordered list of mode names to run, applying the skip rules.

    Warnings (to stderr) are emitted for every skipped mode.
    """
    supported = {s.name: set(s.modes) for s in samples}
    shared = set.intersection(*supported.values())
    asked_all = (len(requested) == 1 and requested[0] == "all")

    if asked_all:
        # Preserve the order in which the first sample declares its modes.
        candidates = [m for m in samples[0].modes if m in shared]
    else:
        candidates = list(dict.fromkeys(requested))  # de-dup, keep order

    selected = []
    for mode in candidates:
        if not asked_all:
            missing = [s.name for s in samples if mode not in supported[s.name]]
            if missing:
                print(f"Skipping mode '{mode}': not supported by samples: "
                      f"{', '.join(missing)}", file=sys.stderr)
                continue
        if not mode_definition_exists(mode, MODES_DIR):
            print(f"Skipping mode '{mode}': no definition found "
                  f"(expected {os.path.join('modes', mode + '.cfg')})",
                  file=sys.stderr)
            continue
        selected.append(mode)
    return selected


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "list-samples":
        return cmd_list_samples()
    if argv and argv[0] == "list-modes":
        return cmd_list_modes()

    args = parse_args(argv)

    names = list(dict.fromkeys(args.samples))
    if len(names) != len(args.samples):
        print("Warning: duplicate sample names ignored.", file=sys.stderr)
    if len(names) < 2:
        print("Error: at least 2 distinct samples are required.", file=sys.stderr)
        return 2

    try:
        samples = [load_sample(name, SAMPLES_DIR, PROJECT_ROOT) for name in names]
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    mode_names = select_modes(args.modes, samples)
    if not mode_names:
        print("Error: no modes to run after applying support/definition checks.",
              file=sys.stderr)
        return 2

    tee = _Tee(sys.stdout)
    sys.stdout = tee

    try:
        rng = random.Random()
        any_failure = False
        mode_stats = {}  # mode_name -> (success, failure, total)

        for name in mode_names:
            try:
                mode = load_mode(name, MODES_DIR, GENERATORS_DIR)
            except ConfigError as exc:
                print(f"Skipping mode '{name}': {exc}", file=sys.stderr)
                any_failure = True
                continue
            success, failures, errored = run_mode(mode, samples, args.n, args.verbose, rng)
            total = success + failures
            mode_stats[name] = (success, failures, total)
            if failures or errored:
                any_failure = True

        _print_summary(mode_stats)
    finally:
        sys.stdout = tee._real
        _save_report(tee.getvalue(), names)

    return 1 if any_failure else 0


def _print_summary(mode_stats):
    if not mode_stats:
        return
    print("=== Summary ===")
    w = max(len(name) for name in mode_stats)
    all_success = 0
    all_total = 0
    for name, (success, failure, total) in mode_stats.items():
        pct = success / total * 100 if total > 0 else 0.0
        status = "" if failure == 0 else f"  ({failure} failed)"
        print(f"  {name:<{w}}  {success}/{total} passed ({pct:.1f}%){status}")
        all_success += success
        all_total += total
    overall_pct = all_success / all_total * 100 if all_total > 0 else 0.0
    print(f"  {'─' * (w + 30)}")
    print(f"  {'Overall':<{w}}  {all_success}/{all_total} passed ({overall_pct:.1f}%)")


if __name__ == "__main__":
    sys.exit(main())
