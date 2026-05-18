from __future__ import annotations

from typing import Protocol


class ExtractionQueue(Protocol):
    """Enqueue SMS intake extraction work (MVP: Celery+Redis; prod: SQS)."""

    def enqueue(self, intake_id: int) -> None: ...
