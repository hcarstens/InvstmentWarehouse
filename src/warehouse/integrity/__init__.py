"""Integrity checks — immutability registry and helpers."""

from warehouse.integrity.frozen_registry import (
    FROZEN_TYPES,
    assert_rejects_mutation,
)

__all__ = ["FROZEN_TYPES", "assert_rejects_mutation"]
