"""Run boomerang (round-trip) tests for a single sample.

A boomerang test draws random inputs, runs an ordered pipeline of sample
invocations (forward op then its inverse), and asserts a chosen value round-trips
to a chosen input. Definitions live in boomerang/<category>/<name>.json; the
folder name is the category and each file is one test:

    {
      "id":     "BELT.CTR.4",
      "doc":    "STB 34.101.31-2020",
      "rounds": 1000,
      "inputs": [{"name": "x", "bytes": 2048}, {"name": "key", "bytes": 32}, ...],
      "steps":  [
        {"mode": "belt-ctr", "params": ["x", "key", "s"], "out": "y"},
        {"mode": "belt-ctr", "params": ["y", "key", "s"], "out": "x2"}
      ],
      "assert_equal": ["x2", "x"]
    }

A param/assert token resolves to:
  * "@literal"     — the literal text after "@",
  * "name.head:N"  — `name`'s value minus its last N bytes,
  * "name.tail:N"  — the last N bytes of `name`'s value,
  * "name"         — a random input slot or a prior step's output.
`params` are in the mode's param order, so the sample's alias resolution is
reused via Sample.argv.
"""

import glob
import json
import os
import subprocess
import sys

from src.util import rng_hex


def categories(boomerang_dir):
    if not os.path.isdir(boomerang_dir):
        return []
    return sorted(
        d for d in os.listdir(boomerang_dir)
        if os.path.isdir(os.path.join(boomerang_dir, d))
    )


def _load_files(boomerang_dir, category):
    files = []
    for path in sorted(glob.glob(os.path.join(boomerang_dir, category, "*.json"))):
        with open(path, encoding="utf-8") as f:
            files.append((path, json.load(f)))
    return files


def _run(sample, mode, params):
    proc = subprocess.run(sample.argv(mode, params),
                          stdout=subprocess.PIPE, stderr=None, text=True)
    return proc.stdout.rstrip("\r\n")


def _resolve(token, values):
    if token.startswith("@"):
        return token[1:]
    if "." in token:
        name, spec = token.split(".", 1)
        kind, n = spec.split(":")
        chars = int(n) * 2
        base = values[name]
        if kind == "head":
            return base[:-chars] if chars else base
        if kind == "tail":
            return base[-chars:] if chars else ""
        raise ValueError(f"bad slice spec '{spec}'")
    return values[token]


def _modes_of(test):
    return {step["mode"] for step in test.get("steps", [])}


def list_boomerang(boomerang_dir):
    cats = categories(boomerang_dir)
    if not cats:
        print("No boomerang tests found in boomerang/")
        return 0
    for category in cats:
        print(f"{category}:")
        for _, test in _load_files(boomerang_dir, category):
            modes = ", ".join(sorted(_modes_of(test)))
            print(f"  {test['id']:<18} rounds={test.get('rounds', '?')}  [{modes}]")
    return 0


def run_boomerang(sample, selected, boomerang_dir, rng, rounds_override=None,
                  verbose=False):
    """Run the boomerang tests for `selected` categories against one sample.

    Returns (passed, failed, skipped) counted in tests (not rounds).
    """
    passed = failed = skipped = 0
    stats = {}

    for category in selected:
        cat_dir = os.path.join(boomerang_dir, category)
        if not os.path.isdir(cat_dir):
            print(f"Skipping category '{category}': no such folder "
                  f"({os.path.relpath(cat_dir)})", file=sys.stderr)
            continue

        print(f"=== {category} ===")
        cat_pass = cat_fail = 0

        for _, test in _load_files(boomerang_dir, category):
            tid = test["id"]
            missing = sorted(m for m in _modes_of(test) if m not in sample.modes)
            if missing:
                print(f"  Skipping {tid}: sample '{sample.name}' lacks mode(s): "
                      f"{', '.join(missing)}", file=sys.stderr)
                skipped += 1
                continue

            rounds = rounds_override or test.get("rounds", 1000)
            ok, detail = _run_test(sample, test, rounds, rng)
            if ok:
                cat_pass += 1
                print(f"  [PASS] {tid}  ({rounds} rounds)")
            else:
                cat_fail += 1
                print(f"  [FAIL] {tid}  {detail}")

        stats[category] = (cat_pass, cat_fail)
        passed += cat_pass
        failed += cat_fail
        print(f"  {category}: {cat_pass}/{cat_pass + cat_fail} passed")
        print("")

    _print_summary(stats, skipped)
    return passed, failed, skipped


def _run_test(sample, test, rounds, rng):
    inputs = test["inputs"]
    steps = test["steps"]
    lhs_tok, rhs_tok = test["assert_equal"]

    for r in range(1, rounds + 1):
        values = {}
        for slot in inputs:
            values[slot["name"]] = rng_hex(rng, slot["bytes"])
        for step in steps:
            params = [_resolve(p, values) for p in step["params"]]
            values[step["out"]] = _run(sample, step["mode"], params)
        lhs = _resolve(lhs_tok, values)
        rhs = _resolve(rhs_tok, values)
        if lhs != rhs:
            return False, (f"round {r}/{rounds}: {lhs_tok}={lhs} != {rhs_tok}={rhs}")
    return True, ""


def _print_summary(stats, skipped):
    if not stats:
        return
    print("=== Summary ===")
    w = max(len(c) for c in stats)
    total_pass = total = 0
    for category, (p, f) in stats.items():
        t = p + f
        pct = p / t * 100 if t else 0.0
        note = "" if f == 0 else f"  ({f} failed)"
        print(f"  {category:<{w}}  {p}/{t} passed ({pct:.1f}%){note}")
        total_pass += p
        total += t
    pct = total_pass / total * 100 if total else 0.0
    print(f"  {'─' * (w + 30)}")
    print(f"  {'Overall':<{w}}  {total_pass}/{total} passed ({pct:.1f}%)")
    if skipped:
        print(f"  ({skipped} test(s) skipped: mode unsupported by the sample)")
