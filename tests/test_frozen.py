"""Frozen registry — ensure immutable types reject mutation (no silent failures)."""

import pytest

from warehouse.integrity.frozen_registry import (
    FROZEN_TYPES,
    assert_rejects_mutation,
    frozen_type_samples,
    is_registered_frozen_type,
)


@pytest.mark.parametrize("cls", FROZEN_TYPES)
def test_frozen_registry_types_are_marked_frozen(cls: type) -> None:
    assert is_registered_frozen_type(cls), (
        f"{cls.__name__} is in FROZEN_TYPES but missing frozen=True configuration"
    )


@pytest.mark.parametrize("cls,instance", frozen_type_samples())
def test_frozen_registry_rejects_mutation(cls: type, instance: object) -> None:
    assert_rejects_mutation(instance)
