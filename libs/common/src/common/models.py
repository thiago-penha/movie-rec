"""SQLAlchemy models for the schema in PROJECT_SPEC §5.1.

Every service imports these, but each table has one owner service that writes it
(noted per class). Alembic (db/) builds migrations from this metadata.

Nullability rule: a column is nullable only when the spec says "null"; text arrays
and flags default to empty / false so inserts only set what they know.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    REAL,
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Dimension of intfloat/multilingual-e5-small. Changing the model to one with another
# size needs a migration (and re-embedding everything).
EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    # Predictable constraint names (e.g. ck_jobs_status_valid). Without them Postgres
    # invents names, and later Alembic migrations cannot reliably drop or alter them.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )

    # Python type -> column type for every `Mapped[...]` annotation below:
    # plain `str` becomes Postgres `text` (not varchar) and datetimes keep the time zone.
    type_annotation_map = {
        str: Text,
        float: REAL,  # spec §5.1 uses `real`; 6 significant digits is plenty for scores
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }

    # Declared on the base, so every table gets it (spec: "All tables have created_at").
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


def _uuid_pk() -> Mapped[uuid.UUID]:
    # gen_random_uuid() is built into Postgres 13+, so the database fills the id.
    return mapped_column(UUID, primary_key=True, server_default=func.gen_random_uuid())


def _text_array() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), server_default="{}")


class User(Base):
    """Owner: api."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # citext compares case-insensitively, so "Ana@x.com" and "ana@x.com" are one user.
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str]
    display_name: Mapped[str]


class Movie(Base):
    """Owner: ingestion. One row per TMDB movie."""

    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)  # serial
    tmdb_id: Mapped[int] = mapped_column(unique=True)
    imdb_id: Mapped[str | None]
    title: Mapped[str]
    original_title: Mapped[str]
    year: Mapped[int | None]
    release_date: Mapped[date | None]
    runtime_min: Mapped[int | None]
    genres: Mapped[list[str]] = _text_array()
    keywords: Mapped[list[str]] = _text_array()
    overview: Mapped[str]
    tagline: Mapped[str | None]
    directors: Mapped[list[str]] = _text_array()
    top_cast: Mapped[list[str]] = _text_array()
    original_language: Mapped[str]
    popularity: Mapped[float]
    vote_average: Mapped[float]
    vote_count: Mapped[int]
    poster_path: Mapped[str | None]
    # Generated column: Postgres keeps it in sync with the titles on every write.
    # 'simple' = no stemming and no stop words, because titles come in many languages
    # and an English dictionary would mangle "Amélie" or "Cidade de Deus".
    title_search: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', title || ' ' || original_title)", persisted=True),
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Trigram index: makes `title ILIKE '%matr%'` and similarity() fast, which
        # autocomplete and fuzzy Letterboxd title matching need.
        Index(
            "ix_movies_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )


class MovieEmbedding(Base):
    """Owner: ingestion. One vector per (movie, model)."""

    __tablename__ = "movie_embeddings"

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    # Part of the key so two models can coexist while switching models.
    model_name: Mapped[str] = mapped_column(primary_key=True)
    text_version: Mapped[str]
    # Vectors are stored normalized (length 1), so cosine distance ranks the same as
    # dot product. Query with `embedding <=> :q` (cosine distance, 0 = same direction).
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    embedded_text_hash: Mapped[str]

    __table_args__ = (
        # HNSW: an approximate nearest-neighbour index (a graph of vectors). It finds
        # the closest vectors without comparing against every row. vector_cosine_ops
        # makes it serve the `<=>` operator; other operators would not use it.
        Index(
            "ix_movie_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class LetterboxdImport(Base):
    """Owner: api (the ingestion worker updates status and counters)."""

    __tablename__ = "letterboxd_imports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    filename: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="pending")
    total_entries: Mapped[int] = mapped_column(server_default="0")
    matched_entries: Mapped[int] = mapped_column(server_default="0")
    error: Mapped[str | None]

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'matching', 'done', 'failed')", name="status_valid"),
    )


class UserMovie(Base):
    """Owner: api inserts; ingestion fills movie_id and the match fields."""

    __tablename__ = "user_movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    import_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("letterboxd_imports.id", ondelete="CASCADE")
    )
    lb_name: Mapped[str]
    lb_year: Mapped[int | None]
    # Letterboxd *film* URI (decision 007), the merge key across the export's CSVs.
    lb_uri: Mapped[str]
    rating: Mapped[float | None]
    liked: Mapped[bool] = mapped_column(server_default="false")
    # false = watchlist-only row: not used for the taste vector and not excluded from
    # recommendations (decision 006).
    watched: Mapped[bool] = mapped_column(server_default="false")
    watched_date: Mapped[date | None]
    rewatch: Mapped[bool] = mapped_column(server_default="false")
    review_text: Mapped[str | None]
    in_watchlist: Mapped[bool] = mapped_column(server_default="false")
    # SET NULL: if a movie is ever deleted, the user's history row stays and can be re-matched.
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id", ondelete="SET NULL"))
    match_status: Mapped[str] = mapped_column(server_default="pending")
    match_confidence: Mapped[float | None]

    __table_args__ = (
        UniqueConstraint("user_id", "lb_uri"),
        CheckConstraint(
            "match_status IN ('pending', 'matched', 'ambiguous', 'not_found')",
            name="match_status_valid",
        ),
        CheckConstraint("rating IS NULL OR rating BETWEEN 0.5 AND 5", name="rating_range"),
    )


class Job(Base):
    """Postgres job queue (spec §5.4). Use common.jobs, not this table directly."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # bigserial
    type: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(server_default="{}")
    status: Mapped[str] = mapped_column(server_default="queued")
    attempts: Mapped[int] = mapped_column(server_default="0")
    run_after: Mapped[datetime] = mapped_column(server_default=func.now())
    last_error: Mapped[str | None]
    locked_at: Mapped[datetime | None]

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status_valid"),
        # Partial index: holds only queued jobs, so claim_next() stays fast however
        # many finished jobs pile up in the table.
        Index("ix_jobs_queued", "id", postgresql_where=text("status = 'queued'")),
    )


class LlmUsage(Base):
    """Owner: recommender. One row per Claude call, for budgets and quotas (§10.2)."""

    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # SET NULL: deleting a user keeps the cost history.
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    endpoint: Mapped[str]
    model: Mapped[str]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    # numeric, not float: money must add up exactly when summing a day of calls.
    est_cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))


class ExplanationCache(Base):
    """Owner: recommender. Cached LLM explanations, keyed by a hash of the request."""

    __tablename__ = "explanation_cache"

    cache_key: Mapped[str] = mapped_column(primary_key=True)
    response: Mapped[dict[str, Any]]
