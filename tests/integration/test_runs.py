# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright 2026 Serverless Ventures LLC
"""The daily run orchestrator end to end against real Postgres (S3-T07, TEST_PLAN section 10.15).

Runs only when SUPERTRENDS_IT_DATABASE_URL is set. Every test migrates in its own fixture and
downgrades to base afterwards. The data is the synthetic fixture dataset; no network is used.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy import Engine

from supertrends.data import db
from supertrends.data.models import Narrative, Recommendation, Run
from supertrends.data.providers.fixture import FixtureFundamentals, FixtureProvider, FixtureUniverse
from supertrends.narrative.evidence import evidence_schema
from supertrends.runs import orchestrator, service
from supertrends.runs.narrator import MinimalNarrator, NarratedPick, PickContext
from supertrends.runs.orchestrator import RunDeps, RunOutcome, execute_run
from supertrends.runs.state import RunState
from supertrends.scoring.config import ScoringConfig, load_scoring_config

URL = os.environ.get("SUPERTRENDS_IT_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="set SUPERTRENDS_IT_DATABASE_URL to run")

ROOT = Path(__file__).resolve().parents[2]
SEED = 20261114
END = date(2026, 11, 13)
SYMBOLS = [f"FX{c}" for c in "ABCDEFGHIJKL"]
ORDER = ["queued", "ingesting", "computing", "scoring", "selecting", "narrating", "published"]


def _downgrade(engine: Engine) -> None:
    config = db.alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = db.create_db_engine(url=URL)
    _downgrade(eng)
    db.migrate(eng)
    yield eng
    _downgrade(eng)
    eng.dispose()


@pytest.fixture(scope="module")
def universe() -> FixtureUniverse:
    return FixtureUniverse(seed=SEED, end_date=END)


@pytest.fixture(scope="module")
def config() -> ScoringConfig:
    return load_scoring_config(ROOT / "config" / "scoring.yaml")


class ShapedProvider(FixtureProvider):
    """Fixture data with a few symbols cut short: `short` keeps 60 bars, `stale` stops early."""

    def __init__(self, universe: FixtureUniverse, *, short: str, stale: str) -> None:
        super().__init__(universe)
        self.short = short
        self.stale = stale

    def daily_bars(self, symbol: str, start: date, end: date) -> Sequence[Any]:
        bars = list(super().daily_bars(symbol, start, end))
        if symbol == self.short:
            return bars[-60:]
        if symbol == self.stale:
            return bars[:-5]
        return bars

    def grouped_daily(self, session: date) -> Sequence[Any]:
        return [b for b in super().grouped_daily(session) if b.symbol != self.stale]


def _deps(
    universe: FixtureUniverse, config: ScoringConfig, *, market: Any = None, **kw: Any
) -> RunDeps:
    return RunDeps(
        market=market or FixtureProvider(universe),
        fundamentals=FixtureFundamentals(universe),
        config=config,
        symbols=SYMBOLS,
        **kw,
    )


def _picks(engine: Engine, run_id: str) -> list[tuple[Any, ...]]:
    return [
        (r.side, r.rank, r.symbol, r.display_score, r.confidence, r.band, dict(r.evidence))
        for r in service.recommendations_for_run(engine, run_id)
    ]


def _run_count(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.scalar(sa.select(sa.func.count()).select_from(Run)) or 0)


class Probe:
    """A narrator that runs a callback (against the database) before delegating."""

    def __init__(self, callback: Any) -> None:
        self.callback = callback

    def narrate(self, ctx: PickContext) -> NarratedPick:
        self.callback()
        return MinimalNarrator().narrate(ctx)


def test_it_runs_state_machine_transitions_queued_to_published_in_order(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    seen: list[str] = []
    out = execute_run(
        engine, _deps(universe, config), trade_date=END, progress=lambda _r, s: seen.append(s.value)
    )
    assert out.status == "published", out.error_detail
    assert out.run_id is not None
    view = service.get_run(engine, out.run_id)
    assert view is not None
    assert [t.to_state for t in view.transitions] == ORDER
    assert [t.from_state for t in view.transitions] == [None, *ORDER[:-1]]
    assert view.state == "published"
    assert seen == ORDER
    assert view.summary["trade_date"] == END.isoformat()


def test_it_runs_publish_writes_recommendations_and_published_at_in_single_transaction(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    during: dict[str, Any] = {}

    def look() -> None:
        with engine.connect() as conn:
            during["recs"] = conn.scalar(sa.select(sa.func.count()).select_from(Recommendation))
            during["published"] = conn.scalar(
                sa.select(sa.func.count()).select_from(Run).where(Run.published_at.is_not(None))
            )

    out = execute_run(engine, _deps(universe, config, narrator=Probe(look)), trade_date=END)
    assert out.status == "published", out.error_detail
    assert during == {"recs": 0, "published": 0}  # nothing visible before the publish commit
    assert out.run_id is not None
    recs = service.recommendations_for_run(engine, out.run_id)
    assert recs
    view = service.get_run(engine, out.run_id)
    assert view is not None
    assert view.published_at is not None
    assert len(view.summary["buys"]) + len(view.summary["sells"]) == len(recs)
    assert service.latest_published_run(engine) is not None


def test_it_runs_publish_stores_full_evidence_and_template_narrative(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    out = execute_run(engine, _deps(universe, config), trade_date=END)
    assert out.run_id is not None
    recs = service.recommendations_for_run(engine, out.run_id)
    assert recs
    validator = jsonschema.Draft202012Validator(evidence_schema())
    for rec in recs:
        validator.validate(dict(rec.evidence))
        assert rec.narrative is not None
        assert rec.narrative.source == "template"
        assert rec.symbol in rec.narrative.text
        assert rec.disclaimer
    assert out.summary["narrative_template"] == len(recs)
    assert out.summary["narrative_errors"] == 0
    with engine.connect() as conn:
        assert conn.scalar(sa.select(sa.func.count()).select_from(Narrative)) == len(recs)


def test_it_runs_narrator_failure_falls_back_to_minimal_and_run_publishes(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    class Boom:
        def narrate(self, ctx: PickContext) -> NarratedPick:
            raise RuntimeError("narrator broke")

    out = execute_run(engine, _deps(universe, config, narrator=Boom()), trade_date=END)
    assert out.status == "published"
    assert out.run_id is not None
    recs = service.recommendations_for_run(engine, out.run_id)
    assert out.summary["narrative_errors"] == len(recs) > 0
    assert all(r.narrative is None and r.evidence["disclaimer"] for r in recs)


_CHILD = textwrap.dedent(
    """
    import sys, time
    from datetime import date
    from pathlib import Path
    from supertrends.data import db
    from supertrends.data.providers.fixture import FixtureFundamentals, FixtureProvider
    from supertrends.data.providers.fixture import FixtureUniverse
    from supertrends.runs.orchestrator import RunDeps, execute_run
    from supertrends.scoring.config import load_scoring_config

    class Hang:
        def narrate(self, ctx):
            Path(sys.argv[3]).write_text("narrating")
            time.sleep(120)

    url, root, flag = sys.argv[1], sys.argv[2], sys.argv[3]
    u = FixtureUniverse(seed=%d, end_date=date(2026, 11, 13))
    deps = RunDeps(
        market=FixtureProvider(u),
        fundamentals=FixtureFundamentals(u),
        config=load_scoring_config(root + "/config/scoring.yaml"),
        symbols=%r,
        narrator=Hang(),
    )
    execute_run(db.create_db_engine(url=url), deps, trade_date=date(2026, 11, 13))
    """
    % (SEED, SYMBOLS)
)


def test_it_runs_publish_midrun_process_kill_previous_run_stays_latest(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig, tmp_path: Path
) -> None:
    previous_date = universe.sessions[-2]
    first = execute_run(engine, _deps(universe, config), trade_date=previous_date)
    assert first.status == "published"
    before = service.latest_published_run(engine)
    assert before is not None
    assert before.id == first.run_id
    flag = tmp_path / "narrating.flag"
    proc = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-c", _CHILD, URL, str(ROOT), str(flag)],
        env={**os.environ, "SUPERTRENDS_IT_DATABASE_URL": URL},
    )
    try:
        deadline = time.monotonic() + 90
        while not flag.exists():
            assert proc.poll() is None, "the run process exited before narrating"
            assert time.monotonic() < deadline, "the run never reached narrating"
            time.sleep(0.1)
        proc.send_signal(signal.SIGKILL)  # no cleanup handler can run
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    after = service.latest_published_run(engine)
    assert after is not None
    assert after.id == before.id  # the previous run is still the latest
    with engine.connect() as conn:
        orphan = conn.execute(
            sa.select(Run.id, Run.state, Run.published_at).where(Run.id != first.run_id)
        ).one()
        assert orphan.state == RunState.NARRATING.value
        assert orphan.published_at is None
        assert conn.scalar(sa.select(sa.func.count()).select_from(Recommendation)) == len(
            service.recommendations_for_run(engine, first.run_id or "")
        )
    # the next executor reaps the orphan as abandoned and publishes normally
    redo = execute_run(engine, _deps(universe, config), trade_date=END)
    assert redo.status == "published"
    reaped = service.get_run(engine, orphan.id)
    assert reaped is not None
    assert reaped.state == "failed"


def test_it_runs_failed_run_leaves_previous_published_run_as_latest(
    engine: Engine,
    universe: FixtureUniverse,
    config: ScoringConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = execute_run(engine, _deps(universe, config), trade_date=universe.sessions[-2])
    assert first.status == "published"

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("selection exploded")

    monkeypatch.setattr(orchestrator, "_select", boom)
    bad = execute_run(engine, _deps(universe, config), trade_date=END)
    assert bad.status == "failed"
    assert bad.error_code == "internal"
    assert bad.run_id is not None
    failed = service.get_run(engine, bad.run_id)
    assert failed is not None
    assert failed.state == "failed"
    assert failed.published_at is None
    assert failed.error_detail and "selection exploded" in failed.error_detail
    latest = service.latest_published_run(engine)
    assert latest is not None
    assert latest.id == first.run_id
    assert service.recommendations_for_run(engine, bad.run_id) == []


def test_it_runs_two_simultaneous_triggers_one_run_one_already_running_response(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    gate = threading.Event()
    started = threading.Event()

    def hold() -> None:
        started.set()
        assert gate.wait(timeout=60)

    deps = _deps(universe, config, narrator=Probe(hold))
    barrier = threading.Barrier(2)

    def trigger() -> RunOutcome:
        barrier.wait(timeout=30)
        return execute_run(engine, deps, trade_date=END)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(trigger), pool.submit(trigger)]
        assert started.wait(timeout=90)  # the winner is mid-run, holding the lock
        loser = next(f for f in futures if f.done()).result(timeout=30)
        assert loser.status == "already_running"
        assert loser.run_id is None
        gate.set()
        outcomes = [f.result(timeout=90) for f in futures]
    assert sorted(o.status for o in outcomes) == ["already_running", "published"]
    assert _run_count(engine) == 1
    # the API path also refuses a second active run
    queued = service.trigger_run(engine, config, trade_date=universe.sessions[-3])
    assert queued.status == "queued"
    again = service.trigger_run(engine, config, trade_date=universe.sessions[-4])
    assert again.status == "already_running"
    assert again.active_run_id == queued.run_id


def test_it_runs_rerun_same_date_new_row_supersedes_only_on_success_both_stored(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    one = execute_run(engine, _deps(universe, config), trade_date=END)
    two = execute_run(engine, _deps(universe, config), trade_date=END)
    assert one.status == two.status == "published"
    assert one.run_id and two.run_id and one.run_id != two.run_id
    old = service.get_run(engine, one.run_id)
    new = service.get_run(engine, two.run_id)
    assert old is not None
    assert new is not None
    assert old.superseded_by == new.id
    assert new.superseded_by is None
    latest = service.latest_published_run(engine)
    assert latest is not None
    assert latest.id == new.id
    current = service.published_run_for_date(engine, END)
    assert current is not None
    assert current.id == new.id
    # both runs keep their recommendations
    assert service.recommendations_for_run(engine, one.run_id)
    assert service.recommendations_for_run(engine, two.run_id)


def test_it_runs_rerun_same_date_failing_keeps_old_run_published(
    engine: Engine,
    universe: FixtureUniverse,
    config: ScoringConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one = execute_run(engine, _deps(universe, config), trade_date=END)
    assert one.status == "published"
    assert one.run_id is not None
    kept = _picks(engine, one.run_id)

    def boom(*_a: Any, **_k: Any) -> None:
        raise RuntimeError("scoring exploded")

    monkeypatch.setattr(orchestrator, "_select", boom)
    two = execute_run(engine, _deps(universe, config), trade_date=END)
    assert two.status == "failed"
    old = service.get_run(engine, one.run_id)
    assert old is not None
    assert old.superseded_by is None
    assert old.published_at is not None
    current = service.published_run_for_date(engine, END)
    assert current is not None
    assert current.id == one.run_id
    assert _picks(engine, one.run_id) == kept


def test_it_runs_summary_lists_stale_and_insufficient_history_exclusions_with_reasons(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    market = ShapedProvider(universe, short="FXK", stale="FXL")
    out = execute_run(engine, _deps(universe, config, market=market), trade_date=END)
    assert out.status == "published", out.error_detail
    assert out.run_id is not None
    view = service.get_run(engine, out.run_id)
    assert view is not None
    excluded = {e["ticker"]: e["reason"] for e in view.summary["excluded"]}
    assert excluded == {"FXK": "insufficient_history", "FXL": "stale"}
    assert view.summary["quality_counts"]["stale"] == 1
    assert view.summary["quality_counts"]["insufficient_history"] == 1
    picked = {r.symbol for r in service.recommendations_for_run(engine, out.run_id)}
    assert not picked & {"FXK", "FXL"}


def test_it_runs_daily_twice_from_clean_databases_identical_picks(
    engine: Engine, universe: FixtureUniverse, config: ScoringConfig
) -> None:
    results = []
    for _ in range(2):
        _downgrade(engine)
        db.migrate(engine)
        out = execute_run(engine, _deps(universe, config), trade_date=END)
        assert out.status == "published", out.error_detail
        assert out.run_id is not None
        picks = _picks(engine, out.run_id)
        assert picks
        results.append((picks, out.summary["config_hash"]))
    assert results[0] == results[1]
