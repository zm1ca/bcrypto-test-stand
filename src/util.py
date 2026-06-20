"""Low-level helpers with no project dependencies.

Kept dependency-free so that generator scripts can import `rng_hex` without
pulling in the rest of the project.
"""

import configparser


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


def new_ini_parser():
    """An INI parser that treats `;` and `#` as inline comment markers."""
    return configparser.ConfigParser(inline_comment_prefixes=(";", "#"))


def split_csv(raw):
    """Split a comma-separated string into a list of trimmed, non-empty items."""
    return [item.strip() for item in raw.split(",") if item.strip()]
