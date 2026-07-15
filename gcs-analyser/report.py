"""
PDF report builder for GCS Analyser (reportlab only — no matplotlib).
Renders: cover + grand totals, an all-buckets summary table, charts
(cost by bucket, size by storage class), then a per-bucket section with
details, lifecycle/versioning, folder breakdown, top files, and class split.
"""

from __future__ import annotations

from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.legends import Legend

# ─── palette ──────────────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#1a2b4a")
BLUE   = colors.HexColor("#2563eb")
LIGHT  = colors.HexColor("#eef2ff")
GREEN  = colors.HexColor("#16a34a")
GREY   = colors.HexColor("#64748b")
ZEBRA  = colors.HexColor("#f5f7fb")

# ─── monochrome ramp ──────────────────────────────────────────────────────────
# Single-hue (navy → pale blue) ramp: clearer than rainbow, colour-blind safe,
# prints fine in greyscale. Categories are shaded dark→light by magnitude.
_RAMP_DARK  = (0x12, 0x2b, 0x4f)   # deep navy
_RAMP_LIGHT = (0xc7, 0xdd, 0xf5)   # pale blue


def _mono_ramp(n: int):
    """n colours interpolated dark→light along one hue."""
    if n <= 1:
        return [colors.HexColor("#1f4e8c")]
    out = []
    for i in range(n):
        t = i / (n - 1)
        r = round(_RAMP_DARK[0] + (_RAMP_LIGHT[0] - _RAMP_DARK[0]) * t)
        g = round(_RAMP_DARK[1] + (_RAMP_LIGHT[1] - _RAMP_DARK[1]) * t)
        b = round(_RAMP_DARK[2] + (_RAMP_LIGHT[2] - _RAMP_DARK[2]) * t)
        out.append(colors.Color(r / 255, g / 255, b / 255))
    return out


def _text_on(color):
    """Black or white label depending on background luminance (readability)."""
    lum = 0.299 * color.red + 0.587 * color.green + 0.114 * color.blue
    return colors.black if lum > 0.6 else colors.white

