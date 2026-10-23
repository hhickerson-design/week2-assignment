"""Load books and their authors from books.csv into library.db.

Each book's genre comes from book_genres.csv (books.csv has no genre column),
so only books listed there are loaded. Books keep their books.csv book_id.
Only the first 3 authors listed for a book are kept.

Usage:
    python load_books.py
"""

import csv
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB = HERE / "library.db"
BOOKS_CSV = HERE / "books.csv"
GENRES_CSV = HERE / "book_genres.csv"
MAX_AUTHORS = 3


def split_name(full_name):
    """'J.R.R. Tolkien' -> ('J.R.R.', 'Tolkien'); 'Homer' -> (None, 'Homer')."""
    parts = full_name.strip().rsplit(" ", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else (None, parts[0])


def get_or_create(conn, select_sql, insert_sql, params):
    row = conn.execute(select_sql, params).fetchone()
    return row[0] if row else conn.execute(insert_sql, params).lastrowid


def main():
    if not DB.exists():
        raise SystemExit("library.db not found. Run build_db.py first.")

    with open(GENRES_CSV, encoding="utf-8", newline="") as f:
        genre_for = {int(row["book_id"]): row["genre"] for row in csv.DictReader(f)}

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    loaded = skipped = 0

    with conn, open(BOOKS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            book_id = int(row["book_id"])
            if book_id not in genre_for:
                continue
            if conn.execute("SELECT 1 FROM books WHERE book_id = ?", (book_id,)).fetchone():
                skipped += 1
                continue

            genre_id = get_or_create(
                conn,
                "SELECT genre_id FROM genres WHERE name = ?",
                "INSERT INTO genres (name) VALUES (?)",
                (genre_for[book_id],))

            year = row["original_publication_year"]
            conn.execute(
                "INSERT INTO books (book_id, title, year_published, genre_id) VALUES (?, ?, ?, ?)",
                (book_id, row["title"].strip(), int(float(year)) if year else None, genre_id))

            names = [n.strip() for n in row["authors"].split(",") if n.strip()]
            for order, name in enumerate(names[:MAX_AUTHORS], start=1):
                first, last = split_name(name)
                author_id = get_or_create(
                    conn,
                    "SELECT author_id FROM authors WHERE first_name IS ? AND last_name = ?",
                    "INSERT INTO authors (first_name, last_name) VALUES (?, ?)",
                    (first, last))
                conn.execute(
                    "INSERT INTO book_authors (book_id, author_id, author_order) VALUES (?, ?, ?)",
                    (book_id, author_id, order))
            loaded += 1
    conn.close()

    print(f"Loaded {loaded} books ({skipped} already in the database).")


if __name__ == "__main__":
    main()
