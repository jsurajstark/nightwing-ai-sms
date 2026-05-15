#!/usr/bin/env python3
"""Truncate demo intakes (cascades to related rows)."""

from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from sms_demo.db import get_engine
from sms_demo.models import Intake


def main() -> None:
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        db.execute(delete(Intake))
        db.commit()
    print("Database reset (intakes cleared).")


if __name__ == "__main__":
    main()
