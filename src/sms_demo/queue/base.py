from __future__ import annotations

from abc import ABC, abstractmethod


class ExtractionQueueBackend(ABC):
    """Enqueue SMS extraction work by intake id (payload lives in DB)."""

    @abstractmethod
    def enqueue_extraction(self, intake_id: int) -> None:
        """Schedule LLM extraction + routing for the given intake."""
