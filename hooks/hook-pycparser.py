"""PyInstaller hook for pycparser across old and new releases.

Older pycparser releases shipped generated lextab/yacctab modules; newer
releases can build the parser without them. Only include the tables when the
installed package actually provides them, which avoids false build warnings.
"""

import importlib.util

_TABLE_MODULES = ("pycparser.lextab", "pycparser.yacctab")

hiddenimports = [
    module_name
    for module_name in _TABLE_MODULES
    if importlib.util.find_spec(module_name) is not None
]
