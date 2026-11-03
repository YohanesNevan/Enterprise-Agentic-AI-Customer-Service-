"""Copy rows from the former local SQLite database into configured PostgreSQL.

Existing target primary keys are kept and skipped, so the migration can be rerun.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import Base, DATABASE_URL, engine as target_engine
from app.modules import models as _models  # noqa: F401
from app.modules import models_a as _models_a  # noqa: F401


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="sqlite:///./eaics_b.db")
    args = parser.parse_args()
    if DATABASE_URL.startswith("sqlite"):
        raise SystemExit("Target DATABASE_URL must be PostgreSQL.")

    source_engine = create_engine(args.source)
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)
    Base.metadata.create_all(bind=target_engine)

    copied: dict[str, int] = {}
    with source_engine.connect() as source, target_engine.begin() as target:
        for target_table in Base.metadata.sorted_tables:
            source_table = source_metadata.tables.get(target_table.name)
            if source_table is None or not target_table.primary_key.columns:
                continue
            primary_key = list(target_table.primary_key.columns)
            existing_keys = {
                tuple(row)
                for row in target.execute(select(*primary_key)).all()
            }
            inserted = 0
            for row in source.execute(select(source_table)).mappings():
                values = {key: row[key] for key in target_table.columns.keys() if key in row}
                key = tuple(values.get(column.name) for column in primary_key)
                if key in existing_keys:
                    continue
                target.execute(target_table.insert().values(**values))
                existing_keys.add(key)
                inserted += 1
            if inserted:
                copied[target_table.name] = inserted

    source_engine.dispose()
    for table, count in copied.items():
        print(f"{table}: {count} rows copied")
    print("Migration finished; source SQLite file was left unchanged.")


if __name__ == "__main__":
    main()
