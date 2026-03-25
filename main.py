import requests
import json
import os
from flask import Flask, render_template, request
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# CONFIG
BASE_URL = "https://www.goodreads.com/"
PREFIX = ["choiceawards/best", "choiceawards/readers-favorite"]

GENRES = {
    "Fiction": "fiction-books",
    "Historical Fiction": "historical-fiction-books",
    "Mystery / Thriller": "mystery-thriller-books",
    "Fantasy": "fantasy-books",
    "Science Fiction": "science-fiction-books"
}

YEARS = list(range(2011, 2026))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

DATA_FILE = "books.json"

app = Flask(__name__)

# --------------------------
# FETCH RATING (PARALLEL)
# --------------------------
def fetch_rating(session, book_url):
    try:
        r = session.get(book_url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        div = soup.select_one("div.RatingStatistics__rating")
        if div:
            return book_url, div.text.strip()

        return book_url, None
    except:
        return book_url, None


# --------------------------
# MAIN SCRAPER
# --------------------------
def scrape_all_genres():
    session = requests.Session()
    session.headers.update(HEADERS)

    books = []

    # -------- Phase 1: Collect metadata --------
    for year in YEARS:
        prefix = PREFIX[0] if year < 2024 else PREFIX[1]

        for genre, genre_url in GENRES.items():
            full_url = f"{BASE_URL}{prefix}-{genre_url}-{year}"

            response = session.get(full_url)
            if response.status_code != 200:
                print(f"Failed ({response.status_code}): {full_url}")
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            vote_blocks = soup.find_all("strong", string=lambda s: s and "votes" in s)

            for rank, block in enumerate(vote_blocks, start=1):
                votes = (
                    block.get_text(strip=True)
                    .replace("votes", "")
                    .replace(",", "")
                    .strip()
                )

                next_a = block.find_next("a")
                if not next_a:
                    continue

                book_url = BASE_URL + next_a["href"]
                img = next_a.find("img")

                if not img or " by " not in img.get("alt", ""):
                    continue

                title, author = img["alt"].split(" by ", 1)

                books.append({
                    "rank": rank,
                    "votes": votes,
                    "genre": genre,
                    "year": year,
                    "title": title.strip(),
                    "author": author.strip(),
                    "rating": None,  # placeholder
                    "book_url": book_url
                })

        print(f"Collected metadata for year {year}")

    print(f"Total books collected: {len(books)}")

    # -------- Phase 2: Fetch ratings in parallel --------
    book_map = {book["book_url"]: book for book in books}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(fetch_rating, session, book["book_url"])
            for book in books
        ]

        for future in as_completed(futures):
            url, rating = future.result()
            book_map[url]["rating"] = rating

    print("Finished fetching ratings")

    return books


# --------------------------
# LOAD OR SCRAPE
# --------------------------
def load_or_scrape():
    if os.path.exists(DATA_FILE):
        print("Loading from file")
        with open(DATA_FILE) as f:
            return json.load(f)

    data = scrape_all_genres()

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved {len(data)} books")
    return data


BOOK_DATA = load_or_scrape()


# --------------------------
# FLASK ROUTE
# --------------------------
@app.route("/")
def home():
    limit_param = request.args.get("limit", "all")
    
    if limit_param == "all":
        display_data = BOOK_DATA
        limit = "all"
    elif limit_param.isdigit() and int(limit_param) in [10, 20, 30, 50, 100]:
        limit = int(limit_param)
        display_data = BOOK_DATA[:limit]
    else:
        display_data = BOOK_DATA
        limit = "all"
    return render_template("home.html", data=display_data, limit=limit)


if __name__ == "__main__":
    app.run(debug=True)