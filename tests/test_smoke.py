"""WP-0 placeholder: the package imports and CI has something to run."""

from __future__ import annotations

import agent


def test_package_imports():
    assert agent.__version__ == "0.1.0"
