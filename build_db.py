"""Create the library database (library.db) from the blueprint in schema.sql.

Usage:
    python build_db.py            # create library.db (refuses if it already exists)
    python build_db.py --rebuild  # delete library.db and start over (erases all data)
"""

import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
SCHEMA = HERE / "schema.sql"
DB = HERE / "library.db"


def main():
    if DB.exists():
        if "--rebuild" not in sys.argv:
            sys.exit(f"{DB.name} already exists. Use --rebuild to erase it and start over.")
        DB.unlink()

    with sqlite3.connect(DB) as conn:
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        views = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name")]
    conn.close()

    print(f"Created {DB.name}")
    print("Tables:", ", ".join(tables))
    print("Views: ", ", ".join(views))


if __name__ == "__main__":
    main()
