-- Library database blueprint (SQLite)
--
-- Dates are stored as text in YYYY-MM-DD form, e.g. '2026-10-23'.
-- Money is stored in whole cents (25 = $0.25) to avoid rounding errors.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------
-- Genres: one row per category, so each genre is spelled one way.
-- ---------------------------------------------------------------
CREATE TABLE genres (
    genre_id INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE COLLATE NOCASE
);

-- ---------------------------------------------------------------
-- Authors: one row per person who writes books.
-- ---------------------------------------------------------------
CREATE TABLE authors (
    author_id  INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name  TEXT NOT NULL
);

-- ---------------------------------------------------------------
-- Books: one row per title (not per physical copy).
-- ---------------------------------------------------------------
CREATE TABLE books (
    book_id        INTEGER PRIMARY KEY,
    title          TEXT NOT NULL,
    year_published INTEGER CHECK (year_published BETWEEN -3000 AND 2100),  -- negative = BC
    genre_id       INTEGER NOT NULL REFERENCES genres (genre_id)
);

-- ---------------------------------------------------------------
-- Book authors: links books to authors. author_order can only be
-- 1, 2 or 3, and each slot is used once per book, so a book can
-- never have more than 3 authors.
-- ---------------------------------------------------------------
CREATE TABLE book_authors (
    book_id      INTEGER NOT NULL REFERENCES books (book_id) ON DELETE CASCADE,
    author_id    INTEGER NOT NULL REFERENCES authors (author_id),
    author_order INTEGER NOT NULL CHECK (author_order BETWEEN 1 AND 3),
    PRIMARY KEY (book_id, author_order),
    UNIQUE (book_id, author_id)
);

-- ---------------------------------------------------------------
-- Copies: one row per physical book on the shelf.
-- ---------------------------------------------------------------
CREATE TABLE copies (
    copy_id           INTEGER PRIMARY KEY,
    book_id           INTEGER NOT NULL REFERENCES books (book_id),
    acquired_date     TEXT CHECK (acquired_date IS date(acquired_date)),
    current_condition TEXT NOT NULL DEFAULT 'New'
        CHECK (current_condition IN ('New', 'Good', 'Fair', 'Poor', 'Damaged'))
);

-- ---------------------------------------------------------------
-- Members: one row per cardholder. Age is calculated from
-- birth_date (see the member_ages view) so it never goes stale.
-- Only 'Active' members may borrow.
-- ---------------------------------------------------------------
CREATE TABLE members (
    member_id   INTEGER PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    phone       TEXT,
    email       TEXT,
    birth_date  TEXT NOT NULL CHECK (birth_date IS date(birth_date)),
    status      TEXT NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Suspended', 'Expired')),
    joined_date TEXT NOT NULL DEFAULT (date('now'))
        CHECK (joined_date IS date(joined_date)),
    CHECK (phone IS NOT NULL OR email IS NOT NULL)
);

-- ---------------------------------------------------------------
-- Loans: one row per checkout of one copy (the "hand receipt").
--
-- Rules built into this table:
--   * due_date is calculated: 30 days after checkout, or 60 days
--     if an extension was requested.
--   * One extension per loan (there is only one extension_date),
--     and it must be requested on or before the original due date
--     and before the book is returned.
--   * Condition is recorded at checkout; at return it is required.
--   * late_fee_cents is calculated at return: 25 cents per day
--     past the due date.
-- ---------------------------------------------------------------
CREATE TABLE loans (
    loan_id        INTEGER PRIMARY KEY,
    copy_id        INTEGER NOT NULL REFERENCES copies (copy_id),
    member_id      INTEGER NOT NULL REFERENCES members (member_id),
    checkout_date  TEXT NOT NULL DEFAULT (date('now'))
        CHECK (checkout_date IS date(checkout_date)),
    condition_out  TEXT NOT NULL
        CHECK (condition_out IN ('New', 'Good', 'Fair', 'Poor', 'Damaged')),
    extension_date TEXT
        CHECK (extension_date IS date(extension_date)),
    returned_date  TEXT
        CHECK (returned_date IS date(returned_date)),
    condition_in   TEXT
        CHECK (condition_in IN ('New', 'Good', 'Fair', 'Poor', 'Damaged')),
    condition_notes TEXT,

    due_date TEXT GENERATED ALWAYS AS (
        date(checkout_date,
             CASE WHEN extension_date IS NULL THEN '+30 days' ELSE '+60 days' END)
    ) STORED,

    late_fee_cents INTEGER GENERATED ALWAYS AS (
        CASE WHEN returned_date > due_date
             THEN 25 * CAST(julianday(returned_date) - julianday(due_date) AS INTEGER)
             ELSE 0 END
    ) STORED,

    CHECK (returned_date IS NULL OR returned_date >= checkout_date),
    CHECK ((returned_date IS NULL) = (condition_in IS NULL)),
    CHECK (extension_date IS NULL OR (
        extension_date >= checkout_date
        AND extension_date <= date(checkout_date, '+30 days')
        AND (returned_date IS NULL OR extension_date <= returned_date)
    ))
);

