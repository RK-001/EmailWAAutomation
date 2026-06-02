"""
utils/ssl_compat.py
-------------------
Helpers for HTTPS certificate compatibility on Windows.

Some environments use local/corporate root certificates that browsers trust
via the Windows certificate store, but Python libraries such as httplib2 only
trust the bundled certifi CA file by default. This module builds a merged CA
bundle using `python-certifi-win32` when available and returns its path.
"""

from __future__ import annotations

from typing import Optional


def get_merged_ca_bundle_path() -> Optional[str]:
    """
    Return a CA bundle path that includes Windows root certificates when possible.

    Returns:
        Absolute path to a PEM file, or None if no special handling is available.
    """
    try:
        from certifi_win32 import wincerts

        wincerts.generate_pem()
        return wincerts.where()
    except Exception:
        return None
