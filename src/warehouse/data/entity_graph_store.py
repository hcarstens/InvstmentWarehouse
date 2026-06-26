"""Load entity graph from the database."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from warehouse.infra.db.models import EntityRelationshipRow, EntityRow
from warehouse.models.entities import (
    Entity,
    EntityGraph,
    EntityType,
    Relationship,
    RelationshipType,
)


def load_entity_graph(
    session: Session,
    household_id: str | None = None,
) -> EntityGraph:
    if household_id:
        core_rows = session.scalars(
            select(EntityRow).where(
                or_(
                    EntityRow.household_id == household_id,
                    EntityRow.entity_id == household_id,
                )
            )
        ).all()
        core_ids = {row.entity_id for row in core_rows}
        if not core_ids:
            return EntityGraph()

        rel_rows = session.scalars(
            select(EntityRelationshipRow).where(
                or_(
                    EntityRelationshipRow.source_id.in_(core_ids),
                    EntityRelationshipRow.target_id.in_(core_ids),
                )
            )
        ).all()
        entity_ids = (
            core_ids
            | {r.source_id for r in rel_rows}
            | {r.target_id for r in rel_rows}
        )
        entity_rows = session.scalars(
            select(EntityRow)
            .where(EntityRow.entity_id.in_(entity_ids))
            .order_by(EntityRow.entity_type)
        ).all()
        rel_rows = session.scalars(
            select(EntityRelationshipRow).where(
                EntityRelationshipRow.source_id.in_(entity_ids),
                EntityRelationshipRow.target_id.in_(entity_ids),
            )
        ).all()
    else:
        entity_rows = session.scalars(
            select(EntityRow).order_by(EntityRow.entity_type)
        ).all()
        rel_rows = session.scalars(select(EntityRelationshipRow)).all()

    return EntityGraph(
        entities=[
            Entity(
                entity_id=row.entity_id,
                entity_type=EntityType(row.entity_type),
                name=row.name,
                household_id=row.household_id,
            )
            for row in entity_rows
        ],
        relationships=[
            Relationship(
                source_id=row.source_id,
                target_id=row.target_id,
                relationship_type=RelationshipType(row.relationship_type),
            )
            for row in rel_rows
        ],
    )
