class GFSError(Exception):
    """Base exception for GFS."""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"