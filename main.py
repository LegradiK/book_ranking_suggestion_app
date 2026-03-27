import requests
import sqlite3
import time
import threading
import re
from flask import Flask, render_template, request
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor


GENRES = ['classic', 'crime', 'fiction', 'historical+fiction', 'mystery', 'thriller', 'fantasy', 'science+fiction', 'autobiography']
# for getting most relevant books
SORTS = ["readinglog", "rating"]

BASE_URL = "https://openlibrary.org/"

# app = Flask(__name__)

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
                "sort": sort}
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


## still getting 5.0 rating for the ones which ratings are way below 5.0
## fix this issue next
def get_rating_goodreads(author, title):
    try:
        search_response = requests.get(
            "https://www.goodreads.com/search",
            params={"q": f"{title} {author}"},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        if search_response.status_code != 200:
            print(f"Blocked! Status code: {search_response.status_code}")
            return None
    
        soup = BeautifulSoup(search_response.text, "html.parser")
        
        rating_tag = soup.find("span", class_="minirating")
        if not rating_tag:
            return None
        
        # text looks like "4.23 avg rating — 1,234 ratings"
        rating = re.search(r"\d\.\d+", rating_tag.text)
        return float(rating.group()) if rating else None

    except Exception:
        return None

def update_ratings():
    books = book_database.execute("SELECT ol_key, author, title FROM books").fetchall()
    print(f"Updating ratings for {len(books)} books...")

    def update_one(book):
        ol_key, author, title = book
        rating = get_rating_goodreads(author, title)
        with db_lock:
            book_database.execute("UPDATE books SET rating = ? WHERE ol_key = ?", (rating, ol_key))

    with ThreadPoolExecutor(max_workers=50) as executor:
        for book in books:
            executor.submit(update_one, book)

    book_database.commit()
    print("Ratings updated.")

update_ratings()
book_database.close()



# @app.route("/")
# def home():
#     return render_template("home.html")


# if __name__ == "__main__":
#     app.run(debug=True)