# Runtime hook for PyInstaller: patch cryptography and isolate environment
import sys
import os

# Strip host Python environment variables that could leak system packages
if getattr(sys, "frozen", False):
    os.environ.pop("PYTHONPATH", None)
    os.environ.pop("PYTHONHOME", None)

try:
    from cryptography.hazmat.bindings._rust import openssl as rust_openssl
    if hasattr(rust_openssl, "mldsa") and not hasattr(rust_openssl.mldsa, "MLDSAMuHasher"):
        rust_openssl.mldsa.MLDSAMuHasher = type("MLDSAMuHasher", (), {})
except Exception:
    pass
