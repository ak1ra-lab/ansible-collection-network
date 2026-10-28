"""Ansible filter plugin: render YAML the way the hand-written files look.

``ansible.builtin.to_nice_yaml`` uses the libyaml C emitter when available,
and libyaml's printable-character check only covers the Basic Multilingual
Plane: astral-plane emoji (``🚀 所有节点``, ``🇸🇬 新加坡节点``, ...) are
escaped into ``"\\U0001F680 ..."`` (valid YAML, but unreadable and
diff-noisy against the hand-written files).

``to_pretty_yaml`` dumps with the pure-Python PyYAML emitter instead, which
emits every character literally, indents block sequences under their mapping
key (the yamlfmt/prettier style), preserves mapping order and disables line
wrapping so long scalars stay on one line.
"""

from __future__ import annotations

from typing import Any

import yaml
from yaml.representer import SafeRepresenter

DOCUMENTATION = r"""
---
name: to_pretty_yaml
short_description: Render YAML in the hand-written file style
description:
  - Dumps a YAML-serializable structure with the pure-Python PyYAML emitter.
  - Unlike C(ansible.builtin.to_nice_yaml), astral-plane characters such as
    emoji are emitted literally instead of being escaped.
  - Block sequences are indented under their mapping key, mapping order is
    preserved, and line wrapping is disabled.
options:
  data:
    description: The YAML-serializable structure to render.
    type: raw
    required: true
  indent:
    description: Block indentation width.
    type: int
    default: 2
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Render a provider mapping like the hand-written profile files
  ansible.builtin.set_fact:
    rendered_provider: >-
      {{ provider_mapping | ak1ra_lab.network.to_pretty_yaml }}
"""

RETURN = r"""
_raw:
  description: The rendered YAML document, with a trailing newline.
  type: str
  returned: always
"""


class _IndentedDumper(yaml.SafeDumper):
    """PyYAML dumper that indents block sequences under their mapping key.

    PyYAML's default emitter writes sequences at the same column as the key
    (``key:\\n- item``); the hand-written files (and yamlfmt) use the
    indented form (``key:\\n  - item``).
    """

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


# Ansible's templating hands filters tagged/lazy subclasses of the builtin
# types (e.g. _AnsibleLazyTemplateDict -> _AnsibleTaggedDict -> dict) that
# PyYAML's exact-type representer lookup does not know; register the concrete
# base types as multi-representers so subclasses resolve through their MRO.
for _type, _representer in (
    (dict, SafeRepresenter.represent_dict),
    (list, SafeRepresenter.represent_list),
    (str, SafeRepresenter.represent_str),
    (bool, SafeRepresenter.represent_bool),
    (int, SafeRepresenter.represent_int),
    (float, SafeRepresenter.represent_float),
):
    _IndentedDumper.add_multi_representer(_type, _representer)


def to_pretty_yaml(data: Any, indent: int = 2) -> str:
    """Dump ``data`` as YAML in the hand-written file style.

    Args:
        data: any YAML-serializable structure.
        indent: block indentation width (default 2).

    Returns:
        The YAML document as a string, with a trailing newline.
    """
    return yaml.dump(
        data,
        Dumper=_IndentedDumper,
        allow_unicode=True,
        default_flow_style=False,
        indent=indent,
        sort_keys=False,
        width=10**9,
    )


class FilterModule:
    """Ansible filter plugin registration for the YAML rendering."""

    def filters(self) -> dict[str, Any]:
        return {"to_pretty_yaml": to_pretty_yaml}
