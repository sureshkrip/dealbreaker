"""Seed the database with default stores."""

from __future__ import annotations

from sqlmodel import Session

from .db import engine, init_db
from .stores import seed_default_stores


def run() -> None:
    init_db()
    with Session(engine) as session:
        created = seed_default_stores(session)
    print(f"Seed complete. Created {created} default store(s).")


if __name__ == "__main__":
    run()
