"""
utils/cryptography_compat.py
----------------------------
Runtime compatibility patch for cryptography's post-quantum ML-DSA bindings.

Why this is needed:
  In Python cryptography v50.0.0+, mldsa.py executes:
      MLDSAMuHasher = rust_openssl.mldsa.MLDSAMuHasher
  In certain packaged builds, frozen environments, or machines where system
  PATH/PYTHONPATH or OpenSSL interfaces load an earlier/different rust backend,
  rust_openssl.mldsa exists but does not expose MLDSAMuHasher. This causes an
  AttributeError: module 'mldsa' has no attribute 'MLDSAMuHasher' during top-level
  import of cryptography.x509 / google-auth / requests.

  This patch defines a fallback dummy class on rust_openssl.mldsa before mldsa.py
  is loaded, safely neutralizing the import crash while preserving all standard
  RSA, ECC, and HTTPS functionality.
"""

import sys


def patch_cryptography() -> None:
    """Safely patch rust_openssl.mldsa if MLDSAMuHasher is missing."""
    try:
        from cryptography.hazmat.bindings._rust import openssl as rust_openssl

        if hasattr(rust_openssl, "mldsa"):
            if not hasattr(rust_openssl.mldsa, "MLDSAMuHasher"):
                rust_openssl.mldsa.MLDSAMuHasher = type("MLDSAMuHasher", (), {})
    except Exception:
        # Ignore if cryptography is not installed or backend is different
        pass


def isolate_environment_if_frozen() -> None:
    """
    When running as a packaged PyInstaller executable, prevent external
    system PYTHONPATH / PYTHONHOME from injecting conflicting C-extensions
    or packages from the user's host machine.
    """
    if not getattr(sys, "frozen", False):
        return

    import os

    # Strip dangerous environment variables that leak host packages
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)

    # Sanitize sys.path to only include the app folder and _internal / base_library
    app_dir = os.path.abspath(os.path.dirname(sys.executable))
    internal_dir = getattr(sys, "_MEIPASS", "")

    allowed_prefixes = (
        app_dir.lower(),
        internal_dir.lower() if internal_dir else "",
    )

    clean_path = []
    for p in sys.path:
        p_abs = os.path.abspath(p).lower() if p else ""
        if not p or any(p_abs.startswith(prefix) for prefix in allowed_prefixes if prefix):
            clean_path.append(p)

    sys.path[:] = clean_path
