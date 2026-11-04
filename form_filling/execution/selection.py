from dataclasses import dataclass


@dataclass(frozen=True)
class Selection:
    status: str
    detail: str


def normalized(text: str) -> str:
    return " ".join(text.split()).casefold()
