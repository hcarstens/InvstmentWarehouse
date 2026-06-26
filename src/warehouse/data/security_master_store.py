"""Security master persistence and queries."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from warehouse.data.security_master import AssetClass, Security, TaxCharacter
from warehouse.infra.db.models import SecurityRow


def row_to_security(row: SecurityRow) -> Security:
    return Security(
        security_id=row.security_id,
        cusip=row.cusip,
        isin=row.isin,
        ticker=row.ticker,
        name=row.name,
        asset_class=AssetClass(row.asset_class),
        tax_character=TaxCharacter(row.tax_character),
        liquidity_tier=row.liquidity_tier,
        wash_sale_substitute_group=row.wash_sale_substitute_group,
    )


def list_securities(
    session: Session, query: str | None = None
) -> list[Security]:
    stmt = select(SecurityRow).order_by(SecurityRow.ticker)
    if query:
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                SecurityRow.ticker.ilike(pattern),
                SecurityRow.name.ilike(pattern),
                SecurityRow.cusip.ilike(pattern),
                SecurityRow.isin.ilike(pattern),
            )
        )
    rows = session.scalars(stmt).all()
    return [row_to_security(row) for row in rows]
