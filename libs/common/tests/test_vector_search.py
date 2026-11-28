"""Acceptance (Phase 1): a stored vector is found again by a cosine-distance query."""

import math
import random

from sqlalchemy import select

from common.models import EMBEDDING_DIM, Movie, MovieEmbedding


def _unit_vector(rng: random.Random) -> list[float]:
    vector = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector]  # stored vectors are normalized


def test_nearest_neighbour_is_the_movie_whose_vector_was_queried(db_session) -> None:
    rng = random.Random(42)
    vectors = {}
    for tmdb_id in (1, 2, 3):
        movie = Movie(
            tmdb_id=tmdb_id,
            title=f"Movie {tmdb_id}",
            original_title=f"Movie {tmdb_id}",
            overview="",
            original_language="en",
            popularity=1.0,
            vote_average=7.0,
            vote_count=100,
        )
        db_session.add(movie)
        db_session.flush()  # assigns movie.id
        vectors[movie.id] = _unit_vector(rng)
        db_session.add(
            MovieEmbedding(
                movie_id=movie.id,
                model_name="test",
                text_version="v1",
                embedding=vectors[movie.id],
                embedded_text_hash="x",
            )
        )
    db_session.commit()

    target_id = 2
    # `<=>` is pgvector's cosine distance operator; .cosine_distance() renders it.
    nearest = db_session.scalar(
        select(MovieEmbedding.movie_id)
        .order_by(MovieEmbedding.embedding.cosine_distance(vectors[target_id]))
        .limit(1)
    )

    assert nearest == target_id
