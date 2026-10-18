"""Lookup plugin: generate a random password on the control node.

Used by ``ak1ra_lab.network.mihomo_server`` for the generated listener
credentials.  The characters are drawn from ``alphabet`` with
``secrets.choice``, the operating system's cryptographically secure random
number generator (not the predictable Mersenne-Twister ``random`` module).
"""

from __future__ import annotations

import secrets
import string
from typing import Any

from ansible.errors import AnsibleLookupError
from ansible.plugins.lookup import LookupBase

DEFAULT_LENGTH = 32
DEFAULT_ALPHABET = string.ascii_letters + string.digits

DOCUMENTATION = r"""
---
name: random_password
short_description: Generate a cryptographically random password
description:
  - Returns a password whose characters are drawn uniformly at random from
    O(alphabet) using C(secrets.choice) (the operating system's
    cryptographically secure random number generator).
  - The lookup generates a new value on every evaluation; store the result
    (for example with the C(ansible.builtin.set_fact) module) when it must
    stay stable across template re-renders and repeated runs.
options:
  length:
    description: Number of characters in the password.
    type: int
    default: 32
  alphabet:
    description:
      - Characters the password is drawn from.
      - A character listed multiple times is weighted proportionally higher.
    type: str
    default: ASCII letters and digits (a-z, A-Z, 0-9)
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Generate a 24-character alphanumeric password
  ansible.builtin.set_fact:
    generated_password: "{{ lookup('ak1ra_lab.network.random_password', length=24) }}"

- name: Generate a password from a custom alphabet
  ansible.builtin.debug:
    msg: "{{ lookup('ak1ra_lab.network.random_password', alphabet='0123456789abcdef') }}"
"""

RETURN = r"""
_raw:
  description: The generated password.
  type: list
  elements: str
"""


class LookupModule(LookupBase):
    """Generate a random password; see the module docstring."""

    def run(
        self,
        terms: list[Any],
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        if terms:
            raise AnsibleLookupError(
                "random_password takes no positional terms; pass length and alphabet as keyword arguments"
            )

        length = kwargs.get("length", DEFAULT_LENGTH)
        try:
            length = int(length)
        except (TypeError, ValueError):
            raise AnsibleLookupError(f"length must be an integer, got {length!r}") from None
        if length <= 0:
            raise AnsibleLookupError(f"length must be a positive integer, got {length!r}")

        alphabet = kwargs.get("alphabet", DEFAULT_ALPHABET)
        if not isinstance(alphabet, str) or not alphabet:
            raise AnsibleLookupError(f"alphabet must be a non-empty string, got {alphabet!r}")

        return ["".join(secrets.choice(alphabet) for _ in range(length))]
