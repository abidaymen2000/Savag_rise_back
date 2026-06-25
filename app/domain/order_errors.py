from fastapi import HTTPException, status


class DomainError(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class InvalidOrderTransitionError(DomainError):
    def __init__(self, detail: str = "Transition de commande invalide"):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class InsufficientStockError(DomainError):
    def __init__(self, detail: str = "Stock insuffisant"):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class OrderAlreadyCancelledError(DomainError):
    def __init__(self, detail: str = "La commande est deja annulee"):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class OrderAlreadyPaidError(DomainError):
    def __init__(self, detail: str = "La commande est deja payee"):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class InvalidIdempotencyKeyReuseError(DomainError):
    def __init__(self, detail: str = "Cette cle d'idempotence est deja utilisee avec une autre requete"):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class ReservationNotFoundError(DomainError):
    def __init__(self, detail: str = "Reservation introuvable"):
        super().__init__(status.HTTP_409_CONFLICT, detail)
