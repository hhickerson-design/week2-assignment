"""Add made-up sample data to library.db: shelf copies, members and loans.

All people, phone numbers and emails here are fictional (555 numbers,
example.com addresses). Run after build_db.py and load_books.py.

Usage:
    python seed_sample_data.py
"""

import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "library.db"

ACQUIRED = "2026-06-01"
EXTRA_COPIES = [1, 2]  # book_ids that get a second copy (popular titles)

# (first, last, phone, email, birth_date)
MEMBERS = [
    ("Maria", "Lopez", "615-555-0101", "maria.lopez@example.com", "1985-03-14"),
    ("James", "Carter", "615-555-0102", None, "1978-11-02"),
    ("Emma", "Carter", "615-555-0102", None, "2015-07-21"),  # James's daughter
    ("Devon", "Brooks", None, "devon.brooks@example.com", "2009-01-30"),
    ("Priya", "Shah", "615-555-0105", "priya.shah@example.com", "1992-09-09"),
    ("Tom", "Nguyen", None, "tom.nguyen@example.com", "1960-05-05"),  # never borrows
    ("Linda", "Park", "615-555-0107", None, "1955-12-12"),  # membership expires later
]

# (member, copy_id, checkout, condition_out, extension_date, returned, condition_in, notes)
# copy_id 1-25 = first copy of book 1-25; 26 = 2nd Hunger Games; 27 = 2nd Sorcerer's Stone
LOANS = [
    ("Maria Lopez", 10, "2026-07-01", "New", None, "2026-07-20", "Good", None),
    ("James Carter", 4, "2026-07-05", "New", None, "2026-08-14", "Fair", None),  # 10 days late
    ("Emma Carter", 2, "2026-07-10", "New", "2026-08-01", "2026-09-05", "Good", None),  # extended
    ("Devon Brooks", 1, "2026-07-15", "New", None, "2026-08-10", "Good", None),
    ("Linda Park", 5, "2026-07-20", "New", None, "2026-08-25", "Good", None),  # 6 days late
    ("Devon Brooks", 17, "2026-08-12", "New", None, "2026-09-02", "Good", None),
    ("Priya Shah", 7, "2026-08-20", "New", None, "2026-09-10", "Poor", "Water damage on back cover"),
    ("Emma Carter", 23, "2026-09-06", "New", None, "2026-10-01", "Good", None),
    ("James Carter", 16, "2026-09-01", "New", None, None, None, None),  # still out, OVERDUE
    ("Maria Lopez", 11, "2026-09-15", "New", "2026-10-05", None, None, None),  # out, extended
    ("Priya Shah", 26, "2026-10-01", "New", None, None, None, None),  # still out
    ("Emma Carter", 18, "2026-10-02", "New", None, None, None, None),  # still out
    ("Devon Brooks", 20, "2026-10-10", "New", None, None, None, None),  # still out
]

EXPIRE_AFTER_LOANS = ["Linda Park"]


def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    if conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]:
        raise SystemExit("library.db already has members. Rebuild it to reseed.")

    with conn:
        book_ids = [r[0] for r in conn.execute("SELECT book_id FROM books ORDER BY book_id")]
        for book_id in book_ids + EXTRA_COPIES:
            conn.execute("INSERT INTO copies (book_id, acquired_date) VALUES (?, ?)",
                         (book_id, ACQUIRED))

        member_id = {}
        for first, last, phone, email, born in MEMBERS:
            member_id[f"{first} {last}"] = conn.execute(
                "INSERT INTO members (first_name, last_name, phone, email, birth_date, joined_date)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (first, last, phone, email, born, ACQUIRED)).lastrowid

        for member, copy_id, out, cond_out, ext, back, cond_in, notes in LOANS:
            loan_id = conn.execute(
                "INSERT INTO loans (copy_id, member_id, checkout_date, condition_out, extension_date)"
                " VALUES (?, ?, ?, ?, ?)",
                (copy_id, member_id[member], out, cond_out, ext)).lastrowid
            if back:  # recorded as a separate step so the copy's condition updates
                conn.execute(
                    "UPDATE loans SET returned_date = ?, condition_in = ?, condition_notes = ?"
                    " WHERE loan_id = ?", (back, cond_in, notes, loan_id))

        for member in EXPIRE_AFTER_LOANS:
            conn.execute("UPDATE members SET status = 'Expired' WHERE member_id = ?",
                         (member_id[member],))
    conn.close()

    print(f"Added {len(book_ids) + len(EXTRA_COPIES)} copies, {len(MEMBERS)} members, "
          f"{len(LOANS)} loans.")


if __name__ == "__main__":
    main()
