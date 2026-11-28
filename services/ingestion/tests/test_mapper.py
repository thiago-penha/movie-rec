import copy
import json
from datetime import date
from pathlib import Path

import pytest

from ingestion.mapper import details_to_row

# Real TMDB response (recorded Nov 2026), with long lists trimmed to a few items.
FIXTURE = Path(__file__).parent / "fixtures" / "interstellar_details.json"


@pytest.fixture
def interstellar() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_maps_interstellar(interstellar) -> None:
    # Shuffle the cast: billing order must come from the "order" field, not list position.
    interstellar["credits"]["cast"].reverse()

    row = details_to_row(interstellar)

    assert row["tmdb_id"] == 157336
    assert row["imdb_id"] == "tt0816692"
    assert row["title"] == row["original_title"] == "Interstellar"
    assert row["release_date"] == date(2014, 11, 4)
    assert row["year"] == 2014
    assert row["runtime_min"] == 169
    assert row["genres"] == ["Adventure", "Drama", "Science Fiction"]
    assert row["countries"] == ["GB", "US"]  # ISO codes, not names
    assert "dystopia" in row["keywords"]
    # Christopher Nolan is in crew three times (director, producer x2); only "Director" counts.
    assert row["directors"] == ["Christopher Nolan"]
    assert row["top_cast"] == [
        "Matthew McConaughey",
        "Anne Hathaway",
        "Michael Caine",
        "Jessica Chastain",
        "Casey Affleck",
    ]
    assert row["tagline"].startswith("Mankind was born on Earth")
    assert row["poster_path"] == interstellar["poster_path"]  # TMDB swaps posters over time


def test_missing_values_become_null_not_empty_strings(interstellar) -> None:
    details = copy.deepcopy(interstellar)
    details.update(
        release_date="", runtime=0, tagline="", imdb_id=None, poster_path=None, overview=None
    )
    del details["keywords"], details["credits"], details["production_countries"]

    row = details_to_row(details)

    assert row["release_date"] is None
    assert row["year"] is None
    assert row["runtime_min"] is None
    assert row["tagline"] is None
    assert row["imdb_id"] is None
    assert row["poster_path"] is None
    assert row["overview"] == ""  # NOT NULL column (decision 011)
    assert row["keywords"] == row["directors"] == row["top_cast"] == row["countries"] == []
