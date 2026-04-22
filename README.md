# 📚 BookShelf

A personal book discovery and ranking tool that combines reading-log popularity from **Open Library** with community ratings from **Goodreads** — giving each book a score that reflects both how widely read it is and how much people actually enjoyed it.

No sponsored placements. No algorithmic noise. Just books.

---

## How it works

**1. Fetch** — `pipeline.py` pulls books from the Open Library Search API across nine genres, sorted by reading-log activity. For each book, reading activity is totalled across want-to-read, currently reading, and already read via the Bookshelves API.

**2. Rate** — Each book is searched on Goodreads by title and author. When a confident match is found, the star rating and a direct link are saved. Books with fewer than 50 ratings or a readinglog under 100 are removed.

**3. Serve** — `server.py` serves everything from a local SQLite database via Flask. No external calls at browse time.

### Ranking formula

```
score = (goodreads_rating × 0.7) + (readinglog_count × 0.3)
```

---

## Setup

### 1. Install dependencies

```bash
pip install flask requests beautifulsoup4
```

### 2. Build the database

In `pipeline.py`, uncomment the fetch block and run:

```bash
python pipeline.py
```

This populates `books.db` with books from Open Library. May take a while depending on your connection.

### 3. Fetch Goodreads ratings

Uncomment `clean_books()` and `update_ratings()` in `pipeline.py` and run it again:

```bash
python pipeline.py
```

To fill in any books still missing ratings without re-running everything, `update_ratings_extra()` is available — it only processes books where `rating IS NULL`.

### 4. Run the app

```bash
python server.py
```

Visit `http://127.0.0.1:5000`

---

## Project structure

```
.
├── main.py          # Data pipeline — fetch, match, rate
├── bookshelf.py            # Flask server
├── books.db             # SQLite database (generated)
├── .gitignore
├── venv/
├── static/
│   ├── style.css
│   └── script.js
└── templates/
    ├── base.html
    ├── home.html
    ├── about.html
    └── footer.html
```

---

## Genres

Classic · Crime · Fiction · Historical Fiction · Mystery · Thriller · Fantasy · Science Fiction · Autobiography

---

## Notes

- Goodreads has no public API — ratings are matched by scraping search results. The thread pool is capped at 10 workers to avoid rate limiting.
- Non-English titles may not match if Goodreads indexes them under their English name.
- Don't name your Flask entry point `flask.py` or `app.py` — these conflict with Flask internals and cause a circular import error.
- The database only needs to be rebuilt when you want fresh data. Normal browsing makes no external calls.

---

## Data sources

- [Open Library](https://openlibrary.org) — book catalogue and reading logs (open API)
- [Goodreads](https://www.goodreads.com) — community star ratings (scraped from search)