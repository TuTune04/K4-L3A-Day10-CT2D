from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from core.config import Settings
from core.utils import now_utc, read_json, write_text

STATES = ["baseline", "corrupted", "repaired"]
STATE_LABELS = {"baseline": "Baseline", "corrupted": "Corrupted", "repaired": "Repaired"}
METRICS = [
    ("retrieval_hit_rate", "Hit Rate", 1.0),
    ("mean_token_f1", "Token F1", 1.0),
    ("judge_accuracy", "Judge Accuracy", 1.0),
    ("mean_judge_score", "Judge Score (/5)", 5.0),
]
AGE_BINS = [(0, 90, "≤ 90"), (91, 180, "91–180"), (181, 365, "181–365"), (366, 1825, "1–5 năm"), (1826, None, "> 5 năm")]


def _load(path: Path) -> Any:
    try:
        return read_json(path) if path.exists() else None
    except Exception:
        return None


def _collect(settings: Settings) -> dict[str, Any]:
    paths = settings.paths
    q = paths.quality_dir
    return {
        "metrics": {
            "baseline": _load(paths.baseline_metrics),
            "corrupted": _load(paths.corrupted_metrics),
            "repaired": _load(paths.repaired_metrics),
        },
        "quality": {state: _load(q / f"{state}_quality_report.json") for state in STATES},
        "freshness": {
            "baseline": _load(paths.freshness_report),
            "corrupted": _load(q / "freshness_report_corrupted.json"),
            "repaired": _load(q / "freshness_report_repaired.json"),
        },
        "datasets": {
            "baseline": _load(paths.clean_json),
            "corrupted": _load(paths.corrupted_clean_json),
            "repaired": _load(paths.repaired_clean_json),
        },
        "corruption_log": _load(paths.corruption_log),
        "self_heal": _load(paths.self_heal_log),
    }


def _age_histogram(rows: list[dict[str, Any]] | None) -> list[int] | None:
    if not rows:
        return None
    counts = [0] * len(AGE_BINS)
    for row in rows:
        age = int(row.get("age_days", 0))
        for index, (low, high, _) in enumerate(AGE_BINS):
            if age >= low and (high is None or age <= high):
                counts[index] += 1
                break
    return counts


def detect_drift(data: dict[str, Any]) -> list[dict[str, str]]:
    """So sanh tung trang thai voi baseline -> danh sach canh bao (severity, message)."""
    alerts: list[dict[str, str]] = []
    base_q, base_f = data["quality"].get("baseline"), data["freshness"].get("baseline")
    for state in ("corrupted", "repaired"):
        quality, freshness = data["quality"].get(state), data["freshness"].get(state)
        label = STATE_LABELS[state]
        if quality and not quality.get("success"):
            alerts.append({"severity": "critical", "message": f"{label}: Quality Gate FAIL – {', '.join(quality.get('failed_expectations', []))}"})
        if freshness and not freshness.get("is_fresh"):
            alerts.append({"severity": "critical", "message": f"{label}: Freshness SLA vi phạm – stale ratio {freshness.get('stale_ratio')} > {freshness.get('max_stale_ratio')}"})
        if base_f and freshness and freshness.get("latest_published") != base_f.get("latest_published"):
            alerts.append({"severity": "serious", "message": f"{label}: bài mới nhất lùi từ {base_f.get('latest_published')} về {freshness.get('latest_published')} (mất dữ liệu tươi)"})
        if base_q and quality and quality.get("row_count") != base_q.get("row_count"):
            alerts.append({"severity": "warning", "message": f"{label}: số dòng thay đổi {base_q.get('row_count')} → {quality.get('row_count')}"})
    if not alerts:
        alerts.append({"severity": "good", "message": "Không phát hiện drift: mọi trạng thái khớp baseline."})
    return alerts


# ---------- rendering helpers ----------

_STATUS_ICON = {"good": "✓", "warning": "!", "serious": "▲", "critical": "✕"}


def _status(ok: bool | None, good: str = "PASS", bad: str = "FAIL") -> str:
    if ok is None:
        return '<span class="status muted">– N/A</span>'
    kind = "good" if ok else "critical"
    return f'<span class="status {kind}"><span aria-hidden="true">{_STATUS_ICON[kind]}</span> {good if ok else bad}</span>'