_styles = getSampleStyleSheet()
H1   = ParagraphStyle("H1", parent=_styles["Title"], textColor=NAVY, fontSize=24)
H2   = ParagraphStyle("H2", parent=_styles["Heading2"], textColor=NAVY, fontSize=14,
                      spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("Body", parent=_styles["Normal"], fontSize=9, textColor=GREY)
CELL = ParagraphStyle("Cell", parent=_styles["Normal"], fontSize=7.5, leading=9)
KPI  = ParagraphStyle("KPI", parent=_styles["Normal"], fontSize=9, textColor=GREY,
                      alignment=1)
KPIV = ParagraphStyle("KPIV", parent=_styles["Title"], fontSize=20, textColor=BLUE,
                      alignment=1, spaceAfter=0)


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _truncate(s: str, n: int = 64) -> str:
    return s if len(s) <= n else "…" + s[-(n - 1):]


def _header_style(ncols: int) -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe1ea")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ])


def _kpi_box(label: str, value: str) -> Table:
    t = Table([[Paragraph(value, KPIV)], [Paragraph(label, KPI)]], colWidths=[4.3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _cost_by_bucket_chart(reports) -> Drawing:
    """Horizontal bars (top 10 by cost) — full bucket names stay readable,
    single-hue fill shaded by rank, value labels at the bar end."""
    data = [(r.name, r.cost_month) for r in reports if not r.error]
    data = sorted(data, key=lambda kv: kv[1], reverse=True)[:10]
    n = len(data) or 1
    row_h = 16
    d = Drawing(450, max(120, n * row_h + 46))

    chart = HorizontalBarChart()
    chart.x, chart.y = 140, 28
    chart.width, chart.height = 240, n * row_h
    # bars drawn bottom→top, so reverse to show the largest at the top
    rows = list(reversed(data))
    chart.data = [[v for _, v in rows]] or [[0]]
    chart.categoryAxis.categoryNames = [_truncate(name, 26) for name, _ in rows] or [""]
    chart.categoryAxis.labels.fontSize = 7.5
    chart.categoryAxis.labels.boxAnchor = "e"
    chart.categoryAxis.labels.dx = -4
    chart.categoryAxis.strokeColor = colors.HexColor("#cbd5e1")
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 7
    chart.valueAxis.strokeColor = colors.HexColor("#cbd5e1")
    chart.valueAxis.gridStrokeColor = colors.HexColor("#eef2f7")
    chart.valueAxis.visibleGrid = True
    chart.barWidth = row_h * 0.62
    chart.groupSpacing = row_h * 0.38
    # monochrome: darkest = most expensive (top). rows is ascending, so reverse ramp.
    ramp = list(reversed(_mono_ramp(n)))
    chart.bars.strokeColor = None
    for i in range(n):
        chart.bars[(0, i)].fillColor = ramp[i]
    # value labels ($) at the end of each bar
    chart.barLabels.fontSize = 7
    chart.barLabels.boxAnchor = "w"
    chart.barLabelFormat = lambda v: _money(v)
    chart.barLabels.dx = 3
    chart.barLabels.fillColor = NAVY
    d.add(chart)
    return d


def _size_by_class_chart(class_totals: dict) -> Drawing:
    """Monochrome pie, slices ordered & shaded by size; legend carries the
    class name + percentage so nothing overlaps on the wedges."""
    items = sorted(((k, v) for k, v in class_totals.items() if v > 0),
                   key=lambda kv: kv[1], reverse=True)
    total = sum(v for _, v in items) or 1
    ramp = _mono_ramp(len(items))

    d = Drawing(330, 200)
    pie = Pie()
    pie.x, pie.y, pie.width, pie.height = 10, 24, 150, 150
    pie.data = [v for _, v in items] or [1]
    pie.labels = None                      # no on-wedge labels → no collisions
    pie.slices.strokeColor = colors.white
    pie.slices.strokeWidth = 1
    pie.sideLabels = False
    for i in range(len(items)):
        pie.slices[i].fillColor = ramp[i]
    d.add(pie)

    leg = Legend()
    leg.x, leg.y = 200, 168
    leg.fontSize = 8.5
    leg.dxTextSpace = 6
    leg.deltay = 15
    leg.columnMaximum = len(items) or 1
    leg.colorNamePairs = [
        (ramp[i], f"{k}  —  {v / total * 100:.1f}%")
        for i, (k, v) in enumerate(items)
    ] or [(GREY, "—")]
    d.add(leg)
    return d


def build_pdf(reports, out_path: str, project: str, prefix_depth: int, format_size):
    doc = SimpleDocTemplate(out_path, pagesize=landscape(A4),
                            leftMargin=1.2 * cm, rightMargin=1.2 * cm,
                            topMargin=1.2 * cm, bottomMargin=1.2 * cm,
                            title=f"GCS Report — {project}")
    ok = [r for r in reports if not r.error]
    story = []

    # ── Cover / grand totals ─────────────────────────────────────────────
    story.append(Paragraph("☁️ Google Cloud Storage — Analysis Report", H1))
    story.append(Paragraph(
        f"Project <b>{project}</b> · generated "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · "
        f"{len(ok)} bucket(s) scanned", BODY))
    story.append(Spacer(1, 10))

    g_size = sum(r.total_size for r in ok)
    g_obj  = sum(r.object_count for r in ok)
    g_cost = sum(r.cost_month for r in ok)
    g_noncur = sum(r.noncurrent_size for r in ok)
    kpis = Table([[
        _kpi_box("Buckets", str(len(ok))),
        _kpi_box("Objects", f"{g_obj:,}"),
        _kpi_box("Total size", format_size(g_size)),
        _kpi_box("Est. cost / month", _money(g_cost)),
        _kpi_box("Noncurrent (versions)", format_size(g_noncur)),
    ]], hAlign="LEFT")
    kpis.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    story.append(kpis)
    story.append(Spacer(1, 6))

    # ── Charts ───────────────────────────────────────────────────────────
    class_totals: dict[str, int] = {}
    for r in ok:
        for sc, v in r.class_breakdown.items():
            class_totals[sc] = class_totals.get(sc, 0) + v["size"]
    story.append(Paragraph("Estimated monthly cost by bucket (top 10) &nbsp;·&nbsp; "
                           "Total size by storage class", H2))
    side = Table([[_cost_by_bucket_chart(ok), _size_by_class_chart(class_totals)]],
                 colWidths=[15.5 * cm, 11.3 * cm])
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(side)

    # ── All-buckets summary table ────────────────────────────────────────
    story.append(Paragraph("All buckets — summary", H2))
    head = ["Bucket", "Location", "Type", "Class", "Versioning",
            "Objects", "Live", "Noncurrent", "Total size", "Cost/mo"]
    rows = [head]
    for r in ok:
        rows.append([
            Paragraph(_truncate(r.name, 34), CELL), r.location, r.location_type,
            r.default_storage_class, "ON" if r.versioning_enabled else "off",
            f"{r.object_count:,}", f"{r.live_count:,}", f"{r.noncurrent_count:,}",
            format_size(r.total_size), _money(r.cost_month),
        ])
    rows.append(["TOTAL", "", "", "", "", f"{g_obj:,}",
                 f"{sum(r.live_count for r in ok):,}",
                 f"{sum(r.noncurrent_count for r in ok):,}",
                 format_size(g_size), _money(g_cost)])
    t = Table(rows, repeatRows=1, hAlign="LEFT",
              colWidths=[4.6*cm, 2.4*cm, 1.7*cm, 1.7*cm, 1.6*cm,
                         1.7*cm, 1.5*cm, 1.9*cm, 2.2*cm, 2.0*cm])
    st = _header_style(len(head))
    st.add("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dcfce7"))
    st.add("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")
    t.setStyle(st)
    story.append(t)

    # ── Per-bucket detail sections ───────────────────────────────────────
    for r in ok:
        story.append(PageBreak())
        story.append(Paragraph(f"🪣 {r.name}", H2))

        life = "<br/>".join("• " + x for x in r.lifecycle_rules) or "— none —"
        meta = [
            ["Location", f"{r.location} ({r.location_type})",
             "Default class", r.default_storage_class],
            ["Created", r.created or "—",
             "Versioning", "ENABLED" if r.versioning_enabled else "disabled"],
            ["Objects (live / noncurrent)",
             f"{r.object_count:,}  ({r.live_count:,} / {r.noncurrent_count:,})",
             "Est. cost / month", _money(r.cost_month)],
            ["Total size", format_size(r.total_size),
             "Noncurrent size", format_size(r.noncurrent_size)],
            ["Lifecycle rules", Paragraph(life, CELL), "", ""],
        ]
        mt = Table(meta, colWidths=[4.5*cm, 7.5*cm, 4*cm, 5.5*cm], hAlign="LEFT")
        mt.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (0, -1), LIGHT),
            ("BACKGROUND", (2, 0), (2, -1), LIGHT),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe1ea")),
            ("SPAN", (1, 4), (3, 4)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(mt)

        # storage-class breakdown
        story.append(Paragraph("Storage-class breakdown", H2))
        cb = [["Storage class", "Objects", "Size", "Cost/mo"]]
        for sc, v in sorted(r.class_breakdown.items(), key=lambda kv: kv[1]["size"], reverse=True):
            cb.append([sc, f"{v['count']:,}", format_size(v["size"]), _money(v["cost"])])
        ct = Table(cb, repeatRows=1, hAlign="LEFT",
                   colWidths=[5*cm, 3*cm, 3.5*cm, 3*cm])
        ct.setStyle(_header_style(4))
        story.append(ct)

        # folder breakdown
        story.append(Paragraph(f"Folder breakdown (prefix depth {prefix_depth})", H2))
        fb = [["Folder", "Objects", "Size", "Cost/mo"]]
        for f in r.folders[:30]:
            fb.append([Paragraph(_truncate(f.folder, 60), CELL),
                       f"{f.count:,}", format_size(f.size), _money(f.cost_month)])
        ft = Table(fb, repeatRows=1, hAlign="LEFT",
                   colWidths=[12*cm, 3*cm, 3.5*cm, 3*cm])
        ft.setStyle(_header_style(4))
        story.append(ft)

        # top files
        story.append(Paragraph(f"Largest {len(r.top_files)} files", H2))
        tf = [["File", "Size", "Class", "State", "Cost/mo"]]
        for o in r.top_files:
            tf.append([Paragraph(_truncate(o.name, 70), CELL), format_size(o.size),
                       o.storage_class, o.state, _money(o.cost_month)])
        tft = Table(tf, repeatRows=1, hAlign="LEFT",
                    colWidths=[12*cm, 3*cm, 2.5*cm, 2.2*cm, 2.3*cm])
        tft.setStyle(_header_style(5))
        story.append(tft)

    # errors (if any)
    errs = [r for r in reports if r.error]
    if errs:
        story.append(PageBreak())
        story.append(Paragraph("Buckets that could not be read", H2))
        for r in errs:
            story.append(Paragraph(f"• <b>{r.name}</b> — {r.error}", BODY))

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Cost = estimated <b>at-rest storage</b> only (size × class price from "
        "pricing.py). Excludes operations, network egress, retrieval, and "
        "early-delete fees. Edit pricing.py to match your region/contract.", BODY))

    doc.build(story)
