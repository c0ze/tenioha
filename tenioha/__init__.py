"""Tenioha: an experimental Japanese particle language."""

from .core import compile_source, execute, run
from .syntax import Diagnostic

__version__ = "0.5.0"
__all__ = ["Diagnostic", "compile_source", "execute", "run"]
