"""Tenioha: an experimental Japanese particle language."""

from .core import compile_source, execute, run
from .syntax import Diagnostic

__version__ = "0.7.0"
__all__ = ["Diagnostic", "compile_source", "execute", "run"]
