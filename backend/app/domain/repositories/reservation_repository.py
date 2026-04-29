from app.domain.models.reservation import Reservation


class ReservationRepository:
    def save(self, reservation: Reservation) -> None:
        raise NotImplementedError

    def get(self, reservation_id: str) -> Reservation | None:
        raise NotImplementedError

    def list_all(self) -> list[Reservation]:
        raise NotImplementedError
