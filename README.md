# bcrypto-test-stand

A differential test harness. Feeds the same random inputs to two or more programs and checks that all outputs match. Useful for validating one implementation against a reference or cross-checking several builds at once.

## Layout

```
run.py          entry point
samples/        one INI file per sample
modes/          one INI file per mode
generators/     Python generators for irregular modes
src/            implementation
bin/            binaries (bin/default/ ships the two bee2 executables)
```

## Default samples

Two bee2 reference executables are shipped in `bin/default/`. They cover different modes and cannot be compared against each other — register your own sample and compare it against whichever one covers the modes you need.

| Sample | Modes |
|--------|-------|
| `bee2a` | sign, split, merge, kwp, dwp, keywrap |
| `bee2b` | cfb, ctr, hsh, mac, brng |

## Usage

```
python run.py <sample> <sample> [<sample> ...] [--modes <mode> ...] [-n <n>] [--verbose]
```

Pick two or more samples that share at least one mode:

```
python run.py bee2b mysample
python run.py bee2b mysample --modes cfb ctr
python run.py bee2b mysample --modes all -n 1000 --verbose
```

- `--modes` — which modes to run. Defaults to `all`, meaning every mode both samples support.
- `-n` — iterations per mode (default 500).
- `--verbose` — print inputs and outputs for every test, not just failures.

A test passes when every sample produces non-empty stdout and all outputs are identical. On failure all outputs are printed for comparison.

## Adding a sample

Drop an INI file in `samples/`. The filename without `.cfg` is the name you pass on the command line.

```ini
[sample]
path          = path/to/binary  ; relative to project root, or absolute (required)
modes         = cfb, ctr, mac   ; comma-separated list of supported modes (required)
cmd           = wine            ; interpreter/wrapper, all platforms (optional)
cmd_win       = ...             ; Windows — overrides cmd (optional)
cmd_linux     = ...             ; Linux x86-64 — overrides cmd (optional)
cmd_linux_arm = ...             ; Linux ARM64 — overrides cmd (optional)
cmd_mac       = ...             ; macOS Intel — overrides cmd (optional)
cmd_mac_arm   = ...             ; macOS Apple Silicon — overrides cmd (optional)
tag           = My label        ; log label; defaults to the filename (optional)
```

Each sample is invoked as `[cmd] <path> <mode> <param1> <param2> ...`. The most specific platform key wins; `cmd` is the fallback for any platform not listed.

## Adding a mode

Drop an INI file in `modes/`. The filename without `.cfg` is the mode token passed as the first argument to every sample.

**Declarative** — fixed-size random hex parameters:

```ini
[mode]
params = x:2048, key:32, s:16
```

Each entry is `name:bytes`; the name is used only in log output.

**Scripted** — for irregular generation:

```ini
[mode]
generator = merge
size      = 32
slots     = 5
fill_min  = 2
fill_max  = 5
```

Points to `generators/merge.py`. Any extra keys are passed to the generator as options.

## Writing a generator

```python
from src.util import rng_hex

def generate(rng, options):
    # rng     : random.Random instance
    # options : dict of extra [mode] keys as strings
    return ["AB12...", "CD34..."]  # ordered list of argument strings
```
