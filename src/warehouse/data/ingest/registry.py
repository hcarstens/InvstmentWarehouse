"""Custodian parser registry — dispatch ingest by custodian_id."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from warehouse.data.ingest.fidelity_csv import parse_fidelity_csv
from warehouse.data.ingest.schwab_csv import (
    CustodianPositionRecord,
    parse_custodian_csv,
)

ParserFn = Callable[[Path], list[CustodianPositionRecord]]

PARSER_REGISTRY: dict[str, ParserFn] = {
    "custodian_schwab": parse_custodian_csv,
    "custodian_fidelity": parse_fidelity_csv,
}


def get_parser(custodian_id: str) -> ParserFn:
    parser = PARSER_REGISTRY.get(custodian_id)
    if parser is None:
        known = ", ".join(sorted(PARSER_REGISTRY))
        raise ValueError(
            f"Unknown custodian {custodian_id!r} — known: {known}")
    return parser


def list_custodians() -> list[str]:
    return sorted(PARSER_REGISTRY)
