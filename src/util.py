"""Low-level helpers with no project dependencies.

Kept dependency-free so that generator scripts can import `rng_hex` without
pulling in the rest of the project.
"""


def rng_hex(rng, n_bytes):
    """Return `n_bytes` random bytes as an uppercase hex string, drawn from `rng`.

    `rng` is a `random.Random`. All randomness in the project flows through a
    single such instance so behaviour is consistent (and could be seeded later).
    """
    if n_bytes <= 0:
        return ""
    try:
        raw = rng.randbytes(n_bytes)              # Python 3.9+
    except AttributeError:                        # older interpreters
        raw = rng.getrandbits(n_bytes * 8).to_bytes(n_bytes, "big")
    return raw.hex().upper()
