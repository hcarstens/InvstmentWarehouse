"""Entity graph — Person, Household, Trust, LLC, Account, Custodian relationships.

Graph (v0):
  Person ──owns──> Trust ──holds──> Account ──custodied_at──> Custodian
  Household ──aggregates──> Person, Trust, Account
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    PERSON = "person"
    HOUSEHOLD = "household"
    TRUST = "trust"
    LLC = "llc"
    ACCOUNT = "account"
    CUSTODIAN = "custodian"
    BENEFICIARY = "beneficiary"


class RelationshipType(StrEnum):
    OWNS = "owns"
    HOLDS = "holds"
    CUSTODIED_AT = "custodied_at"
    BENEFICIARY_OF = "beneficiary_of"
    AGGREGATES = "aggregates"


class Entity(BaseModel):
    entity_id: str
    entity_type: EntityType
    name: str
    household_id: str | None = None


class Relationship(BaseModel):
    source_id: str
    target_id: str
    relationship_type: RelationshipType


class EntityGraph(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
