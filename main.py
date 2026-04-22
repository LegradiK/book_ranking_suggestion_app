import requests
import sqlite3
import threading
import re
import unicodedata
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

"""
Data pipeline for BookShelf.

Handles three jobs:
  1. Fetch books from Open Library by genre and insert them into books.db
  2. Match each book against Goodreads by title/author and save the rating + URL
  3. Clean up low-quality entries (no rating, low reading activity)

Typical usage:
  - Run once with the fetch block uncommented to build books.db from scratch
  - Run again with update_ratings() uncommented to populate Goodreads ratings
  - Run update_ratings_extra() any time to fill in books that are still missing ratings
"""


GENRES = ['classic', 'crime', 'fiction', 'historical+fiction', 'mystery', 'thriller', 'fantasy', 'science+fiction', 'autobiography']
# for getting most relevant books
SORTS = ["readinglog", "rating"]

BASE_URL = "https://openlibrary.org/"

db_lock = threading.Lock()

book_database = sqlite3.connect('books.db', check_same_thread=False)
book_database.execute("""
                      CREATE TABLE IF NOT EXISTS books (
                        id       INTEGER PRIMARY KEY AUTOINCREMENT,
                        ol_key   TEXT UNIQUE,
                        author   TEXT,
                        title    TEXT NOT NULL,
                        year     INTEGER,
                        genre    TEXT,          -- comma-separated, e.g. 'crime, thriller'
                        rating   REAL,
                        book_url TEXT,
                        readinglog  INTEGER                        )
                    """)
book_database.commit()


def fetch_subject(subject, sort="readinglog"):
    response = requests.get(
        "https://openlibrary.org/search.json",
        params={"subject": subject, 
                "limit": 1000, 
                "page": 1,
                "sort": sort,
                "language": "eng"}
    )
    return response.json().get('docs', [])

def get_total_readinglog(ol_key):
    # ol_key is like /works/OL45804W — convert to bookshelves API
    url = f"https://openlibrary.org{ol_key}/bookshelves.json"
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    data = response.json().get('counts', {})
    return (
        data.get('want_to_read', 0) +
        data.get('currently_reading', 0) +
        data.get('already_read', 0)
    )

def insert_data(book, genre):
    ol_key = book.get('key')
    author = book.get('author_name', [None])[0]  # also fixed the char bug from before
    title = book.get('title')
    year = book.get('first_publish_year')
    url = BASE_URL + ol_key

    # 2. Wrap the read in a lock
    with db_lock:
        existing = book_database.execute(
            "SELECT id, genre FROM books WHERE ol_key = ?", (ol_key,)
        ).fetchone()

    if existing:
        current_genres = existing[1] or ""
        genres = [g.strip() for g in current_genres.split(",")]
        if genre not in genres:
            genres.append(genre)
            with db_lock:  # 3. Wrap every write in a lock
                book_database.execute(
                    "UPDATE books SET genre = ? WHERE ol_key = ?",
                    (", ".join(genres), ol_key)
                )
    else:
        readinglog = get_total_readinglog(ol_key=ol_key)
        with db_lock:
            book_database.execute(
                "INSERT INTO books (ol_key, author, title, year, genre, book_url, readinglog) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ol_key, author, title, year, genre, url, readinglog)
            )

def insert_data_parallel(books, genre):
    with ThreadPoolExecutor(max_workers=3) as executor:
        for book in books:
            executor.submit(insert_data, book, genre)

""" Create books.db by collecting bookdata from Openlibrary with their readinglogs per genre """
## Uncomment here for creating books.db
# for genre in GENRES:
#     for sort in SORTS:
#         print(f"Fetching: {genre} sorted by {sort}...")
#         books = fetch_subject(genre, sort)
#         insert_data_parallel(books, genre) 
#         book_database.commit()
#         print(f"{genre}: Done")

# print("Done.")

import unicodedata

def normalize(text):
    """Lowercase, remove special characters, and normalize unicode."""
    if not text:
        return ""
    text = text.lower()
    # Normalize unicode (e.g. accented chars)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # Remove special characters (keep only alphanumeric and spaces)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()

