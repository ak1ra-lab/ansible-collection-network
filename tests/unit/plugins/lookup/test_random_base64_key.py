"""Unit tests for plugins/lookup/random_base64_key.py."""

from __future__ import annotations

import base64

import pytest
from ansible.errors import AnsibleLookupError
from random_base64_key import DEFAULT_BYTES, LookupModule


def generate(**kwargs: object) -> str:
    return LookupModule().run([], {}, **kwargs)[0]


def test_default_bytes() -> None:
    decoded = base64.b64decode(generate(), validate=True)
    assert len(decoded) == DEFAULT_BYTES


def test_custom_bytes() -> None:
    decoded = base64.b64decode(generate(bytes=16), validate=True)
    assert len(decoded) == 16


def test_bytes_accepts_numeric_strings() -> None:
    decoded = base64.b64decode(generate(bytes="8"), validate=True)
    assert len(decoded) == 8


def test_new_key_on_every_evaluation() -> None:
    assert generate(bytes=16) != generate(bytes=16)


@pytest.mark.parametrize("size", [0, -1, "nope", None])
def test_invalid_bytes(size: object) -> None:
    with pytest.raises(AnsibleLookupError):
        generate(bytes=size)


def test_positional_terms_rejected() -> None:
    with pytest.raises(AnsibleLookupError):
        LookupModule().run(["16"], {})
