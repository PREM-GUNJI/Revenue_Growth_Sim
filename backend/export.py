"""PowerPoint and HTML export of a workspace. Every figure comes from `evaluate_batch`; nothing is estimated.

A REFUSED scenario is named with the engine's refusal reasons and no numbers at all. Figures are the focal
brand's (Aurora's) weekly totals in INR, taken from the engine's `focal` result, and percentages are simple
ratios of those totals against the first scenario (the baseline), the same as the app's comparison.

The PowerPoint and HTML brief share `executive_narrative` so the boardroom story matches the in-app
Executive Brief screen.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

from backend.assumptions.assumptions import ASSUMPTIONS
from backend.engine.batch import ENGINE_VERSION, _data_hash, evaluate_batch
from backend.engine.scenario import Scenario
from backend.model.backtest import spec_hash
from backend.model.spec import build_param_draws

INK = RGBColor(0x0A, 0x10, 0x34)
GREY = RGBColor(0x52, 0x52, 0x52)
MUTED = RGBColor(0x73, 0x73, 0x73)
RED = RGBColor(0xDC, 0x26, 0x26)
K, SEED = 200, 42
DEFAULT_GUARDRAIL_PCT = 5.0
SYNTHETIC = "All data in this simulator is synthetic. Figures are modelled, not observed."


class ExportError(ValueError):
    """The saved scenarios cannot be exported (empty, or not valid scenarios)."""


def _pct(value: float, base: float) -> float | None:
    return (value / base - 1) * 100 if base else None


def _signed(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1f}%"


def _money(value: float | None, *, signed: bool = False) -> str:
    """Whole currency units for the active market (INR uses Indian digit grouping)."""
    from backend.markets.context import get_active_market
    from backend.markets.packs import load_market
    from backend.markets.context import DEFAULT_MARKET_ID

    if value is None:
        return "n/a"
    market = get_active_market() or load_market(DEFAULT_MARKET_ID)
    code, symbol = market.currency.code, market.currency.symbol
    amount = int(round(abs(value)))
    if code == "INR":
        digits = str(amount)
        if len(digits) > 3:
            head, tail = digits[:-3], digits[-3:]
            groups = []
            while len(head) > 2:
                groups.insert(0, head[-2:])
                head = head[:-2]
            digits = ",".join(([head] if head else []) + groups + [tail])
        formatted = digits
    else:
        formatted = f"{amount:,}"
    sign = "-" if round(value) < 0 else ("+" if signed and round(value) > 0 else "")
    return f"{sign}{symbol}{formatted}"


def _inr(value: float | None, *, signed: bool = False) -> str:
    """Backward-compatible alias; prefers the active market's currency."""
    return _money(value, signed=signed)


def _currency_code() -> str:
    from backend.markets.context import DEFAULT_MARKET_ID, get_active_market
    from backend.markets.packs import load_market

    return (get_active_market() or load_market(DEFAULT_MARKET_ID)).currency.code


def evaluate(scenario_dicts: list[dict[str, Any]]) -> tuple[list[Scenario], list[dict[str, Any]]]:
    if not scenario_dicts:
        raise ExportError("This workspace has no scenarios to export.")
    try:
        scenarios = [Scenario.model_validate({k: v for k, v in item.items() if k != "source"}) for item in scenario_dicts]
    except Exception as exc:
        raise ExportError("Some saved scenarios are not valid and cannot be evaluated.") from exc
    results = [asdict(r) for r in evaluate_batch(scenarios, build_param_draws(k=K, seed=SEED))]
    return scenarios, results