-- A copy can be out to only one person at a time.
CREATE UNIQUE INDEX one_open_loan_per_copy
    ON loans (copy_id) WHERE returned_date IS NULL;

-- Only active members may borrow, and no more than 4 books at once.
CREATE TRIGGER check_member_can_borrow
BEFORE INSERT ON loans
BEGIN
    SELECT RAISE(ABORT, 'Member is not Active and cannot borrow')
    WHERE (SELECT status FROM members WHERE member_id = NEW.member_id) <> 'Active';

    SELECT RAISE(ABORT, 'Member already has 4 books checked out')
    WHERE (SELECT COUNT(*) FROM loans
           WHERE member_id = NEW.member_id AND returned_date IS NULL) >= 4;
END;

-- When a book comes back, update the copy's condition to match.
CREATE TRIGGER update_copy_condition_on_return
AFTER UPDATE OF returned_date ON loans
WHEN OLD.returned_date IS NULL AND NEW.returned_date IS NOT NULL
BEGIN
    UPDATE copies SET current_condition = NEW.condition_in
    WHERE copy_id = NEW.copy_id;
END;

-- ---------------------------------------------------------------
-- Views: saved questions you can ask the database at any time.
-- ---------------------------------------------------------------

-- Catalog: each title with its authors, year, genre and copy counts.
-- Sort or filter by year_published or genre.
CREATE VIEW book_catalog AS
SELECT
    b.book_id,
    b.title,
    (SELECT group_concat(name, ', ') FROM (
        SELECT trim(coalesce(a.first_name, '') || ' ' || a.last_name) AS name
        FROM book_authors ba JOIN authors a ON a.author_id = ba.author_id
        WHERE ba.book_id = b.book_id
        ORDER BY ba.author_order)) AS authors,
    b.year_published,
    g.name AS genre,
    (SELECT COUNT(*) FROM copies c WHERE c.book_id = b.book_id) AS total_copies,
    (SELECT COUNT(*) FROM copies c
     WHERE c.book_id = b.book_id
       AND NOT EXISTS (SELECT 1 FROM loans l
                       WHERE l.copy_id = c.copy_id AND l.returned_date IS NULL)
    ) AS copies_available
FROM books b
JOIN genres g ON g.genre_id = b.genre_id;

-- Books currently checked out, with any late fee building up as of today.
CREATE VIEW current_loans AS
SELECT
    l.loan_id,
    m.first_name || ' ' || m.last_name AS member,
    b.title,
    l.copy_id,
    l.checkout_date,
    l.due_date,
    l.extension_date IS NOT NULL AS extended,
    MAX(0, CAST(julianday(date('now')) - julianday(l.due_date) AS INTEGER)) AS days_overdue,
    25 * MAX(0, CAST(julianday(date('now')) - julianday(l.due_date) AS INTEGER)) AS fee_so_far_cents
FROM loans l
JOIN members m ON m.member_id = l.member_id
JOIN copies c  ON c.copy_id = l.copy_id
JOIN books b   ON b.book_id = c.book_id
WHERE l.returned_date IS NULL;

-- Members with their current age.
CREATE VIEW member_ages AS
SELECT
    member_id,
    first_name,
    last_name,
    birth_date,
    CAST(strftime('%Y', 'now') AS INTEGER) - CAST(strftime('%Y', birth_date) AS INTEGER)
        - (strftime('%m-%d', 'now') < strftime('%m-%d', birth_date)) AS age,
    status
FROM members;
