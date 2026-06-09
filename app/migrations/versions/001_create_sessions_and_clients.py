"""Crée les tables ingest_runs et ingest_articles.

Revision ID: 001
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ingester", sa.String(20), nullable=False),
        sa.Column("topics", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("status", sa.String(10), nullable=False, server_default="running"),
        sa.Column("fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("stored", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
    )
    op.create_index(
        "ix_ingest_runs_ingester_started",
        "ingest_runs",
        ["ingester", "started_at"],
    )

    op.create_table(
        "ingest_articles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer,
            sa.ForeignKey("ingest_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("article_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("publication", sa.String(255), nullable=False, server_default=""),
        sa.Column("url", sa.Text),
        sa.Column("topic", sa.String(100)),
        sa.Column("ingested_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ingest_articles_run_id", "ingest_articles", ["run_id"])
    op.create_index("ix_ingest_articles_publication", "ingest_articles", ["publication"])


def downgrade() -> None:
    op.drop_table("ingest_articles")
    op.drop_table("ingest_runs")
