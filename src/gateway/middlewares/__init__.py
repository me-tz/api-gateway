"""Pluggable middleware base and registry.
Auto-import all middleware modules so their register_middleware() calls run.
"""
from __future__ import annotations

import importlib
import pkgutil

for _mod in pkgutil.iter_modules(__path__):
    if _mod.name not in {"base"}:
        importlib.import_module(f"{__name__}.{_mod.name}")
