from __future__ import annotations

import logging
import threading

from sms_demo.services.pipeline import complete_intake

logger = logging.getLogger(__name__)


class InlineExtractionQueue:
    """Single-process fallback: daemon thread (no Redis). For tests or quick local runs."""

    def enqueue(self, intake_id: int) -> None:
        logger.info("Inline extraction scheduled intake_id=%s", intake_id)
        threading.Thread(target=complete_intake, args=(intake_id,), daemon=True).start()
