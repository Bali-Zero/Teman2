"""Mata Garuda — Tools package."""
import os
from mata_garuda.registry import import_all_recursively

_current_dir = os.path.dirname(__file__)
import_all_recursively(_current_dir, "mata_garuda.tools")
