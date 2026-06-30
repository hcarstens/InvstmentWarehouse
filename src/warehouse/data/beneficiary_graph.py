"""Beneficiary designation edges on the entity graph (qa8).

``beneficiary_of`` links a ``beneficiary`` entity to an account or trust
they are designated on. Helpers expose graph queries for tests and panels.
"""

from __future__ import annotations

from warehouse.models.entities import (
    Entity,
    EntityGraph,
    EntityType,
    RelationshipType,
)


class BeneficiaryGraphError(ValueError):
    """Raised when beneficiary edges fail structural validation."""


def beneficiary_of_map(graph: EntityGraph) -> dict[str, str]:
    """Map beneficiary entity id → designated account/trust id."""
    return {
        rel.source_id: rel.target_id
        for rel in graph.relationships
        if rel.relationship_type == RelationshipType.BENEFICIARY_OF
    }


def beneficiaries_of(graph: EntityGraph, target_id: str) -> list[str]:
    """Beneficiary entity ids designated on ``target_id``."""
    return [
        rel.source_id
        for rel in graph.relationships
        if rel.relationship_type == RelationshipType.BENEFICIARY_OF
        and rel.target_id == target_id
    ]


def beneficiary_entities(graph: EntityGraph) -> list[Entity]:
    """All beneficiary-typed entities in the graph."""
    return [
        entity
        for entity in graph.entities
        if entity.entity_type == EntityType.BENEFICIARY
    ]


def assert_beneficiary_edges_resolve(graph: EntityGraph) -> None:
    """Validate beneficiary_of endpoints and beneficiary source types."""
    entity_by_id = {entity.entity_id: entity for entity in graph.entities}
    for rel in graph.relationships:
        if rel.relationship_type != RelationshipType.BENEFICIARY_OF:
            continue
        source = entity_by_id.get(rel.source_id)
        if source is None:
            raise BeneficiaryGraphError(
                f"beneficiary_of source {rel.source_id!r} missing from graph"
            )
        if source.entity_type != EntityType.BENEFICIARY:
            raise BeneficiaryGraphError(
                f"{rel.source_id!r} is {source.entity_type.value}, "
                "expected beneficiary"
            )
        if rel.target_id not in entity_by_id:
            raise BeneficiaryGraphError(
                f"beneficiary_of target {rel.target_id!r} missing from graph"
            )
