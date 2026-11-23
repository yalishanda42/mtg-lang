from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    code: str
    message: str
    file: str | None = None
    line: int | None = None
    col: int | None = None

    def __str__(self) -> str:
        loc = ":".join(str(p) for p in (self.file, self.line, self.col) if p is not None)
        head = f"{self.severity} {self.code}: {self.message}"
        return f"{loc}: {head}" if loc else head
