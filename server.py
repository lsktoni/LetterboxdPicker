from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from letterboxdpy.watchlist import Watchlist
from letterboxdpy.user import User
import requests
import random
import json
import os
import re

app = Flask(__name__, static_folder=".")
CORS(app)

CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def get_movie_details(slug):
    try:
        url = f"https://letterboxd.com/film/{slug}/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=8)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")

        poster = None
        og = soup.find("meta", property="og:image")
        if og:
            poster = og.get("content")

        genres = []
        genre_links = soup.select("a[href*='/films/genre/']")
        for g in genre_links[:4]:
            genres.append(g.text.strip())

        runtime = None
        footer = soup.find("p", class_="text-footer")
        if footer:
            m = re.search(r"(\d+)\s*min", footer.text)
            if m:
                runtime = int(m.group(1))

        year = None
        year_el = soup.find("meta", property="og:title")
        if year_el:
            m = re.search(r"\((\d{4})\)", year_el.get("content", ""))
            if m:
                year = int(m.group(1))

        return {"poster": poster, "genres": genres, "runtime": runtime, "year": year}
    except Exception as e:
        print(f"Error fetching details for {slug}: {e}")
        return {"poster": None, "genres": [], "runtime": None, "year": None}

def get_watched_slugs(username):
    try:
        user = User(username)
        films = user.get_films()
        if isinstance(films, dict):
            return set(films.keys())
        return set()
    except Exception as e:
        print(f"Could not fetch watched films: {e}")
        return set()

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/v2")
def index_v2():
    return send_from_directory(".", "index_v2.html")

@app.route("/api/last-username")
def last_username():
    cache = load_cache()
    return jsonify({"username": cache.get("last_username", "")})

@app.route("/api/pick", methods=["POST"])
def pick():
    data = request.json
    username = data.get("username", "").strip()
    if not username:
        return jsonify({"error": "No username provided"}), 400

    genre_filter   = data.get("genre", "").strip().lower()
    year_min       = data.get("year_min")
    year_max       = data.get("year_max")
    runtime_max    = data.get("runtime_max")
    exclude_watched = data.get("exclude_watched", False)

    try:
        watchlist = Watchlist(username)
        movies = list(watchlist.movies.values())
    except Exception as e:
        return jsonify({"error": f"Could not fetch watchlist: {str(e)}"}), 500

    if not movies:
        return jsonify({"error": "Watchlist is empty or private"}), 404

    cache = load_cache()
    cache["last_username"] = username
    save_cache(cache)

    total_watchlist = len(movies)

    watched_slugs = set()
    if exclude_watched:
        watched_slugs = get_watched_slugs(username)

    # Year filter (fast — from watchlist data)
    if year_min or year_max:
        filtered = []
        for m in movies:
            y = m.get("year")
            try:
                y = int(y) if y else None
                if y:
                    if year_min and y < int(year_min):
                        continue
                    if year_max and y > int(year_max):
                        continue
            except:
                pass
            filtered.append(m)
        movies = filtered

    # Exclude watched
    if exclude_watched and watched_slugs:
        movies = [m for m in movies if m.get("slug", "") not in watched_slugs]

    if not movies:
        return jsonify({"error": "No films match your filters"}), 404

    random.shuffle(movies)
    needs_detail = bool(genre_filter or runtime_max)

    selected = None
    details = {}

    if needs_detail:
        for candidate in movies[:20]:
            slug = candidate.get("slug", "")
            d = get_movie_details(slug)
            if genre_filter:
                genres_lower = [g.lower() for g in d.get("genres", [])]
                if not any(genre_filter in g for g in genres_lower):
                    continue
            if runtime_max and d.get("runtime"):
                if d["runtime"] > int(runtime_max):
                    continue
            selected = candidate
            details = d
            break
        if not selected:
            return jsonify({"error": "No films matched filters (checked 20 candidates — try broadening)"}), 404
    else:
        selected = movies[0]
        details = get_movie_details(selected.get("slug", ""))

    slug = selected.get("slug", "")
    year = selected.get("year") or details.get("year", "")

    return jsonify({
        "title":    selected.get("name", "Unknown"),
        "year":     str(year) if year else "",
        "url":      f"https://letterboxd.com/film/{slug}/",
        "poster":   details.get("poster"),
        "genres":   details.get("genres", []),
        "runtime":  details.get("runtime"),
        "total":    total_watchlist,
        "filtered": len(movies)
    })

if __name__ == "__main__":
    print("Letterboxd Suggester running:")
    print("  Version 1 (original UI) → http://localhost:5000/")
    print("  Version 2 (slot machine) → http://localhost:5000/v2")
    app.run(debug=False, port=5000)