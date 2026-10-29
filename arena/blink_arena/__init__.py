"""PiccoloArena: portable games, model adapters and evaluation records."""
from pathlib import Path
import sys

# Preserved production engines use their original module names. This directory
# is part of this distribution; it never points at a training workspace.
_engines = str(Path(__file__).resolve().parent / 'engines')
if _engines not in sys.path:
    sys.path.insert(0, _engines)
__version__ = '1.0.0'
