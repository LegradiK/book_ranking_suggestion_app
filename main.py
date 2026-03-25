import requests
import json
import os
from flask import Flask, render_template, request
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# CONFIG
BASE_URL = "www.librarything.com/tag/"

GENRES = {
    "Classic": "classic",
    "Crime": "crime",
    "Fiction": "fiction",
    "Historical Fiction": "historical+fiction",
    "Mystery": "mystery",
    "Thriller": "thriller",
    "Fantasy": "fantasy",
    "Science Fiction": "science+fiction"
}

all_books = []

response = requests.get(
    "https://openlibrary.org/search.json",
    params={"subject": "science fiction", 
            "limit": 100, 
            "page": 1,
            "sort":"rating"}
)
books = response.json()["docs"]
all_books.extend(books)


@app.route("/")
def home():
    return render_template("home.html", data=display_data, limit=limit)


if __name__ == "__main__":
    app.run(debug=True)