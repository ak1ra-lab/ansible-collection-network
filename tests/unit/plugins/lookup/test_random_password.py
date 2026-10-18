"""Unit tests for plugins/lookup/random_password.py."""

from __future__ import annotations

import pytest
from ansible.errors import AnsibleLookupError
from random_password import DEFAULT_ALPHABET, DEFAULT_LENGTH, LookupModule


def generate(**kwargs: object) -> str:
    return LookupModule().run([], {}, **kwargs)[0]


def test_default_length_and_alphabet() -> None:
    password = generate()
    assert len(password) == DEFAULT_LENGTH
    assert set(password) <= set(DEFAULT_ALPHABET)


def test_length_and_custom_alphabet() -> None:
    password = generate(length=16, alphabet="ab")
    assert len(password) == 16
    assert set(password) <= {"a", "b"}


def test_length_accepts_numeric_strings() -> None:
    assert len(generate(length="8")) == 8


def test_new_password_on_every_evaluation() -> None:
    assert generate(length=16) != generate(length=16)


@pytest.mark.parametrize("length", [0, -1, "nope", None])
def test_invalid_length(length: object) -> None:
    with pytest.raises(AnsibleLookupError):
        generate(length=length)


@pytest.mark.parametrize("alphabet", ["", 3, None])
def test_invalid_alphabet(alphabet: object) -> None:
    with pytest.raises(AnsibleLookupError):
        generate(alphabet=alphabet)


def test_positional_terms_rejected() -> None:
    with pytest.raises(AnsibleLookupError):
        LookupModule().run(["32"], {})
