"""
GET /api/v1/report?session_key=
Generates a comprehensive PDF area report covering all 5 tabs.
Uses ReportLab (pure Python, no system dependencies).
"""
import asyncio
import io
from datetime import date
from xml.sax.saxutils import escape as _xml_escape
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.errors import http_error
from app.services.session_helpers import (
    require_session,
    session_centroid,
    session_parent_lads,
    session_parent_name,
    session_boundary_source,
)
from app.services.helpers import enrich_metrics
from app.services.tab_property import fetch_property_market
from app.services.tab_lifestyle import fetch_lifestyle_connectivity
from app.services.tab_environment import fetch_environment_safety
from app.services.tab_community import fetch_community_education
from app.services.tab_governance import fetch_local_governance

router = APIRouter()

# Brand colours
BRAND_BLUE  = (0.231, 0.357, 0.859)   # #3b5bdb
INK         = (0.102, 0.102, 0.180)   # #1a1a2e
INK_MUTED   = (0.333, 0.333, 0.333)
SURFACE     = (0.973, 0.976, 0.980)   # #f8f9fa
DIVIDER     = (0.910, 0.925, 0.941)   # #e8ecf0
GREEN_BG    = (0.827, 0.976, 0.847)
GREEN_TEXT  = (0.102, 0.478, 0.212)
RED_BG      = (1.0,   0.890, 0.890)
RED_TEXT    = (0.788, 0.165, 0.165)
BLUE_BG     = (0.906, 0.965, 1.0)
BLUE_TEXT   = (0.098, 0.443, 0.761)


def _fmt(value, unit="") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        if unit in ("GBP", "GBP/year", "GBP/month"):
            return f"£{value:,.0f}"
        return f"{value:,.1f}"
    if isinstance(value, int):
        if unit in ("GBP", "GBP/year", "GBP/month"):
            return f"£{value:,}"
        return f"{value:,}"
    return str(value)