def _grouped_bars(categories: list[str], series: dict[str, list[float | None]], max_value: float, fmt, title: str,
                  shade_from: int | None = None) -> str:
    """SVG grouped bar chart: 1 nhom / category, 1 cot / trang thai, nhan gia tri tren dinh cot."""
    width, height = 720, 280
    left, right, top, bottom = 44, 12, 16, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / len(categories)
    names = [name for name in STATES if name in series]
    bar_w = min(28, (group_w - 24) / max(len(names), 1) - 2)
    y = lambda value: top + plot_h - (value / max_value) * plot_h  # noqa: E731

    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}" class="chart">']
    if shade_from is not None:
        x0 = left + shade_from * group_w
        parts.append(f'<rect x="{x0:.1f}" y="{top}" width="{plot_w - shade_from * group_w:.1f}" height="{plot_h}" class="stale-zone"/>')
        parts.append(f'<text x="{x0 + 6:.1f}" y="{top + 12}" class="zone-label">Vùng stale (age_days &gt; 180)</text>')
    for tick in range(5):
        value = max_value * tick / 4
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y(value):.1f}" y2="{y(value):.1f}" class="grid"/>')
        parts.append(f'<text x="{left - 6}" y="{y(value) + 4:.1f}" class="tick" text-anchor="end">{fmt(value, axis=True)}</text>')
    parts.append(f'<line x1="{left}" x2="{width - right}" y1="{top + plot_h}" y2="{top + plot_h}" class="axis"/>')

    for gi, category in enumerate(categories):
        gx = left + gi * group_w + (group_w - len(names) * (bar_w + 2)) / 2
        for si, name in enumerate(names):
            value = series[name][gi]
            if value is None:
                continue
            x = gx + si * (bar_w + 2)
            bar_h = max((value / max_value) * plot_h, 0)
            y0 = top + plot_h - bar_h
            radius = min(4, bar_w / 2, bar_h)
            # Cot bo tron 4px o dau du lieu, day phang tai baseline.
            path = (f"M{x:.1f},{top + plot_h} V{y0 + radius:.1f} Q{x:.1f},{y0:.1f} {x + radius:.1f},{y0:.1f} "
                    f"H{x + bar_w - radius:.1f} Q{x + bar_w:.1f},{y0:.1f} {x + bar_w:.1f},{y0 + radius:.1f} V{top + plot_h} Z") if bar_h > 0 else ""
            tip = f"{STATE_LABELS[name]} · {category}: {fmt(value)}"
            path_el = f'<path d="{path}" class="s-{name}"/>' if path else ""
            parts.append(f'<g class="mark" tabindex="0"><title>{escape(tip)}</title>'
                         f'<rect x="{x - 1:.1f}" y="{top}" width="{bar_w + 2:.1f}" height="{plot_h}" class="hit"/>'
                         f'{path_el}'
                         f'<text x="{x + bar_w / 2:.1f}" y="{y0 - 4:.1f}" class="value" text-anchor="middle">{fmt(value)}</text></g>')
        parts.append(f'<text x="{left + gi * group_w + group_w / 2:.1f}" y="{height - bottom + 18}" class="cat" text-anchor="middle">{escape(category)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _legend(names: list[str]) -> str:
    items = "".join(f'<span class="key"><span class="swatch s-{name}"></span>{STATE_LABELS[name]}</span>' for name in names)
    return f'<div class="legend">{items}</div>'


def render_dashboard(data: dict[str, Any], generated_at: str) -> str:
    metrics, quality, freshness = data["metrics"], data["quality"], data["freshness"]
    available = [state for state in STATES if metrics.get(state) or quality.get(state)]

    # KPI tiles theo trang thai.
    tiles = []
    for state in available:
        q, f = quality.get(state) or {}, freshness.get(state) or {}
        tiles.append(f"""<div class="tile">
  <div class="tile-head"><span class="swatch s-{state}"></span>{STATE_LABELS[state]}</div>
  <div class="tile-row"><span>Quality Gate</span>{_status(q.get('success') if q else None)}</div>
  <div class="tile-row"><span>Freshness SLA</span>{_status(f.get('is_fresh') if f else None, 'FRESH', 'STALE')}</div>
  <div class="tile-row"><span>Số dòng</span><b>{q.get('row_count', '–')}</b></div>
  <div class="tile-row"><span>Stale ratio</span><b>{f.get('stale_ratio', '–')}</b></div>
  <div class="tile-row"><span>Bài mới nhất</span><b>{f.get('latest_published', '–')}</b></div>
</div>""")

    # Metric chart (chuan hoa judge score ve 0-1).
    metric_names = [state for state in STATES if metrics.get(state)]
    metric_series = {state: [metrics[state][key] / scale for key, _, scale in METRICS] for state in metric_names}
    pct = lambda value, axis=False: f"{value:.0%}" if axis else f"{value:.2f}"  # noqa: E731
    metric_chart = _grouped_bars([label for _, label, _ in METRICS], metric_series, 1.0, pct, "RAG metrics by state") if metric_names else "<p class='muted'>Chưa có metrics.</p>"

    metric_rows = "".join(
        f"<tr><td>{label}</td>" + "".join(f"<td class='num'>{metrics[state][key]:.4f}</td>" if metrics.get(state) else "<td>–</td>" for state in STATES) + "</tr>"
        for key, label, _ in METRICS
    )

    # Age distribution (drift ve thoi gian).
    histograms = {state: _age_histogram(data["datasets"].get(state)) for state in STATES}
    histograms = {state: counts for state, counts in histograms.items() if counts}
    count_fmt = lambda value, axis=False: f"{value:.0f}"  # noqa: E731
    age_max = max([max(counts) for counts in histograms.values()] + [1])
    age_max = age_max + (4 - age_max % 4) % 4  # tick tron
    age_chart = _grouped_bars([label for _, _, label in AGE_BINS], histograms, age_max, count_fmt, "Age distribution", shade_from=2) if histograms else ""

    # Expectation matrix.
    expectation_keys: list[tuple[str, str]] = []
    for state in STATES:
        for item in (quality.get(state) or {}).get("results", []):
            key = (item["expectation"], item.get("column") or "(table)")
            if key not in expectation_keys:
                expectation_keys.append(key)
    lookup = {state: {(i["expectation"], i.get("column") or "(table)"): i for i in (quality.get(state) or {}).get("results", [])} for state in STATES}
    expectation_rows = "".join(
        f"<tr><td><code>{escape(exp)}</code></td><td>{escape(col)}</td>"
        + "".join(f"<td>{_status(lookup[state][(exp, col)]['success']) if (exp, col) in lookup[state] else '–'}</td>" for state in STATES)
        + "</tr>"
        for exp, col in expectation_keys
    )

    alerts = "".join(
        f'<li class="alert {a["severity"]}"><span class="status {a["severity"]}" aria-hidden="true">{_STATUS_ICON[a["severity"]]}</span> {escape(a["message"])}</li>'
        for a in detect_drift(data)
    )

    corruption_rows = "".join(
        f"<tr><td><code>{escape(e['corruption'])}</code></td><td class='num'>{e['affected_rows']}</td><td>{escape(e['description'])}</td></tr>"
        for e in (data["corruption_log"] or {}).get("corruptions", [])
    )
    heal_rows = "".join(
        f"<tr><td>{escape(run['timestamp'][:19].replace('T', ' '))}</td><td>{escape(run['dataset'])}</td>"
        f"<td>{'Có' if run['triggered'] else 'Không'}</td><td>{escape(str(run['strategy'] or '–'))}</td>"
        f"<td class='num'>{run['rows_before']} → {run['rows_after']}</td><td>{_status(run['healthy_after'], 'HEALTHY', 'UNHEALTHY')}</td></tr>"
        for run in reversed((data["self_heal"] or {}).get("runs", [])[-10:])
    )

    return f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data Observability Dashboard</title>
<style>
:root {{
  color-scheme: light;
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
  --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
  --s-baseline: #2a78d6; --s-corrupted: #eb6834; --s-repaired: #1baf7a;
  --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
  --zone: rgba(208,59,59,0.06);
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) {{
    color-scheme: dark;
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
    --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
    --s-baseline: #3987e5; --s-corrupted: #d95926; --s-repaired: #199e70; --zone: rgba(208,59,59,0.12);
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
  --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
  --s-baseline: #3987e5; --s-corrupted: #d95926; --s-repaired: #199e70; --zone: rgba(208,59,59,0.12);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--page); color: var(--ink); font: 14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }}
h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 16px; margin: 0 0 12px; }}
.sub {{ color: var(--ink-2); margin: 0 0 20px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 16px; overflow-x: auto; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px; }}
.tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px; }}
.tile-head {{ font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }}
.tile-row {{ display: flex; justify-content: space-between; padding: 3px 0; color: var(--ink-2); }}
.tile-row b {{ color: var(--ink); font-weight: 600; }}
.swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
.swatch.s-baseline {{ background: var(--s-baseline); }} .swatch.s-corrupted {{ background: var(--s-corrupted); }} .swatch.s-repaired {{ background: var(--s-repaired); }}
.legend {{ display: flex; gap: 16px; margin-bottom: 8px; color: var(--ink-2); flex-wrap: wrap; }}
.key {{ display: inline-flex; align-items: center; gap: 6px; }}
.chart {{ width: 100%; min-width: 520px; height: auto; display: block; }}
.chart .grid {{ stroke: var(--grid); stroke-width: 1; }} .chart .axis {{ stroke: var(--axis); stroke-width: 1; }}
.chart .tick, .chart .zone-label {{ fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }}
.chart .cat {{ fill: var(--ink-2); font-size: 12px; }} .chart .value {{ fill: var(--ink-2); font-size: 10px; opacity: 0; }}
.chart .stale-zone {{ fill: var(--zone); }}
.chart .hit {{ fill: transparent; }}
.chart .s-baseline {{ fill: var(--s-baseline); }} .chart .s-corrupted {{ fill: var(--s-corrupted); }} .chart .s-repaired {{ fill: var(--s-repaired); }}
.chart .mark:hover .value, .chart .mark:focus .value {{ opacity: 1; }}
.chart .mark:hover path, .chart .mark:focus path {{ opacity: .85; }}
.chart .mark:focus {{ outline: none; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--grid); vertical-align: top; }}
th {{ color: var(--ink-2); font-weight: 600; }} td.num {{ font-variant-numeric: tabular-nums; }}
code {{ font-size: 12px; }}
.status {{ font-weight: 600; white-space: nowrap; }}
.status.good {{ color: var(--good); }} .status.critical {{ color: var(--critical); }}
.status.serious {{ color: var(--serious); }} .status.warning {{ color: var(--warning); }} .status.muted, .muted {{ color: var(--muted); }}
ul.alerts {{ list-style: none; margin: 0; padding: 0; }}
li.alert {{ padding: 6px 0; border-bottom: 1px solid var(--grid); }}
.two {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }}
@media (max-width: 520px) {{ .two {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<main>
<h1>Data Observability Dashboard</h1>
<p class="sub">Crossref → Clean → GX 1.x Quality Gate → ChromaDB → RAG · cập nhật {escape(generated_at)} (UTC) · sinh tự động bởi <code>script/build_dashboard.py</code></p>

<div class="tiles">{''.join(tiles)}</div>

<div class="card"><h2>Cảnh báo drift &amp; chất lượng</h2><ul class="alerts">{alerts}</ul></div>

<div class="card">
  <h2>RAG metrics theo trạng thái</h2>
  {_legend(metric_names)}
  {metric_chart}
  <table><thead><tr><th>Metric</th><th>Baseline</th><th>Corrupted</th><th>Repaired</th></tr></thead><tbody>{metric_rows}</tbody></table>
</div>

<div class="card">
  <h2>Phân bố độ tuổi bài báo (age_days)</h2>
  {_legend(list(histograms))}
  {age_chart}
</div>

<div class="card">
  <h2>Great Expectations 1.x – kết quả từng expectation</h2>
  <table><thead><tr><th>Expectation</th><th>Cột</th><th>Baseline</th><th>Corrupted</th><th>Repaired</th></tr></thead><tbody>{expectation_rows}</tbody></table>
</div>

<div>
  <div class="card"><h2>Corruption đã tiêm</h2>
    <table><thead><tr><th>Loại</th><th>Dòng</th><th>Mô tả</th></tr></thead><tbody>{corruption_rows or "<tr><td colspan='3' class='muted'>Chưa chạy corruption flow.</td></tr>"}</tbody></table></div>
  <div class="card"><h2>Self-healing log</h2>
    <table><thead><tr><th>Thời điểm</th><th>Dataset</th><th>Tự sửa</th><th>Chiến lược</th><th>Dòng</th><th>Sau repair</th></tr></thead><tbody>{heal_rows or "<tr><td colspan='6' class='muted'>Chưa có lần self-heal nào.</td></tr>"}</tbody></table></div>
</div>
</main>
</body>
</html>
"""


def build_dashboard(settings: Settings, output_path: Path | None = None) -> Path:
    """Doc artifact trong data/ va sinh dashboard HTML tu chua (khong can server/thu vien ngoai)."""
    output_path = output_path or settings.paths.dashboard_html
    write_text(output_path, render_dashboard(_collect(settings), now_utc().strftime("%Y-%m-%d %H:%M")))
    return output_path
