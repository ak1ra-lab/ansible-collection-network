"""Unit tests for plugins/filter/pretty_yaml.py.

The dumper exists because Ansible's to_nice_yaml (libyaml C emitter) escapes
astral-plane emoji, which the generated profiles are full of.
"""

from __future__ import annotations

from pretty_yaml import FilterModule, to_pretty_yaml


def test_registered_filters() -> None:
    assert set(FilterModule().filters()) == {"to_pretty_yaml"}


def test_astral_emoji_are_emitted_literally() -> None:
    out = to_pretty_yaml([{"name": "🇸🇬 新加坡节点"}, {"name": "🚀 所有节点"}])
    assert "🇸🇬 新加坡节点" in out
    assert "🚀 所有节点" in out
    assert "\\U" not in out
    assert "\\u" not in out


def test_nested_sequences_are_indented() -> None:
    out = to_pretty_yaml({"g": [{"name": "a", "p": ["x", "y"], "flag": True}]})
    assert out == "g:\n  - name: a\n    p:\n      - x\n      - y\n    flag: true\n"


def test_long_scalars_are_not_wrapped() -> None:
    regex = "(?i:" + "|".join(f"keyword-{index}" for index in range(30)) + ")"
    assert to_pretty_yaml({"filter": regex}) == f"filter: {regex}\n"


def test_key_order_is_preserved() -> None:
    out = to_pretty_yaml({"name": "PROXY", "type": "select", "proxies": ["DIRECT"]})
    assert out.splitlines()[0] == "name: PROXY"
    assert out.splitlines()[1] == "type: select"
