"""Ticket references.

`SUP-XXXXXX`, random rather than sequential: a sequential reference tells anyone
who opens two tickets how many the platform receives, and lets them guess other
people's.

The alphabet excludes 0/O/1/I/L because references are read aloud to agents over
the phone by people who are already annoyed.
"""

from __future__ import annotations

import secrets
from typing import Final

_ALPHABET: Final = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def new_reference() -> str:
    return "SUP-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
