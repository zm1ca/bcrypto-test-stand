"""Run selected modes across selected samples and report comparisons.

Pass rule (per project decision): a test passes when every sample produced
non-empty stdout and all outputs are identical. On any other result the test
fails and all outputs are printed for manual comparison.
"""

import subprocess
import sys
import time


def _run_sample(sample, mode_name, params):
    """Invoke one sample and return its stdout with the trailing newline stripped.

    stderr passes through to the console; exit codes are ignored (only stdout
    is compared), matching the original harness.
    """
    proc = subprocess.run(sample.argv(mode_name, params),
                          stdout=subprocess.PIPE, stderr=None, text=True)
    return proc.stdout.rstrip("\r\n")


def _all_equal_nonempty(outputs):
    if any(out == "" for out in outputs):
        return False
    first = outputs[0]
    return all(out == first for out in outputs)


def run_mode(mode, samples, n, verbose, rng):
    """Run one mode for `n` iterations.

    Returns (failure_count, errored) where `errored` is True if generation or
    invocation raised, in which case the mode was stopped early.
    """
    desc = f" — {mode.description}" if mode.description else ""
    print(f"=== {mode.name}{desc} ===")

    success_count = 0
    failure_count = 0
    total_start = time.perf_counter()
    batch_start = time.perf_counter()

    tag_width = max((len(s.tag) for s in samples), default=0)

    for index in range(1, n + 1):
        try:
            params = mode.generate(rng)
            outputs = [_run_sample(s, mode.name, params) for s in samples]
        except Exception as exc:  # noqa: BLE001 - stop this mode, continue the run
            print(f"Error in mode '{mode.name}' at test #{index}: {exc}",
                  file=sys.stderr)
            print(f"Stopping mode '{mode.name}'; moving on to the next mode.",
                  file=sys.stderr)
            return failure_count, True

        passed = _all_equal_nonempty(outputs)
        if passed:
            success_count += 1
        else:
            print(f"Comparison failed for Test #{index}")
            failure_count += 1

        if verbose or not passed:
            label_width = max((len(mode.label_for(i)) for i in range(len(params))),
                              default=0)
            for i, value in enumerate(params):
                print(f"{mode.label_for(i).ljust(label_width)} : {value}")
            for sample, out in zip(samples, outputs):
                print(f"{sample.tag.ljust(tag_width)} : {out}")

        if not verbose and index % 1000 == 0:
            batch_seconds = time.perf_counter() - batch_start
            print(f"After {index} tests: Success={success_count}, "
                  f"Failure={failure_count}, Batch time={batch_seconds} s")
            batch_start = time.perf_counter()

    total_seconds = time.perf_counter() - total_start
    print(f"Mode {mode.name} finished: Total tests={n}, "
          f"Success={success_count}, Failure={failure_count}, "
          f"Total time={total_seconds} s")
    print("")
    return failure_count, False