def normalize_author(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    # Collapse single-letter tokens (initials) to remove spaces between them
    # "h g wells" -> "hgwells", "hg wells" -> "hgwells"
    text = re.sub(r'\b([a-z])\s+(?=[a-z]\b)', r'\1', text)
    return text.strip()

def titles_match(search_title, result_title, threshold=0.75, max_length_ratio=2.5):
    search_normalized = normalize(clean_text(search_title))
    result_normalized = normalize(clean_text(result_title))
    search_words = search_normalized.split()

    if not search_words:
        return False

    # For very short titles (1-2 words), skip length ratio check entirely —
    # GR almost always appends a subtitle, making ratio explode unfairly
    if len(search_words) > 2 and len(search_normalized) > 0:
        length_ratio = len(result_normalized) / len(search_normalized)
        if length_ratio > max_length_ratio:
            return False

    matched = sum(1 for word in search_words if word in result_normalized)
    return (matched / len(search_words)) >= threshold


def clean_text(text):
    if not text:
        return text
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'\[.*?\]', '', text)
    # Strip leading/trailing punctuation like quotes and periods
    text = text.strip(' \t\n\r"\'`\u201c\u201d\u2018\u2019')
    # Remove "Book One / Two" series suffixes
    text = re.sub(r'\bbook\s+(one|two|three|four|\d+)\b', '', text, flags=re.IGNORECASE)
    return text.strip(' .')


