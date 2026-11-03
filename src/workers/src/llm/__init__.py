"""LLM worker module.

Public surface: ``run()``. ``src/main.py`` owns the thread and targets this
function; nothing else in the module is part of the public contract.
"""

from .worker import run

__all__ = ["run"]
