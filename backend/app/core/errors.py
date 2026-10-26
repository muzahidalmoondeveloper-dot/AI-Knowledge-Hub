class AppError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def not_found() -> AppError:
    return AppError(404, "not_found", "Resource not found")
