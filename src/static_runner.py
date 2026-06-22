"""Run known-answer (static) tests for a single sample.

A static test fixes the inputs and the expected stdout (the canonical answer
from a published methodology) and checks the sample reproduces it. Vectors live
in static/<category>/<mode>.json; the folder name is the category and each file
holds one mode's tests:

    {
      "mode": "belt-ctr",
      "doc":  "met-10131-11-01.pdf",
      "tests": [
        {"id": "BELT.CTR.1", "params": ["<hex>", ...], "output": "<expected stdout>"}
      ]
    }

`params` are in the mode's param order, so the sample's alias resolution is
reused via Sample.argv. `expect` is "equal" (default) or "not_equal".
"""

import glob
import json
import os
import subprocess
import sys


def categories(static_dir):
    if not os.path.isdir(static_dir):
        return []
    return sorted(
        d for d in os.listdir(static_dir)
        if os.path.isdir(os.path.join(static_dir, d))
    )


def _load_files(static_dir, category):
    files = []
    for path in sorted(glob.glob(os.path.join(static_dir, category, "*.json"))):
        with open(path, encoding="utf-8") as f:
            files.append((path, json.load(f)))
    return files


def _run(sample, mode, params):
    proc = subprocess.run(sample.argv(mode, params),
                          stdout=subprocess.PIPE, stderr=None, text=True)
    return proc.stdout.rstrip("\r\n")


def _resolve_params(raw_params, base_dir):
    """Pass-through for string params; a {"file": "<rel-path>"} param becomes an
    absolute path resolved against the test file's directory."""
    resolved = []
    for p in raw_params:
        if isinstance(p, dict) and "file" in p:
            resolved.append(os.path.abspath(os.path.join(base_dir, p["file"])))
        else:
            resolved.append(p)
    return resolved


def list_static(static_dir):
    cats = categories(static_dir)
    if not cats:
        print("No static tests found in static/")
        return 0
    for category in cats:
        print(f"{category}:")
        for _, data in _load_files(static_dir, category):
            ids = ", ".join(t["id"] for t in data.get("tests", []))
            print(f"  {data['mode']:<20} {ids}")
    return 0


def run_static(sample, selected, static_dir, verbose=False):
    """Run the static tests for `selected` categories against one sample.

    Returns (success, failure, skipped).
    """
    success = failure = skipped = 0
    stats = {}

    for category in selected:
        cat_dir = os.path.join(static_dir, category)
        if not os.path.isdir(cat_dir):
            print(f"Skipping category '{category}': no such folder "
                  f"({os.path.relpath(cat_dir)})", file=sys.stderr)
            continue

        print(f"=== {category} ===")
        cat_success = cat_failure = 0

        for json_path, data in _load_files(static_dir, category):
            mode = data["mode"]
            tests = data.get("tests", [])
            if mode not in sample.modes:
                print(f"  Skipping mode '{mode}': not supported by sample "
                      f"'{sample.name}'", file=sys.stderr)
                skipped += len(tests)
                continue

            base_dir = os.path.dirname(json_path)
            for test in tests:
                tid = test["id"]
                expect = test.get("expect", "equal")
                expected = test["output"]
                actual = _run(sample, mode, _resolve_params(test["params"], base_dir))
                ok = (actual == expected) if expect == "equal" else (actual != expected)

                if ok:
                    cat_success += 1
                    if verbose:
                        print(f"  [PASS] {tid}")
                else:
                    cat_failure += 1
                    rel = "==" if expect == "equal" else "!="
                    print(f"  [FAIL] {tid}")
                    print(f"    expected ({rel}) : {expected}")
                    print(f"    actual          : {actual}")

        stats[category] = (cat_success, cat_failure)
        success += cat_success
        failure += cat_failure
        total = cat_success + cat_failure
        print(f"  {category}: {cat_success}/{total} passed")
        print("")

    _print_summary(stats, skipped)
    return success, failure, skipped


def _print_summary(stats, skipped):
    if not stats:
        return
    print("=== Summary ===")
    w = max(len(c) for c in stats)
    total_success = total_total = 0
    for category, (s, f) in stats.items():
        total = s + f
        pct = s / total * 100 if total else 0.0
        note = "" if f == 0 else f"  ({f} failed)"
        print(f"  {category:<{w}}  {s}/{total} passed ({pct:.1f}%){note}")
        total_success += s
        total_total += total
    pct = total_success / total_total * 100 if total_total else 0.0
    print(f"  {'─' * (w + 30)}")
    print(f"  {'Overall':<{w}}  {total_success}/{total_total} passed ({pct:.1f}%)")
    if skipped:
        print(f"  ({skipped} test(s) skipped: mode unsupported by the sample)")
