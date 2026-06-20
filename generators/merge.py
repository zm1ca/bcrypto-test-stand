"""Built-in generator for the irregular `merge` mode.

Produces a fixed number of argument slots, of which a random subset are filled
with random hex and the rest are left as empty-string arguments. Reproduces the
behaviour of the original harness with its default options.

Generator contract:
    generate(rng, options) -> list[str]
where `rng` is a random.Random and `options` is a dict of strings (the extra
keys from the mode's [mode] section). Generators convert option types as needed.
"""

from src.util import rng_hex


def generate(rng, options):
    size = int(options.get("size", 32))
    slots = int(options.get("slots", 5))
    fill_min = int(options.get("fill_min", 2))
    fill_max = int(options.get("fill_max", 5))

    params = [""] * slots
    count = rng.randint(fill_min, fill_max)
    for idx in rng.sample(range(slots), count):
        params[idx] = rng_hex(rng, size)
    return params
