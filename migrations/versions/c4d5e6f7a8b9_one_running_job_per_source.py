"""one running scrape job per source

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Two concurrent run_scrape calls against the same source race to UPDATE overlapping Listing
    # rows in different orders (whatever order each crawl happens to encounter them in) and can
    # deadlock — reproduced in production 2026-09-13 (DeadlockDetectedError on `UPDATE listings
    # SET last_seen_at=...`). This constraint makes "only one RUNNING job per source" a DB-enforced
    # invariant instead of an app-level convention nothing was checking, so a second job for a
    # source already mid-crawl fails fast (see worker.py's run_scrape_job) instead of racing it.
    #
    # A row already stuck at RUNNING (e.g. from before #98 fixed jobs getting cancelled and left
    # RUNNING forever with no error recorded) would make CREATE UNIQUE INDEX fail outright the
    # moment a source has more than one such row — verified against a live copy of the schema.
    # Self-heal first: per source, keep only the most-recently-started RUNNING row as-is and fail
    # every other one, so the index can always be created regardless of what state exists.
    op.execute(
        sa.text(
            """
            UPDATE scrape_jobs
            SET status = 'FAILED',
                error = '{"type": "OrphanedRunningJob", "message": "Marked failed by migration c4d5e6f7a8b9 to allow one-running-job-per-source: another, more recently started job for the same source was also RUNNING"}'::json,
                finished_at = now()
            WHERE status = 'RUNNING'
              AND id NOT IN (
                  SELECT DISTINCT ON (source_id) id
                  FROM scrape_jobs
                  WHERE status = 'RUNNING'
                  ORDER BY source_id, started_at DESC NULLS LAST
              )
            """
        )
    )
    # 'RUNNING' (the enum member's name), not 'running' (.value) — matches how
    # Enum(ScrapeJobStatus, native_enum=False) (app/models/scrape_job.py) actually stores it.
    op.create_index(
        'uq_scrape_jobs_one_running_per_source',
        'scrape_jobs',
        ['source_id'],
        unique=True,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )


def downgrade() -> None:
    op.drop_index('uq_scrape_jobs_one_running_per_source', table_name='scrape_jobs')
