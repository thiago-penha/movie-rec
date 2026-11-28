"""Turn a TMDB movie-details response into a `movies` row (a dict of column values)."""

from datetime import date
from typing import Any

TOP_CAST_SIZE = 5


def _none_if_empty(value: str | None) -> str | None:
    # TMDB uses "" and null interchangeably for missing text; store NULL for both.
    return value or None


def details_to_row(details: dict[str, Any]) -> dict[str, Any]:
    """`details` comes from /movie/{id}?append_to_response=keywords,credits."""
    release = _none_if_empty(details.get("release_date"))
    release_date = date.fromisoformat(release) if release else None
    credits = details.get("credits") or {}
    cast = sorted(credits.get("cast") or [], key=lambda person: person.get("order", 0))

    return {
        "tmdb_id": details["id"],
        "imdb_id": _none_if_empty(details.get("imdb_id")),
        "title": details["title"],
        "original_title": details.get("original_title") or details["title"],
        "year": release_date.year if release_date else None,
        "release_date": release_date,
        # TMDB reports 0 when the runtime is unknown.
        "runtime_min": details.get("runtime") or None,
        "genres": [genre["name"] for genre in details.get("genres") or []],
        "countries": [c["iso_3166_1"] for c in details.get("production_countries") or []],
        "keywords": [k["name"] for k in (details.get("keywords") or {}).get("keywords") or []],
        "overview": details.get("overview") or "",
        "tagline": _none_if_empty(details.get("tagline")),
        # dict.fromkeys drops duplicates (one person can be listed twice in crew)
        # while keeping TMDB's order.
        "directors": list(
            dict.fromkeys(
                person["name"]
                for person in credits.get("crew") or []
                if person.get("job") == "Director"
            )
        ),
        "top_cast": [person["name"] for person in cast[:TOP_CAST_SIZE]],
        "original_language": details.get("original_language") or "",
        "popularity": details.get("popularity") or 0.0,
        "vote_average": details.get("vote_average") or 0.0,
        "vote_count": details.get("vote_count") or 0,
        "poster_path": _none_if_empty(details.get("poster_path")),
    }
