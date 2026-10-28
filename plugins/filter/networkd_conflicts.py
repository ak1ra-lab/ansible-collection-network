"""Filter plugin: networkd files that actually claim a managed device.

systemd-networkd .network/.netdev files match devices through [Match]
Name= patterns (shell-style globs, with '!' negation).  A device is
configured by a single .network file, so any foreign file whose patterns
overlap with a device this role manages is a conflict; files whose
wildcards cannot match any managed device (e.g. the distro-packaged
80-container-*.network defaults) are not.
"""

from __future__ import annotations

import base64
import fnmatch
import re

DOCUMENTATION = r"""
---
name: networkd_conflicts
short_description: Find systemd-networkd files that claim a managed device
description:
  - Reads C([Match]) C(Name=) patterns (shell-style globs with C(!) negation)
    from candidate systemd-networkd files and reports the paths that can
    match one of the managed devices.
  - Files carrying the caller's marker comment are ignored, so the role never
    reports its own files.
  - The filter is used by the C(systemd_bridge) preflight check.
options:
  pairs:
    description:
      - List of C([path, base64_encoded_content]) pairs, usually the
        C(ansible.builtin.slurp) results zipped with the file list.
    type: list
    elements: list
    required: true
  marker:
    description: Marker comment identifying files owned by the role.
    type: str
    required: true
  devices:
    description: Device names the role manages.
    type: list
    elements: str
    required: true
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Find foreign networkd files that claim a managed interface
  ansible.builtin.set_fact:
    networkd_conflicts_found: >-
      {{ (candidate_paths | ansible.builtin.zip(
            slurp_results | map(attribute='content') | list))
         | map('list') | list
         | ak1ra_lab.network.networkd_conflicts(
             systemd_bridge_file_marker, systemd_bridge_devices) }}
"""

RETURN = r"""
_raw:
  description: Paths of conflicting systemd-networkd files.
  type: list
  elements: str
  returned: always
"""

_NAME_LINE = re.compile(r"^Name=(.+)$", re.MULTILINE)


def _claims_device(text: str, devices: list[str]) -> bool:
    for match in _NAME_LINE.finditer(text):
        for token in match.group(1).split():
            if token.startswith("!"):
                continue
            if any(fnmatch.fnmatchcase(device, token) for device in devices or []):
                return True
    return False


def _decode(content) -> str:
    try:
        return base64.b64decode((content or "").strip(), validate=False).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def networkd_conflicts(pairs: list[list], marker: str, devices: list[str]) -> list[str]:
    """Return the file paths whose Name= patterns match a managed device.

    pairs: [path, base64-encoded content] per candidate file (slurp output
    zipped with the file list).  Files carrying the role's own marker
    comment are this role's and never reported.
    """
    conflicts = []
    for path, content in pairs or []:
        text = _decode(content)
        if marker in text or not _NAME_LINE.search(text):
            continue
        if _claims_device(text, devices):
            conflicts.append(path)
    return conflicts


class FilterModule:
    """networkd_conflicts filter."""

    def filters(self) -> dict:
        return {"networkd_conflicts": networkd_conflicts}
