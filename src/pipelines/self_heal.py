from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, read_json, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks


@dataclass
class HealthReport:
    name: str
    healthy: bool
    quality: dict[str, Any]
    freshness: dict[str, Any]
    reasons: list[str] = field(default_factory=list)


@dataclass
class HealResult:
    df: pd.DataFrame
    triggered: bool
    strategy: str | None
    before: HealthReport
    after: HealthReport
    events: list[dict[str, Any]] = field(default_factory=list)


def assess_health(df: pd.DataFrame, settings: Settings, name: str, freshness_path: Path) -> HealthReport:
    """Phat hien loi: Quality Gate (GX 1.x) + Freshness SLA. Healthy khi ca hai deu pass."""
    quality = run_data_quality_checks(df, settings, name)
    freshness = build_freshness_report(df, settings, freshness_path)
    reasons = [f"quality:{item}" for item in quality["failed_expectations"]]
    if not freshness["is_fresh"]:
        reasons.append(f"freshness:stale_ratio={freshness['stale_ratio']}")
    return HealthReport(name=name, healthy=not reasons, quality=quality, freshness=freshness, reasons=reasons)


def _rebuild_from_raw(settings: Settings) -> pd.DataFrame:
    return build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), now_utc())


def _refetch_from_source(settings: Settings) -> pd.DataFrame:
    return build_clean_dataframe(fetch_source_records(replace(settings, refresh_source=True)), now_utc())


def self_heal(
    df: pd.DataFrame,
    settings: Settings,
    name: str,
    freshness_path: Path,
    healed_name: str | None = None,
    healed_freshness_path: Path | None = None,
    allow_refetch: bool = True,
    before: HealthReport | None = None,
) -> HealResult:
    """Tu dong phat hien va sua du lieu hong, khong can can thiep tay.

    1. Assess: chay Quality Gate + Freshness tren `df`.
    2. Neu healthy -> giu nguyen (khong trigger).
    3. Neu unhealthy -> rollback ve raw snapshot (clean lai tu `crossref_records.json`).
    4. Neu van unhealthy va `allow_refetch` -> re-fetch tu Crossref roi clean lai.
    5. Ghi toan bo quyet dinh vao `data/results/self_heal_log.json`.
    """
    healed_name = healed_name or f"{name}_healed"
    healed_freshness_path = healed_freshness_path or freshness_path.with_name(f"{freshness_path.stem}_healed.json")

    before = before or assess_health(df, settings, name, freshness_path)
    events: list[dict[str, Any]] = [{"step": "detect", "dataset": name, "healthy": before.healthy, "reasons": before.reasons}]
    if before.healthy:
        result = HealResult(df=df, triggered=False, strategy=None, before=before, after=before, events=events)
        _write_log(settings, result)
        return result

    strategies = [("rollback_to_raw_snapshot", _rebuild_from_raw)]
    if allow_refetch:
        strategies.append(("refetch_from_source", _refetch_from_source))

    healed_df, after, strategy = df, before, None
    for strategy, action in strategies:
        try:
            healed_df = action(settings)
        except Exception as exc:  # thu chien luoc tiep theo
            events.append({"step": "repair", "strategy": strategy, "error": str(exc)})
            continue
        after = assess_health(healed_df, settings, healed_name, healed_freshness_path)
        events.append({"step": "repair", "strategy": strategy, "rows": len(healed_df), "healthy": after.healthy, "reasons": after.reasons})
        if after.healthy:
            break

    result = HealResult(df=healed_df, triggered=True, strategy=strategy, before=before, after=after, events=events)
    _write_log(settings, result)
    if not after.healthy:
        raise RuntimeError(f"Self-healing failed for '{name}': {after.reasons}")
    return result


def _write_log(settings: Settings, result: HealResult) -> None:
    path = settings.paths.self_heal_log
    history = read_json(path).get("runs", []) if path.exists() else []
    run = {
        "timestamp": now_utc().isoformat(),
        "dataset": result.before.name,
        "triggered": result.triggered,
        "strategy": result.strategy,
        "healthy_before": result.before.healthy,
        "healthy_after": result.after.healthy,
        "rows_before": result.before.quality["row_count"],
        "rows_after": result.after.quality["row_count"],
        "events": result.events,
    }
    # Giu 20 lan chay gan nhat de dashboard ve duoc lich su.
    write_json(path, {"runs": (history + [run])[-20:]})
