"""
setup.py — legacy compatibility shim.

For modern installation, use pyproject.toml.
Run:  pip install .
      pip install -e .     (editable / development mode)
"""
from setuptools import setup

if __name__ == "__main__":
    setup()
