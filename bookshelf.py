import sqlite3
from flask import Flask, render_template

"""
Flask server for BookShelf.

Serves two routes:
  /     — main rankings page, loads all rated books from books.db and passes
           them to the template along with a sorted list of unique genres
  /about — static about page

Run with: python server.py
"""


app = Flask(__name__)

@app.route("/")
def home():
    conn = sqlite3.connect("books.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, author, rating, genre, year, readinglog, book_url
        FROM books
        WHERE rating IS NOT NULL
    """)

    rows = cursor.fetchall()
    conn.close()

    data = [dict(row) for row in rows]

    # Extract unique individual genres server-side
    genre_set = set()
    for book in data:
        if book.get("genre"):
            for g in book["genre"].split(","):
                genre_set.add(g.strip())
    genres = sorted(genre_set)

    print(data[0])

    return render_template("home.html", data=data, genres=genres, limit="all")

@app.route("/about")
def about():
    return render_template('about.html')


if __name__ == "__main__":
    app.run(debug=True)