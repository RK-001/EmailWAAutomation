"""Collect only the lxml modules needed by this Windows desktop build."""

from PyInstaller.utils.hooks import collect_submodules

_EXCLUDED_PREFIXES = (
    "lxml.html",
    "lxml.isoschematron",
    "lxml.objectify",
    "lxml.sax",
)


def _include_module(module_name):
    return not module_name.startswith(_EXCLUDED_PREFIXES)


hiddenimports = collect_submodules("lxml", filter=_include_module)
