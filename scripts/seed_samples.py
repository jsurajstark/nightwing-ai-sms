#!/usr/bin/env python3
"""Load each samples/*.txt through the intake pipeline (requires Ollama if using default provider)."""

from pathlib import Path

from sqlalchemy.orm import sessionmaker

from sms_demo.config import get_settings
from sms_demo.db import get_engine
from sms_demo.services.pipeline import run_intake


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    samples = sorted((root / "samples").glob("*.txt"))
    if not samples:
        print("No files in samples/")
        return

    settings = get_settings()
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        for path in samples:
            text = path.read_text(encoding="utf-8")
            print(f"Seeding: {path.name} …")
            run_intake(db, settings, text, source="console")
        db.commit()
    print("Done.")


if __name__ == "__main__":
    main()
