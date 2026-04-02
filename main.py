import requests
import sqlite3
import threading
import re
import unicodedata
from flask import Flask, render_template
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


GENRES = ['classic', 'crime', 'fiction', 'historical+fiction', 'mystery', 'thriller', 'fantasy', 'science+fiction', 'autobiography']
# for getting most relevant books
SORTS = ["readinglog", "rating"]

BASE_URL = "https://openlibrary.org/"

app = Flask(__name__)

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

# ## Uncomment here for creating books.db ###
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

def titles_match(search_title, result_title, threshold=0.75):
    """Return True if most words of search_title appear in result_title."""
    search_words = normalize(search_title).split()
    result_normalized = normalize(result_title)
    
    if not search_words:
        return False

    matched = sum(1 for word in search_words if word in result_normalized)
    return (matched / len(search_words)) >= threshold

def clean_text(text):
    if not text:
        return text
    # Remove anything in parentheses or brackets
    text = re.sub(r'\(.*?\)', '', text)  # (...)
    text = re.sub(r'\[.*?\]', '', text)  # [...]
    return text.strip()

def get_rating_goodreads(ol_key, author, title):
    if not author or not title:
        print(f"{author}-{title}: Author or title is None, skipping.")
        return None

    clean_title = normalize(clean_text(title))
    clean_author = normalize_author(clean_text(author))

    try:
        # Step 1: Search by author only
        search_response = requests.get(
            "https://www.goodreads.com/search",
            params={"q": clean_author, "search_type": "books"},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xhtml;q=0.9,*/*;q=0.8",
            }
        )
        if search_response.status_code != 200:
            print(f"Blocked! Status code: {search_response.status_code}")
            return None

        soup = BeautifulSoup(search_response.text, "html.parser")
        results = soup.select("table.tableList tr")

        for row in results:
            book_title_tag = row.select_one("a.bookTitle span")
            book_author_tag = row.select_one("a.authorName span")
            rating_tag = row.select_one("span.minirating")
            book_link_tag = row.select_one("a.bookTitle")

            book_title = book_title_tag.text.strip() if book_title_tag else ""
            book_author = book_author_tag.text.strip() if book_author_tag else ""

            if not rating_tag or not book_title or not book_author:
                continue

            # Step 2: Match title from author's results
            if not titles_match(clean_title, book_title):
                continue

            # Step 3: Sanity-check author still matches (guards against author name collision)
            if normalize_author(clean_author) not in normalize_author(book_author):
                continue

            # Step 4: Extract rating — require minimum ratings count to avoid 5.0-from-1-rating noise
            rating_text = rating_tag.text
            count_match = re.search(r"([\d,]+)\s+rating", rating_text)
            if count_match:
                count = int(count_match.group(1).replace(",", ""))
                if count < 50:
                    print(f"Deleting '{title}' — only {count} ratings")
                    with db_lock:
                        book_database.execute("DELETE FROM books WHERE ol_key = ?", (ol_key,))
                        book_database.commit()
                    return None

            rating_match = re.search(r"\d\.\d+", rating_text)
            rating = float(rating_match.group()) if rating_match else None

            book_link = None
            if book_link_tag and book_link_tag.get("href"):
                href = book_link_tag["href"]
                book_link = f"https://www.goodreads.com{href}" if href.startswith("/") else href

            print(f"MATCHED: '{book_title}' by '{book_author}' | rating: {rating}")
            return rating, book_link

        return None

    except Exception as e:
        print(f"Error: {e}")
        return None


def update_one(book):
    ol_key, author, title = book
    result = get_rating_goodreads(ol_key, author, title)

    if result is None:
        return  # Skip if lookup failed

    rating, book_link = result  # Unpack the tuple

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
    books = book_database.execute("SELECT ol_key, author, title FROM books").fetchall()

    with ThreadPoolExecutor(max_workers=10) as executor:  # Lower from 100 — GR will rate-limit you
        futures = {executor.submit(update_one, book): book for book in books}
        for future in as_completed(futures):
            try:
                future.result()  # Surface any exceptions from threads
            except Exception as e:
                book = futures[future]
                print(f"Failed to update {book}: {e}")

    print("Ratings updated.")

# Uncomment here for updating your database with up-to-date url and rating scores
update_ratings()
book_database.close()




# @app.route("/")
# def home():
#     conn = sqlite3.connect("books.db")
#     conn.row_factory = sqlite3.Row
#     cursor = conn.cursor()

#     cursor.execute("""
#         SELECT title, author, rating, genre, year, readinglog, book_url
#         FROM books
#         WHERE rating IS NOT NULL
#     """)

#     rows = cursor.fetchall()
#     conn.close()

#     data = [dict(row) for row in rows]

#     # Extract unique individual genres server-side
#     genre_set = set()
#     for book in data:
#         if book.get("genre"):
#             for g in book["genre"].split(","):
#                 genre_set.add(g.strip())
#     genres = sorted(genre_set)

#     print(data[0])

#     return render_template("home.html", data=data, genres=genres, limit="all")

# @app.route("/about")
# def about():
#     return render_template('about.html')


# if __name__ == "__main__":
#     app.run(debug=True)