def summary_rows(scenarios: list[Scenario], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    base = results[0]
    base_ok = base["status"] != "REFUSED"
    rows = []
    for index, (scenario, result) in enumerate(zip(scenarios, results, strict=True)):
        row: dict[str, Any] = {"name": scenario.name, "status": result["status"], "scenario_id": result["scenario_id"],
                               "result_hash": result["result_hash"], "baseline": index == 0,
                               "reasons": [r["message"] for r in result["refusal_reasons"]]}
        if result["status"] == "REFUSED" or not base_ok:
            row.update(units=None, revenue=None, gp=None, gp_change=None,
                       volume_pct=None, revenue_pct=None, gp_pct=None)  # refused: no numbers, ever
        else:
            f, b = result["focal"], base["focal"]
            row.update(units=f["volume"]["value"], revenue=f["gsv"]["value"], gp=f["gp"]["value"],
                       gp_change=f["gp"]["value"] - b["gp"]["value"],
                       volume_pct=_pct(f["volume"]["value"], b["volume"]["value"]),
                       revenue_pct=_pct(f["gsv"]["value"], b["gsv"]["value"]),
                       gp_pct=_pct(f["gp"]["value"], b["gp"]["value"]))
        rows.append(row)
    return rows


def executive_narrative(rows: list[dict[str, Any]], guardrail_pct: float = DEFAULT_GUARDRAIL_PCT) -> dict[str, Any]:
    """Sparse boardroom story shared by the PPT, HTML brief, and (by design) the Executive Brief UI.

    Recommendation = best gross-profit % change among non-baseline supported options that keep volume
    loss within the guardrail and beat baseline by more than 0.05 pp. Losers stay in the top-3 glance.
    Refused options are named only — never with numbers.
    """
    baseline = next((r for r in rows if r["baseline"]), None)
    supported = [r for r in rows if not r["baseline"] and r["status"] != "REFUSED" and r["gp_pct"] is not None]
    eligible = [r for r in supported if r["volume_pct"] is not None and r["volume_pct"] >= -guardrail_pct]
    ranked = sorted(eligible, key=lambda r: -(r["gp_pct"] if r["gp_pct"] is not None else float("-inf")))
    recommendation = ranked[0] if ranked and ranked[0]["gp_pct"] is not None and ranked[0]["gp_pct"] > 0.05 else None
    options = sorted(supported, key=lambda r: -(r["gp_pct"] if r["gp_pct"] is not None else float("-inf")))[:3]
    refused = [r for r in rows if r["status"] == "REFUSED"]
    return {
        "baseline": baseline,
        "recommendation": recommendation,
        "hold_baseline": recommendation is None,
        "options": options,
        "refused": refused,
        "guardrail_pct": guardrail_pct,
    }


def _text(slide, left, top, width, height, text, size=14, bold=False, color=INK):
    frame = slide.shapes.add_textbox(left, top, width, height).text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    run = paragraph.add_run()
    run.text, run.font.size, run.font.bold, run.font.color.rgb = text, Pt(size), bold, color
    return frame


def _add_note(frame, text, size=11, color=GREY):
    paragraph = frame.add_paragraph()
    run = paragraph.add_run()
    run.text, run.font.size, run.font.color.rgb = text, Pt(size), color


def build_deck(workspace_name: str, scenarios: list[Scenario], results: list[dict[str, Any]], author: str) -> bytes:
    """Four-slide executive deck: cover, recommendation, options compared, caveats."""
    rows = summary_rows(scenarios, results)
    story = executive_narrative(rows)
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    blank = deck.slide_layouts[6]
    width = deck.slide_width - Inches(1.2)
    today = datetime.now(UTC)

    cover = deck.slides.add_slide(blank)
    _text(cover, Inches(0.6), Inches(1.8), width, Inches(0.5), f"Decision brief · Aurora · weekly {_currency_code()}", 16, color=MUTED)
    _text(cover, Inches(0.6), Inches(2.4), width, Inches(1.4), workspace_name, 40, True)
    frame = _text(cover, Inches(0.6), Inches(4.2), width, Inches(1.6),
                  f"Prepared by {author} on {today:%d %b %Y}", 14, color=GREY)
    _add_note(frame, SYNTHETIC, 13, RED)

    rec_slide = deck.slides.add_slide(blank)
    _text(rec_slide, Inches(0.6), Inches(0.45), width, Inches(0.4), "Recommendation", 14, color=MUTED)
    winner = story["recommendation"]
    if winner:
        _text(rec_slide, Inches(0.6), Inches(1.0), width, Inches(0.9), winner["name"] or "Top option", 32, True)
        _text(rec_slide, Inches(0.6), Inches(2.1), width, Inches(0.9),
              f"{_inr(winner['gp_change'], signed=True)} gross profit a week", 36, True)
        _text(rec_slide, Inches(0.6), Inches(3.2), width, Inches(0.6),
              f"Volume {_signed(winner['volume_pct'])} · gross profit {_signed(winner['gp_pct'])}", 18, color=GREY)
        _text(rec_slide, Inches(0.6), Inches(4.1), width, Inches(1.0),
              f"Volume loss kept within {story['guardrail_pct']:.0f}%. Modeled by the deterministic engine for Aurora only.",
              14, color=GREY)
    else:
        _text(rec_slide, Inches(0.6), Inches(1.0), width, Inches(1.0), "Hold the baseline", 32, True)
        _text(rec_slide, Inches(0.6), Inches(2.3), width, Inches(1.2),
              f"No supported option beats baseline on gross profit while keeping volume loss within {story['guardrail_pct']:.0f}%.",
              18, color=GREY)

    options_slide = deck.slides.add_slide(blank)
    _text(options_slide, Inches(0.6), Inches(0.45), width, Inches(0.4), "Options compared", 14, color=MUTED)
    _text(options_slide, Inches(0.6), Inches(0.85), width, Inches(0.5), "Aurora weekly change vs baseline", 26, True)
    chartable = list(story["options"])
    if story["baseline"] and story["baseline"]["gp_pct"] is not None:
        # Baseline as a zero reference is not charted; only non-baseline options.
        pass
    if chartable:
        data = CategoryChartData()
        data.categories = [r["name"] for r in chartable]
        data.add_series("Gross profit %", [round(r["gp_pct"], 2) for r in chartable])
        chart = options_slide.shapes.add_chart(
            XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.5), Inches(7.2), Inches(5.2), data
        ).chart
        chart.has_legend = False
        chart.plots[0].has_data_labels = True
        chart.plots[0].data_labels.number_format = '0.0"%"'
        chart.plots[0].data_labels.number_format_is_linked = False
        frame = _text(options_slide, Inches(8.2), Inches(1.5), Inches(4.4), Inches(5.2), "At a glance", 14, True)
        for row in chartable:
            loser = (row["gp_pct"] or 0) < 0
            _add_note(frame, row["name"], 13, INK)
            _add_note(
                frame,
                f"  GP {_signed(row['gp_pct'])} · vol {_signed(row['volume_pct'])}"
                + (" · worse than baseline" if loser else ""),
                12,
                GREY,
            )
    else:
        _text(options_slide, Inches(0.6), Inches(1.6), width, Inches(1.0),
              "No supported options to compare yet.", 18, color=GREY)

    if story["refused"]:
        _text(options_slide, Inches(0.6), Inches(6.6), width, Inches(0.5),
              f"{len(story['refused'])} request(s) refused — outside observed data; no figures shown.", 12, color=RED)

    caveats = deck.slides.add_slide(blank)
    _text(caveats, Inches(0.6), Inches(0.45), width, Inches(0.4), "Caveats", 14, color=MUTED)
    _text(caveats, Inches(0.6), Inches(0.9), width, Inches(0.5), "What this brief does and does not claim", 26, True)
    frame = _text(caveats, Inches(0.6), Inches(1.7), width, Inches(4.8), SYNTHETIC, 16, color=RED)
    _add_note(frame, "Modeled results are engine outputs for supported scenarios, not forecasts.", 14, GREY)
    _add_note(
        frame,
        f"Volume guardrail used for the recommendation: {story['guardrail_pct']:.0f}% loss vs baseline.",
        14,
        GREY,
    )
    if story["refused"]:
        _add_note(frame, "Refused (no numbers):", 14, INK)
        for row in story["refused"]:
            _add_note(frame, f"  {row['name']}", 13, INK)
            for reason in row["reasons"][:2]:
                _add_note(frame, f"    {reason}", 12, GREY)
    _add_note(frame, "", 10, GREY)
    _add_note(
        frame,
        f"Reproduce: engine {ENGINE_VERSION}, data {_data_hash()[:12]}, model {spec_hash()[:12]}, "
        f"assumptions {assumptions_hash()[:12]}, k={K}, seed={SEED}",
        11,
        MUTED,
    )
    for row in rows:
        _add_note(frame, f"{row['name']}: {row['scenario_id'][:16]} / {row['result_hash'][:16]}", 10, MUTED)

    buffer = io.BytesIO()
    deck.save(buffer)
    return buffer.getvalue()


