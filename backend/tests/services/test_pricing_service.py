import pytest
from app.services.pricing_service import PricingService


def test_two_nights_returns_correct_total():
    svc = PricingService(nightly_rate=800.0)
    price = svc.calculate(checkin="2026-04-10", checkout="2026-04-12", guests=4)
    assert price == 1600.0


def test_one_night():
    svc = PricingService(nightly_rate=800.0)
    price = svc.calculate(checkin="2026-04-10", checkout="2026-04-11", guests=2)
    assert price == 800.0


def test_invalid_dates_raises():
    svc = PricingService(nightly_rate=800.0)
    with pytest.raises(ValueError):
        svc.calculate(checkin="2026-04-12", checkout="2026-04-10", guests=2)
