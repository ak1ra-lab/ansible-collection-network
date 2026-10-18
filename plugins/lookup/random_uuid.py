"""Lookup plugin: generate a random UUID (version 4) on the control node.

Used by ``ak1ra_lab.network.mihomo_server`` for the generated vless/tuic
user identifiers.  ``secrets``-backed ``uuid.uuid4()`` values carry the
RFC 4122 version and variant bits, unlike a reformatted random hex string.
"""

from __future__ import annotations

import uuid
from typing import Any

from ansible.errors import AnsibleLookupError
from ansible.plugins.lookup import LookupBase

DOCUMENTATION = r"""
---
name: random_uuid
short_description: Generate a random UUID (version 4)
description:
  - Returns a random UUID generated with C(uuid.uuid4()) in the canonical
    lowercase hyphenated form (for example
    C(936da01f-9abd-4d9d-80c7-02af85c822a8)).
  - The lookup generates a new UUID on every evaluation; store the result
    (for example with the C(ansible.builtin.set_fact) module) when it must
    stay stable across template re-renders and repeated runs.
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Generate a UUID for a vless user
  ansible.builtin.set_fact:
    vless_uuid: "{{ lookup('ak1ra_lab.network.random_uuid') }}"
"""

RETURN = r"""
_raw:
  description: The generated UUID.
  type: list
  elements: str
"""


class LookupModule(LookupBase):
    """Generate a random UUID; see the module docstring."""

    def run(
        self,
        terms: list[Any],
        variables: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        if terms or kwargs:
            raise AnsibleLookupError("random_uuid takes no arguments")
        return [str(uuid.uuid4())]
