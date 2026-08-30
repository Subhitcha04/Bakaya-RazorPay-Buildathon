from types import SimpleNamespace

from app.control_plane.gates.rbi import fastag_exemption


def test_flags_fastag_replenishment_as_exempt():
    case = SimpleNamespace(kind="fastag_replenishment")
    result = fastag_exemption.check(db=None, case=case, proposed=None, context={})
    assert result.passed is True
    assert result.evidence["exempt"] is True


def test_flags_ncmc_replenishment_as_exempt():
    case = SimpleNamespace(kind="ncmc_replenishment")
    result = fastag_exemption.check(db=None, case=case, proposed=None, context={})
    assert result.evidence["exempt"] is True


def test_ordinary_mandate_debit_is_not_exempt():
    case = SimpleNamespace(kind="insufficient_funds")
    result = fastag_exemption.check(db=None, case=case, proposed=None, context={})
    assert result.evidence["exempt"] is False
    assert result.evidence["basis"] is None