def _build_pdf(area_name: str, lad_code: str, all_tabs: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import Color, HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable, KeepTogether,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title=f"PropertyPulse — {area_name}",
        author="PropertyPulse",
    )

    W = A4[0] - 36*mm  # usable width

    c_brand  = Color(*BRAND_BLUE)
    c_ink    = Color(*INK)
    c_muted  = Color(*INK_MUTED)
    c_surf   = Color(*SURFACE)
    c_div    = Color(*DIVIDER)
    c_gbg    = Color(*GREEN_BG)
    c_gtxt   = Color(*GREEN_TEXT)
    c_rbg    = Color(*RED_BG)
    c_rtxt   = Color(*RED_TEXT)
    c_bbg    = Color(*BLUE_BG)
    c_btxt   = Color(*BLUE_TEXT)

    styles = getSampleStyleSheet()

    def sty(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    cover_title = sty("CoverTitle", fontSize=26, textColor=c_ink,
                      fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=6)
    cover_sub   = sty("CoverSub",   fontSize=13, textColor=c_muted,
                      alignment=TA_CENTER, spaceAfter=4)
    cover_meta  = sty("CoverMeta",  fontSize=8,  textColor=c_muted,
                      alignment=TA_CENTER, spaceAfter=0)
    tab_title   = sty("TabTitle",   fontSize=14, textColor=c_brand,
                      fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=8)
    metric_name = sty("MName",      fontSize=7.5, textColor=c_muted,
                      fontName="Helvetica-Bold", spaceAfter=1)
    metric_val  = sty("MVal",       fontSize=16,  textColor=c_ink,
                      fontName="Helvetica-Bold", spaceAfter=1)
    metric_par  = sty("MPar",       fontSize=7.5, textColor=c_muted, spaceAfter=1)
    detail_lbl  = sty("DLbl",       fontSize=7.5, textColor=c_muted)
    detail_val  = sty("DVal",       fontSize=7.5, textColor=c_ink,
                      fontName="Helvetica-Bold")
    note_style  = sty("Note",       fontSize=7,   textColor=c_muted,
                      fontName="Helvetica-Oblique")
    disc_style  = sty("Disc",       fontSize=7.5, textColor=c_muted, spaceAfter=0)

    def _badge_text(flag):
        if flag == "higher_than_parent":
            return "▲ Above avg", c_gbg, c_gtxt
        if flag == "lower_than_parent":
            return "▼ Below avg", c_rbg, c_rtxt
        if flag == "equal_to_parent":
            return "= Area avg",  c_bbg, c_btxt
        return None, None, None

    def _metric_block(m: dict):
        """Return a list of flowables for one metric card."""
        mid   = m.get("id", "")
        name  = m.get("name", "")
        local = m.get("local_value")
        parent= m.get("parent_value")
        unit  = m.get("unit", "")
        flag  = m.get("comparison_flag") or ""
        det   = m.get("details") or {}

        if mid in ("demographics_overview", "area_persona"):
            return []

        items = []
        items.append(Paragraph(_xml_escape(name.upper()), metric_name))
        items.append(Paragraph(_xml_escape(_fmt(local, unit)), metric_val))

        badge_txt, bg, fg = _badge_text(flag)
        if badge_txt:
            items.append(Paragraph(f'<font color="#{_hex(fg)}">{_xml_escape(badge_txt)}</font>', metric_par))

        if parent is not None:
            items.append(Paragraph(f"Area avg: {_xml_escape(_fmt(parent, unit))}", metric_par))

        # Detail key-value rows (skip nested, notes, risk_score)
        det_rows = [
            (k, v) for k, v in det.items()
            if v is not None
            and not isinstance(v, (dict, list))
            and not k.endswith("_note")
            and k not in ("risk_score",)
        ][:6]
        if det_rows:
            tdata = [
                [Paragraph(_xml_escape(k.replace("_", " ").title()), detail_lbl),
                 Paragraph(_xml_escape(_fmt(v, unit if ("price" in k or "earn" in k) else "")), detail_val)]
                for k, v in det_rows
            ]
            t = Table(tdata, colWidths=[W*0.5*0.58, W*0.5*0.42])
            t.setStyle(TableStyle([
                ("FONTSIZE",    (0,0),(-1,-1), 7.5),
                ("TOPPADDING",  (0,0),(-1,-1), 1),
                ("BOTTOMPADDING",(0,0),(-1,-1), 1),
                ("LEFTPADDING", (0,0),(-1,-1), 0),
                ("RIGHTPADDING",(0,0),(-1,-1), 0),
                ("ALIGN",       (1,0),(1,-1), "RIGHT"),
            ]))
            items.append(t)

        # Notes
        for k, v in det.items():
            if k.endswith("_note") and isinstance(v, str):
                items.append(Paragraph(_xml_escape(v), note_style))

        return items

    def _hex(color):
        """Convert reportlab Color to hex string for Paragraph markup."""
        if color is None:
            return "000000"
        r = int(color.red * 255)
        g = int(color.green * 255)
        b = int(color.blue * 255)
        return f"{r:02x}{g:02x}{b:02x}"

    story = []

    # ── Cover page ──────────────────────────────────────────────────
    story.append(Spacer(1, 30*mm))
    story.append(HRFlowable(width=W, thickness=3, color=c_brand, spaceAfter=16))
    story.append(Paragraph("Area Intelligence Report", cover_title))
    story.append(Paragraph(_xml_escape(area_name), cover_sub))
    story.append(Paragraph(
        f"LAD Code: {_xml_escape(lad_code)}  ·  Generated by PropertyPulse  ·  {date.today().strftime('%d %B %Y')}",
        cover_meta))
    story.append(HRFlowable(width=W, thickness=1, color=c_div, spaceBefore=16))

    # ── Tab sections ────────────────────────────────────────────────
    tab_colours = {
        "Property & Market":       HexColor("#2563eb"),
        "Lifestyle & Connectivity":HexColor("#7c3aed"),
        "Environment & Safety":    HexColor("#059669"),
        "Community & Education":   HexColor("#ea580c"),
        "Local Governance":        HexColor("#0891b2"),
    }

    for tab_name, metrics in all_tabs.items():
        if not metrics:
            continue
        story.append(PageBreak())

        colour = tab_colours.get(tab_name, c_brand)
        h_sty = sty(f"TH_{tab_name}", fontSize=14, textColor=colour,
                    fontName="Helvetica-Bold", spaceBefore=0, spaceAfter=8)
        story.append(Paragraph(_xml_escape(tab_name), h_sty))
        story.append(HRFlowable(width=W, thickness=1.5, color=colour, spaceAfter=10))

        # Two-column grid of metric cards
        col_w = (W - 6*mm) / 2
        cells = []
        skip = {"demographics_overview", "area_persona"}
        valid = [m for m in metrics if m.get("id") not in skip]

        for i in range(0, len(valid), 2):
            row_cells = []
            for m in valid[i:i+2]:
                block = _metric_block(m)
                if not block:
                    row_cells.append("")
                else:
                    # Wrap block in a mini-table cell
                    inner = Table([[b] for b in block], colWidths=[col_w - 6*mm])
                    inner.setStyle(TableStyle([
                        ("TOPPADDING",   (0,0),(-1,-1), 1),
                        ("BOTTOMPADDING",(0,0),(-1,-1), 1),
                        ("LEFTPADDING",  (0,0),(-1,-1), 0),
                        ("RIGHTPADDING", (0,0),(-1,-1), 0),
                    ]))
                    row_cells.append(inner)
            if len(row_cells) == 1:
                row_cells.append("")
            cells.append(row_cells)

        if cells:
            grid = Table(cells, colWidths=[col_w, col_w], spaceBefore=0)
            grid.setStyle(TableStyle([
                ("BACKGROUND",   (0,0),(-1,-1), c_surf),
                ("BOX",          (0,0),(0,-1),  0.5, c_div),
                ("BOX",          (1,0),(1,-1),  0.5, c_div),
                ("TOPPADDING",   (0,0),(-1,-1), 6),
                ("BOTTOMPADDING",(0,0),(-1,-1), 6),
                ("LEFTPADDING",  (0,0),(-1,-1), 8),
                ("RIGHTPADDING", (0,0),(-1,-1), 8),
                ("VALIGN",       (0,0),(-1,-1), "TOP"),
                ("ROWBACKGROUNDS",(0,0),(-1,-1), [c_surf, Color(0.96,0.97,0.98)]),
            ]))
            story.append(KeepTogether([grid]))

    # ── Disclaimer ──────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Data Sources & Disclaimer", tab_title))
    story.append(HRFlowable(width=W, thickness=1, color=c_div, spaceAfter=8))
    disc_text = (
        "Property prices from HM Land Registry Price Paid Data (OGL v3). "
        "Crime statistics from data.police.uk (OGL v3). "
        "Broadband coverage from Ofcom Connected Nations (OGL v3). "
        "Deprivation indices from MHCLG English Indices of Deprivation 2025. "
        "Demographics from ONS Census 2021. "
        "Air quality from DEFRA LAQM modelled data. "
        "Flood risk from Environment Agency (OGL v3). "
        "Transport access from NaPTAN / TfL (OGL v3). "
        "Schools from Ofsted / Get Information About Schools (OGL v3). "
        "This report is for informational purposes only and does not constitute professional advice. "
        f"© PropertyPulse {date.today().year}"
    )
    story.append(Paragraph(disc_text, disc_style))

    doc.build(story)
    return buf.getvalue()


@router.get("/report")
async def generate_report(
    session_key: str = Query(..., description="LSOA session key from /resolve"),
    db: AsyncSession = Depends(get_db),
):
    sess = await require_session(session_key)

    lad_code = sess.get("lad_code", "_")
    ward_code = sess.get("ward_code", "_")
    lsoa_codes = sess.get("lsoa_codes", [])
    centroid_lat, centroid_lon = session_centroid(sess)
    effective_mode = sess.get("search_mode", "postcode")
    local_lads = sess.get("local_lads", [])
    parent_lads = session_parent_lads(sess)

    # Fetch area name
    lad_row = await db.execute(
        text("SELECT lad_name FROM core_lad_boundaries WHERE lad_code = :lad"),
        {"lad": lad_code},
    )
    lad_name_row = lad_row.mappings().first()
    area_name = lad_name_row["lad_name"] if lad_name_row else lad_code

    parent_name = session_parent_name(sess)

    # Fetch all 5 tabs in parallel
    kwargs = dict(
        db=db, lad_code=lad_code, ward_code=ward_code,
        lsoa_codes=lsoa_codes, centroid_lat=centroid_lat, centroid_lon=centroid_lon,
        search_mode=effective_mode, local_lads=local_lads,
        parent_lads=parent_lads,
        parent_name=parent_name,
        boundary_source=session_boundary_source(sess),
    )
    results = await asyncio.gather(
        fetch_property_market(**kwargs),
        fetch_lifestyle_connectivity(**kwargs),
        fetch_environment_safety(**kwargs),
        fetch_community_education(**kwargs),
        fetch_local_governance(**kwargs),
        return_exceptions=True,
    )

    tab_names = [
        "Property & Market",
        "Lifestyle & Connectivity",
        "Environment & Safety",
        "Community & Education",
        "Local Governance",
    ]
    all_tabs = {}
    for tab_name, result in zip(tab_names, results):
        flat = [] if isinstance(result, Exception) else result
        all_tabs[tab_name] = enrich_metrics(flat, parent_name=parent_name)

    try:
        pdf_bytes = await asyncio.to_thread(_build_pdf, area_name, lad_code, all_tabs)
    except Exception as e:
        raise http_error(500, "PDF_GENERATION_FAILED", f"PDF generation failed: {e}")

    filename = f"PropertyPulse_{area_name.replace(' ', '_')}_{lad_code}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
