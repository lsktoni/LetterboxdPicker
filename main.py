from letterboxdpy.watchlist import Watchlist
import random

username = "tonitbh"

watchlist = Watchlist(username)

# watchlist is a dict with a "movies" key containing {id: {slug, name, year, url}}
films = [movie["name"] for movie in watchlist.movies.values()]

if films:
    print(f"\nWatch this: {random.choice(films)}")
    print(f"(Picked from {len(films)} films in your watchlist)")
else:
    print("No films found. Make sure your watchlist is public.")