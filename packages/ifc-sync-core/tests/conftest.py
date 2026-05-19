from __future__ import annotations

from typing import Any

import ifcopenshell  # type: ignore[import-untyped]
import pytest


@pytest.fixture
def model() -> Any:
    return ifcopenshell.file(schema="IFC4")
