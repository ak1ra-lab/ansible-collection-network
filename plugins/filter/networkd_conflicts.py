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
