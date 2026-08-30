from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, ModelVersion, AuditEntry
from app.mlops.rollback import rollback, RollbackError


def _seeded_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_rollback_flips_statuses_correctly():
    db = _seeded_db()
    good = ModelVersion(component="strategist", model_id="v1", status="rolled_back")
    db.add(good); db.commit()

    bad = ModelVersion(component="strategist", model_id="v2", status="live",
                        rollback_target=good.id)
    db.add(bad); db.commit()

    result = rollback(db, "strategist")

    db.refresh(good)
    db.refresh(bad)
    assert bad.status == "rolled_back"
    assert good.status == "live"
    assert result.rolled_back_from == bad.id
    assert result.rolled_back_to == good.id


def test_rollback_writes_an_audit_entry():
    db = _seeded_db()
    good = ModelVersion(component="strategist", model_id="v1", status="rolled_back")
    db.add(good); db.commit()
    bad = ModelVersion(component="strategist", model_id="v2", status="live", rollback_target=good.id)
    db.add(bad); db.commit()

    rollback(db, "strategist")
    entries = db.query(AuditEntry).filter(AuditEntry.event_type == "rollback").all()
    assert len(entries) == 1
    assert entries[0].payload_json["component"] == "strategist"


def test_rollback_raises_when_no_live_version_exists():
    db = _seeded_db()
    try:
        rollback(db, "nonexistent_component")
        assert False, "expected RollbackError"
    except RollbackError as e:
        assert "no live version" in str(e)


def test_rollback_raises_when_live_version_has_no_rollback_target():
    db = _seeded_db()
    live = ModelVersion(component="diagnostician", model_id="v1", status="live", rollback_target=None)
    db.add(live); db.commit()
    try:
        rollback(db, "diagnostician")
        assert False, "expected RollbackError"
    except RollbackError as e:
        assert "no rollback_target" in str(e)


def test_rollback_raises_when_rollback_target_row_does_not_exist():
    db = _seeded_db()
    live = ModelVersion(component="composer", model_id="v1", status="live",
                          rollback_target="nonexistent_id")
    db.add(live); db.commit()
    try:
        rollback(db, "composer")
        assert False, "expected RollbackError"
    except RollbackError as e:
        assert "not found" in str(e)


def test_rollback_only_affects_the_named_component():
    db = _seeded_db()
    good_a = ModelVersion(component="strategist", model_id="v1", status="rolled_back")
    db.add(good_a); db.commit()
    bad_a = ModelVersion(component="strategist", model_id="v2", status="live", rollback_target=good_a.id)
    db.add(bad_a); db.commit()

    other_live = ModelVersion(component="composer", model_id="v1", status="live")
    db.add(other_live); db.commit()

    rollback(db, "strategist")
    db.refresh(other_live)
    assert other_live.status == "live"
