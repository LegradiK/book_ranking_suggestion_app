import requests
import sqlite3
import time
from flask import Flask, render_template, request
from bs4 import BeautifulSoup


GENRES = ['classic', 'crime', 'fiction', 'historical+fiction', 'mystery', 'thriller', 'fantasy', 'science+fiction', 'autobiography']

# app = Flask(__name__)

book_database = sqlite3.connect('books.db')
book_database.execute("""
                      CREATE TABLE IF NOT EXISTS books (
                        id       INTEGER PRIMARY KEY AUTOINCREMENT,
                        ol_key   TEXT UNIQUE,
                        author   TEXT,
                        title    TEXT NOT NULL,
                        year     INTEGER,
                        genre    TEXT,          -- comma-separated, e.g. 'crime, thriller'
                        rating   REAL,
                        book_url TEXT
                        )
                    """)
book_database.commit()


def fetch_subject(subject):
    response = requests.get(
        "https://openlibrary.org/search.json",
        params={"subject": subject, 
                "limit": 1000, 
                "page": 1,
                "sort":"rating"}
    )
    return response.json().get('docs', [])

def insert_data(book, genre):
    ol_key = book.get('key')
    # author name is stored as list in OpenLibrary database like ['Douglas Adams']
    author_list = book.get('author_name',[None])[0]
    author = author_list[0] if author_list else None
    title = book.get('title')
    year = book.get('first_publish_year')

    existing = book_database.execute(
        "SELECT id, genre FROM books WHERE ol_key = ?", (ol_key,)
    ).fetchone()

    if existing:
        current_genres = existing[1] or ""
        genres = [g.strip() for g in current_genres.split(",")]
        if genre not in genres:
            genres.append(genre)
            book_database.execute(
                "UPDATE books SET genre = ? WHERE ol_key = ?",
                (", ".join(genres), ol_key)
            )
    else:
        book_database.execute(
            "INSERT INTO books (ol_key, author, title, year, genre) VALUES (?, ?, ?, ?, ?)",
            (ol_key, author, title, year, genre)
        )

for genre in GENRES:
    print(f"Fetching: {genre}...")
    books = fetch_subject(genre)
    for book in books:
        insert_data(book, genre)
    book_database.commit()
    time.sleep(1)  # be polite to the API

book_database.close()
print("Done.")


# @app.route("/")
# def home():
#     return render_template("home.html")


# if __name__ == "__main__":
#     app.run(debug=True)