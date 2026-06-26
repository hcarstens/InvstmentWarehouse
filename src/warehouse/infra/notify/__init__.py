"""Outbound notifications (email, messaging webhooks)."""

from warehouse.infra.notify.dispatch import dispatch_risk_alert

__all__ = ["dispatch_risk_alert"]
