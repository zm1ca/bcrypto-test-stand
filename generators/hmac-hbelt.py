from src.util import rng_hex


def generate(rng, options, index=0):
    x_bytes = (index % 32) + 1
    k_bytes = (index % 64) + 1
    return [rng_hex(rng, x_bytes), rng_hex(rng, k_bytes)]