def assumptions_hash() -> str:
    """Fingerprint of every registry value, so a saved set records which assumptions produced it."""
    body = json.dumps({a.id: a.value for a in ASSUMPTIONS.values()}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def build_brief(workspace_name: str, scenarios: list[Scenario], results: list[dict[str, Any]],
                author: str, trace_id: str | None = None) -> str:
    """Sparse one-page brief aligned with the Executive Brief screen and PPT narrative."""
    e = html.escape
    rows = summary_rows(scenarios, results)
    story = executive_narrative(rows)
    winner = story["recommendation"]
    if winner:
        rec_html = (
            f'<section class="hero"><p class="eyebrow">Recommended</p>'
            f'<h2>{e(winner["name"] or "Top option")}</h2>'
            f'<p class="metric">{e(_inr(winner["gp_change"], signed=True))} '
            f'<span>gross profit a week</span></p>'
            f'<p class="sub">Volume {e(_signed(winner["volume_pct"]))} · '
            f'gross profit {e(_signed(winner["gp_pct"]))} · '
            f'volume loss within {story["guardrail_pct"]:.0f}%</p></section>'
        )
    else:
        rec_html = (
            f'<section class="hero"><p class="eyebrow">Recommended</p>'
            f'<h2>Hold the baseline</h2>'
            f'<p class="sub">No supported option beats baseline on gross profit while keeping '
            f'volume loss within {story["guardrail_pct"]:.0f}%.</p></section>'
        )
    option_rows = []
    for r in story["options"]:
        tag = "worse than baseline" if (r["gp_pct"] or 0) < 0 else "Modeled"
        option_rows.append(
            f'<tr><td>{e(r["name"] or "Scenario")}</td><td>{tag}</td>'
            f'<td>{e(_signed(r["volume_pct"]))}</td><td>{e(_signed(r["gp_pct"]))}</td>'
            f'<td>{e(_inr(r["gp_change"], signed=True))}</td></tr>'
        )
    refused_block = ""
    if story["refused"]:
        items = "".join(
            f'<li><strong>{e(r["name"])}</strong> — {e("; ".join(r["reasons"]) or "outside observed data")}</li>'
            for r in story["refused"]
        )
        refused_block = f'<p class="bad">{len(story["refused"])} refused (no figures)</p><ul class="refused">{items}</ul>'
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{e(workspace_name)} decision brief</title>
<style>
body{{font:16px/1.45 system-ui,sans-serif;max-width:720px;margin:2.5rem auto;padding:0 1.25rem;color:#0a1034}}
h1{{font-size:1.75rem;margin:0 0 .25rem}}h2{{font-size:1.5rem;margin:.25rem 0}}
.meta,.eyebrow{{color:#737373;font-size:.8rem;text-transform:uppercase;letter-spacing:.06em}}
.hero{{background:#0a1034;color:#fff;border-radius:12px;padding:1.5rem 1.75rem;margin:1.25rem 0}}
.hero .eyebrow{{color:rgba(255,255,255,.55)}}
.metric{{font-size:2.25rem;font-weight:700;margin:.5rem 0;letter-spacing:-.02em}}
.metric span{{font-size:1rem;font-weight:500;opacity:.75}}
.sub{{opacity:.8;margin:0}}
table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.95rem}}
td,th{{border-bottom:1px solid #e5e5e5;padding:.55rem .4rem;text-align:left}}
.bad{{color:#dc2626}}ul.refused{{padding-left:1.1rem;color:#525252;font-size:.9rem}}
.foot{{color:#737373;font-size:.75rem;margin-top:2rem}}
@media print{{body{{margin:0;max-width:none}}}}
</style>
<p class="eyebrow">Decision brief · Aurora · weekly {_currency_code()}</p>
<h1>{e(workspace_name)}</h1>
<p class="meta">{e(author)} · {datetime.now(UTC):%Y-%m-%d} · Modeled, not a forecast</p>
{rec_html}
<h2>Options at a glance</h2>
<table><tr><th>Option</th><th></th><th>Volume</th><th>Gross profit</th><th>GP change</th></tr>
{"".join(option_rows) or "<tr><td colspan='5'>No supported options yet.</td></tr>"}</table>
{refused_block}
<p>{e(SYNTHETIC)}</p>
<p class="foot">Reproduce: engine {e(ENGINE_VERSION)}, data {_data_hash()[:12]}, model {spec_hash()[:12]},
assumptions {assumptions_hash()[:12]}, k={K}, seed={SEED}
{", agent trace " + e(trace_id) if trace_id else ""}.</p></html>"""
