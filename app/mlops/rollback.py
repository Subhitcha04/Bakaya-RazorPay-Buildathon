"""
Rollback: reverts a component to its designated rollback_target model
version, in one call. Demoable: deploy a deliberately bad version,
watch a golden-set eval gate catch it, roll back immediately -- exactly
how changes to money-touching logic should be reversible.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import ModelVersion
from app.audit import ledger as audit


class RollbackError(Exception):
    pass


@dataclass(frozen=True)
class RollbackResult:
    component: str
    rolled_back_from: str
    rolled_back_to: str


def rollback(db: Session, component: str) -> RollbackResult:
    current_live = (
        db.query(ModelVersion)
        .filter(ModelVersion.component == component, ModelVersion.status == "live")
        .first()
    )
    if current_live is None:
        raise RollbackError(f"no live version found for component {component!r}")
    if not current_live.rollback_target:
        raise RollbackError(
            f"live version {current_live.id!r} for {component!r} has no rollback_target set -- "
            "cannot roll back to nothing"
        )

    target = db.get(ModelVersion, current_live.rollback_target)
    if target is None:
        raise RollbackError(f"rollback_target {current_live.rollback_target!r} not found")

    from_id, to_id = current_live.id, target.id
    current_live.status = "rolled_back"
    target.status = "live"
    db.commit()

    audit.append(db, event_type="rollback", payload={
        "component": component,
        "rolled_back_from": from_id,
        "rolled_back_to": to_id,
    })

    return RollbackResult(component=component, rolled_back_from=from_id, rolled_back_to=to_id)
