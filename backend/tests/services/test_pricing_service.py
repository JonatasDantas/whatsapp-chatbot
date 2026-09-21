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


def test_same_day_checkout_raises():
    """checkout == checkin means 0 nights — should raise."""
    svc = PricingService(nightly_rate=800.0)
    with pytest.raises(ValueError):
        svc.calculate(checkin="2026-04-10", checkout="2026-04-10", guests=2)


def test_large_group_same_rate():
    """Price is not affected by guest count — only by nightly rate × nights."""
    svc = PricingService(nightly_rate=1000.0)
    assert svc.calculate(checkin="2026-04-10", checkout="2026-04-13", guests=20) == 3000.0
