from datetime import date


class PricingService:
    def __init__(self, nightly_rate: float):
        self._rate = nightly_rate

    def calculate(self, checkin: str, checkout: str, guests: int) -> float:
        start = date.fromisoformat(checkin)
        end = date.fromisoformat(checkout)
        nights = (end - start).days
        if nights <= 0:
            raise ValueError(f"checkout must be after checkin: {checkin} -> {checkout}")
        return float(self._rate * nights)
