"""Initial schema: extensions, all Phase 1 tables and their indexes.

Revision ID: 0001
Revises:
Create Date: 2026-11-28 10:55:06.058421
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Extensions must exist before the tables that use their types (vector, citext) and
# index operators (gin_trgm_ops). Autogenerate does not detect extensions.
EXTENSIONS = ("vector", "pg_trgm", "citext")


def upgrade() -> None:
    for name in EXTENSIONS:
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {name}")
    op.create_table(
        "explanation_cache",
        sa.Column("cache_key", sa.Text(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("cache_key", name=op.f("pk_explanation_cache")),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column(
            "payload", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "run_after", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'done', 'failed')", name=op.f("ck_jobs_status_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
    )
    op.create_index(
        "ix_jobs_queued",
        "jobs",
        ["id"],
        unique=False,
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("imdb_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("original_title", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("runtime_min", sa.Integer(), nullable=True),
        sa.Column("genres", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("overview", sa.Text(), nullable=False),
        sa.Column("tagline", sa.Text(), nullable=True),
        sa.Column("directors", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("top_cast", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("original_language", sa.Text(), nullable=False),
        sa.Column("popularity", sa.REAL(), nullable=False),
        sa.Column("vote_average", sa.REAL(), nullable=False),
        sa.Column("vote_count", sa.Integer(), nullable=False),
        sa.Column("poster_path", sa.Text(), nullable=True),
        sa.Column(
            "title_search",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('simple', title || ' ' || original_title)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movies")),
        sa.UniqueConstraint("tmdb_id", name=op.f("uq_movies_tmdb_id")),
    )
    op.create_index(
        "ix_movies_title_trgm",
        "movies",
        ["title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "letterboxd_imports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("total_entries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("matched_entries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'matching', 'done', 'failed')",
            name=op.f("ck_letterboxd_imports_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_letterboxd_imports_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_letterboxd_imports")),
    )
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("est_cost_usd", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_llm_usage_user_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_usage")),
    )
    op.create_table(
        "movie_embeddings",
        sa.Column("movie_id", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("text_version", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedded_text_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
            name=op.f("fk_movie_embeddings_movie_id_movies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("movie_id", "model_name", name=op.f("pk_movie_embeddings")),
    )
    op.create_index(
        "ix_movie_embeddings_embedding_hnsw",
        "movie_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_table(
        "user_movies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("import_id", sa.UUID(), nullable=False),
        sa.Column("lb_name", sa.Text(), nullable=False),
        sa.Column("lb_year", sa.Integer(), nullable=True),
        sa.Column("lb_uri", sa.Text(), nullable=False),
        sa.Column("rating", sa.REAL(), nullable=True),
        sa.Column("liked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("watched", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("watched_date", sa.Date(), nullable=True),
        sa.Column("rewatch", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("review_text", sa.Text(), nullable=True),
        sa.Column("in_watchlist", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("movie_id", sa.Integer(), nullable=True),
        sa.Column("match_status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("match_confidence", sa.REAL(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "match_status IN ('pending', 'matched', 'ambiguous', 'not_found')",
            name=op.f("ck_user_movies_match_status_valid"),
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 0.5 AND 5", name=op.f("ck_user_movies_rating_range")
        ),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["letterboxd_imports.id"],
            name=op.f("fk_user_movies_import_id_letterboxd_imports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
            name=op.f("fk_user_movies_movie_id_movies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_movies_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_movies")),
        sa.UniqueConstraint("user_id", "lb_uri", name=op.f("uq_user_movies_user_id_lb_uri")),
    )


def downgrade() -> None:
    # Dropping a table also drops its indexes.
    op.drop_table("user_movies")
    op.drop_table("movie_embeddings")
    op.drop_table("llm_usage")
    op.drop_table("letterboxd_imports")
    op.drop_table("users")
    op.drop_table("movies")
    op.drop_table("jobs")
    op.drop_table("explanation_cache")
    for name in reversed(EXTENSIONS):
        op.execute(f"DROP EXTENSION IF EXISTS {name}")
