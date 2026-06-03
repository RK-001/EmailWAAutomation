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

import ssl
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


def create_ssl_context() -> ssl.SSLContext:
    """
    Create an SSL context that prefers the merged Windows/certifi CA bundle.

    Falls back to Python's default trust configuration when the merge helper is
    unavailable. This keeps HTTPS calls working in normal and corporate-proxy
    Windows environments without disabling certificate verification.
    """
    ca_bundle = get_merged_ca_bundle_path()
    if ca_bundle:
        return ssl.create_default_context(cafile=ca_bundle)
    return ssl.create_default_context()