def normalize_author(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    # Remove single-letter initials entirely (e.g. "walter s tevis" -> "walter tevis")
    text = re.sub(r'\b[a-z]\b', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def author_matches(clean_authors, book_author):
    result_normalized = normalize_author(book_author)
    result_parts = result_normalized.split()

    for a in clean_authors:
        a_parts = a.split()
        # Direct containment
        if a in result_normalized or result_normalized in a:
            return True
        # Any 2 words from stored author appear in result (handles middle names, "de", etc.)
        if len(a_parts) >= 2:
            matches = sum(1 for p in a_parts if p in result_parts and len(p) > 1)
            if matches >= 2:
                return True
        # Reversed last/first
        if len(a_parts) == 2:
            reversed_name = f"{a_parts[1]} {a_parts[0]}"
            if reversed_name in result_normalized:
                return True
    return False


def _search_goodreads(query):
    """Run a single Goodreads search query and return result rows."""
    response = requests.get(
        "https://www.goodreads.com/search",
        params={"q": query, "search_type": "books"},
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xhtml;q=0.9,*/*;q=0.8",
        }
    )
    if response.status_code != 200:
        print(f"Blocked! Status code: {response.status_code}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    return soup.select("table.tableList tr")


def _find_match_in_rows(rows, clean_title, clean_authors, ol_key, title, year=None):
    """Scan result rows and return (rating, book_link) for the first valid match."""
    for row in rows:
        book_title_tag = row.select_one("a.bookTitle span")
        book_author_tag = row.select_one("a.authorName span")
        rating_tag = row.select_one("span.minirating")
        book_link_tag = row.select_one("a.bookTitle")

        book_title = book_title_tag.text.strip() if book_title_tag else ""
        book_author = book_author_tag.text.strip() if book_author_tag else ""

        if not rating_tag or not book_title or not book_author:
            continue

        # Step 1: Match title
        if not titles_match(clean_title, book_title):
            continue

        # Step 2: Sanity-check author — pass if any stored author matches
        if not author_matches(clean_authors, book_author):
            continue

        # Step 3: Year check — if we have a year, it must match
        if year:
            year_match = re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', row.get_text())
            if year_match:
                result_year = int(year_match.group())
                if abs(result_year - year) > 2:   # allow ±2 years for edition differences
                    print(f"Year mismatch for '{book_title}': expected {year}, got {result_year}")
                    continue

        # Step 4: Parse ratings count — hard gate
        rating_text = rating_tag.text
        count_match = re.search(r"([\d,]+)\s+ratings?", rating_text)
        if not count_match:
            print(f"Skipping '{book_title}' — couldn't parse ratings count from: '{rating_text}'")
            continue

        count = int(count_match.group(1).replace(",", ""))
        if count < 50:
            print(f"Deleting '{title}' — only {count} ratings")
            with db_lock:
                book_database.execute("DELETE FROM books WHERE ol_key = ?", (ol_key,))
                book_database.commit()
            return None

        # Step 5: Extract rating
        rating_match = re.search(r"\d\.\d+", rating_text)
        if not rating_match:
            print(f"Skipping '{book_title}' — couldn't parse rating from: '{rating_text}'")
            continue

        rating = float(rating_match.group())

        # Step 6: Build Goodreads URL
        book_link = None
        if book_link_tag and book_link_tag.get("href"):
            href = book_link_tag["href"]
            book_link = f"https://www.goodreads.com{href}" if href.startswith("/") else href

        print(f"MATCHED: '{book_title}' by '{book_author}' | rating: {rating} ({count} ratings)")
        return rating, book_link

    return None


def get_rating_goodreads(ol_key, authors, title, year=None):
    if not authors or not title:
        return None

    # Skip titles that are too generic to match after cleaning
    clean_title = normalize(clean_text(title))
    if len(clean_title.split()) < 1 or clean_title in {"works", "diary", "an autobiography"}:
        print(f"Skipping '{title}' — title too generic after cleaning")
        return None

    clean_authors  = [normalize_author(clean_text(a)) for a in authors]
    # Filter out empty strings that result from bad author data like "'Layton', 'Edwin T.'"
    clean_authors  = [a for a in clean_authors if len(a.split()) >= 1 and len(a) > 1]
    if not clean_authors:
        print(f"Skipping '{title}' — no usable author after cleaning")
        return None

    primary_author = clean_authors[0]

    query_passes = [
        [f"{primary_author} {clean_title}", primary_author],
        [clean_title, f"{primary_author} {clean_title}"],
    ]

    try:
        for pass_num, queries in enumerate(query_passes, start=1):
            for query in queries:
                rows = _search_goodreads(query)
                if not rows:
                    continue
                result = _find_match_in_rows(rows, clean_title, clean_authors, ol_key, title, year=year)
                if result is not None:
                    if pass_num == 2:
                        print(f"Matched '{title}' on title-first fallback pass")
                    return result

        print(f"No match found for '{title}' by '{authors}'")
        return None

    except Exception as e:
        print(f"Error fetching '{title}' by '{authors}': {e}")
        return None


def update_one(book):
    ol_key, author, title, year = book   # unpack year too
    authors = [a.strip() for a in author.split(",")] if author else []
    result = get_rating_goodreads(ol_key, authors, title, year=year)

    if result is None:
        return

    rating, book_link = result
    with db_lock:
        if book_link:
            book_database.execute(
                "UPDATE books SET rating = ?, book_url = ? WHERE ol_key = ?",
                (rating, book_link, ol_key)
            )
        else:
            book_database.execute(
                "UPDATE books SET rating = ? WHERE ol_key = ?",
                (rating, ol_key)
            )
        book_database.commit()


def update_ratings():
    books = book_database.execute(
        "SELECT ol_key, author, title, year FROM books"
    ).fetchall()

    with ThreadPoolExecutor(max_workers=10) as executor:  # Lower from 100 — GR will rate-limit you
        futures = {executor.submit(update_one, book): book for book in books}
        for future in as_completed(futures):
            try:
                future.result()  # Surface any exceptions from threads
            except Exception as e:
                book = futures[future]
                print(f"Failed to update {book}: {e}")

    print("Ratings updated.")

def update_ratings_extra():
    books = book_database.execute(
        "SELECT ol_key, author, title, year FROM books WHERE rating IS NULL"
    ).fetchall()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(update_one, book): book for book in books}
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                book = futures[future]
                print(f"Failed to update {book}: {e}")

    print("Ratings updated.")

def clean_books():
    """ delete books if  they don't have ratings and readinglog is less than 100 """
    book_database.execute("""
        DELETE FROM books
        WHERE rating IS NULL
        AND readinglog < 100
    """)
    book_database.commit()


"""Update books.db with goodreads data - url and rating scores """
# Uncomment here for updating your database with up-to-date url and rating scores from goodreads
# clean_books()
# update_ratings()
# update_ratings_extra()
# book_database.close()




