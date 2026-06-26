"""Schwab-style custodian CSV ingest parser."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class CustodianPositionRecord:
    account_id: str
    ticker: str
    quantity: Decimal
    as_of_date: date


REQUIRED_COLUMNS = ("account_id", "ticker", "quantity", "as_of_date")


def parse_custodian_csv(path: Path) -> list[CustodianPositionRecord]:
    if not path.is_file():
        raise FileNotFoundError(f"Custodian file not found: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Empty custodian file: {path}")
        missing = [
            col for col in REQUIRED_COLUMNS if col not in reader.fieldnames
        ]
        if missing:
            raise ValueError(f"Missing columns {missing} in {path.name}")

        records: list[CustodianPositionRecord] = []
        for line_no, row in enumerate(reader, start=2):
            try:
                records.append(
                    CustodianPositionRecord(
                        account_id=row["account_id"].strip(),
                        ticker=row["ticker"].strip().upper(),
                        quantity=Decimal(row["quantity"].strip()),
                        as_of_date=date.fromisoformat(
                            row["as_of_date"].strip()
                        ),
                    )
                )
            except (KeyError, ValueError, ArithmeticError) as err:
                raise ValueError(
                    f"Invalid row {line_no} in {path.name}: {err}"
                ) from err
        if not records:
            raise ValueError(f"No position rows in {path.name}")
        return records
