# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""Append-only triggers, run state guard, and watchlist cap (ARCHITECTURE 5.1, 5.3).

Revision ID: 0002
Revises: 0001

No later migration may drop or weaken these triggers without an ADR (section 5.3).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "config_versions",
    "run_transitions",
    "indicator_snapshots",
    "ticker_scores",
    "factor_scores",
    "narratives",
    "outcomes",
)
WATCHLIST_CAP = 300

REJECT_MUTATION = """
CREATE FUNCTION supertrends_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    RAISE EXCEPTION 'append_only_violation: % on table % is not allowed (append-only)',
        TG_OP, TG_TABLE_NAME USING ERRCODE = 'P0001';
END;
$fn$
"""

RECOMMENDATIONS_GUARD = """
CREATE FUNCTION supertrends_recommendations_guard() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'append_only_violation: DELETE on table % is not allowed (append-only)',
            TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
    IF (to_jsonb(NEW) - 'entry_price' - 'entry_date')
           IS DISTINCT FROM (to_jsonb(OLD) - 'entry_price' - 'entry_date') THEN
        RAISE EXCEPTION 'append_only_violation: only entry_price and entry_date may change on %',
            TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
    IF OLD.entry_price IS NOT NULL OR NEW.entry_price IS NULL THEN
        RAISE EXCEPTION 'append_only_violation: entry_price on % may be set once from NULL',
            TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$fn$
"""

RUNS_GUARD = """
CREATE FUNCTION supertrends_runs_guard() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'append_only_violation: DELETE on table % is not allowed',
            TG_TABLE_NAME USING ERRCODE = 'P0001';
    END IF;
    IF OLD.state IN ('published', 'failed') THEN
        IF (to_jsonb(NEW) - 'superseded_by') IS DISTINCT FROM (to_jsonb(OLD) - 'superseded_by')
           OR (NEW.superseded_by IS DISTINCT FROM OLD.superseded_by
               AND NOT (OLD.state = 'published' AND OLD.superseded_by IS NULL
                        AND NEW.superseded_by IS NOT NULL)) THEN
            RAISE EXCEPTION
                'append_only_violation: run in terminal state % is immutable except superseded_by',
                OLD.state USING ERRCODE = 'P0001';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.superseded_by IS DISTINCT FROM OLD.superseded_by THEN
        RAISE EXCEPTION 'append_only_violation: superseded_by may be set only on a published run'
            USING ERRCODE = 'P0001';
    END IF;
    IF NEW.state <> OLD.state AND NOT (
        NEW.state = 'failed'
        OR (OLD.state = 'queued' AND NEW.state = 'ingesting')
        OR (OLD.state = 'ingesting' AND NEW.state = 'computing')
        OR (OLD.state = 'computing' AND NEW.state = 'scoring')
        OR (OLD.state = 'scoring' AND NEW.state = 'selecting')
        OR (OLD.state = 'selecting' AND NEW.state = 'narrating')
        OR (OLD.state = 'narrating' AND NEW.state = 'published')
    ) THEN
        RAISE EXCEPTION 'append_only_violation: run state cannot move from % to %',
            OLD.state, NEW.state USING ERRCODE = 'P0001';
    END IF;
    IF NEW.published_at IS DISTINCT FROM OLD.published_at AND NEW.state <> 'published' THEN
        RAISE EXCEPTION 'append_only_violation: published_at requires state published'
            USING ERRCODE = 'P0001';
    END IF;
    RETURN NEW;
END;
$fn$
"""

WATCHLIST_CAP_FN = f"""
CREATE FUNCTION supertrends_watchlist_cap() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF (SELECT count(*) FROM watchlist_items WHERE watchlist_id = NEW.watchlist_id)
           > {WATCHLIST_CAP} THEN
        RAISE EXCEPTION 'watchlist % exceeds the {WATCHLIST_CAP} item cap', NEW.watchlist_id
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NULL;
END;
$fn$
"""  # noqa: S608 (integer constant, no user input)


def upgrade() -> None:
    op.execute(REJECT_MUTATION)
    op.execute(RECOMMENDATIONS_GUARD)
    op.execute(RUNS_GUARD)
    op.execute(WATCHLIST_CAP_FN)
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION supertrends_reject_mutation()"
        )
    op.execute(
        "CREATE TRIGGER trg_recommendations_guard BEFORE UPDATE OR DELETE ON recommendations "
        "FOR EACH ROW EXECUTE FUNCTION supertrends_recommendations_guard()"
    )
    op.execute(
        "CREATE TRIGGER trg_runs_guard BEFORE UPDATE OR DELETE ON runs "
        "FOR EACH ROW EXECUTE FUNCTION supertrends_runs_guard()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_watchlist_items_cap AFTER INSERT ON watchlist_items "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION supertrends_watchlist_cap()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_watchlist_items_cap ON watchlist_items")
    op.execute("DROP TRIGGER trg_runs_guard ON runs")
    op.execute("DROP TRIGGER trg_recommendations_guard ON recommendations")
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION supertrends_watchlist_cap()")
    op.execute("DROP FUNCTION supertrends_runs_guard()")
    op.execute("DROP FUNCTION supertrends_recommendations_guard()")
    op.execute("DROP FUNCTION supertrends_reject_mutation()")
