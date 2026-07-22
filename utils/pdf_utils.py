from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)

PRIMARY = colors.HexColor("#1e293b")
ACCENT = colors.HexColor("#2563eb")
LIGHT = colors.HexColor("#f1f5f9")


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontSize=18, leading=22, textColor=PRIMARY, spaceAfter=6, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="SectionHeading", fontSize=13, leading=16, textColor=PRIMARY, spaceBefore=14, spaceAfter=6, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="SmallGrey", fontSize=8.5, textColor=colors.HexColor("#64748b")))
    return styles


def _kv_table(pairs, col_widths=(240, 220)):
    data = [[Paragraph(f"<b>{k}</b>", getSampleStyleSheet()["Normal"]), str(v)] for k, v in pairs]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    return t


def _boq_table(headers, rows, col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_estimate_pdf(pdf_path, project, metrics=None, boq=None, optimization=None):
    """
    Builds a professional multi-section PDF estimate report covering:
    project details, AI-detected geometry, BOQ (materials & labour),
    area calculations, GST/wastage/profit cost summary, AI optimization
    suggestions, and the Manual vs AI comparison.

    `project` is the SQLAlchemy Project row. `metrics`/`boq`/`optimization`
    are optional richer dicts (from the last analysis) that are used when
    available and fall back to the persisted project fields otherwise.
    """
    styles = _styles()
    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm
    )
    story = []

    story.append(Paragraph("BuildAI Construction Estimator", styles["ReportTitle"]))
    story.append(Paragraph("Comparative Analysis: Manual vs AI-Assisted Cost Estimation Report", styles["Normal"]))
    story.append(Spacer(1, 10))

    # --- Project Details ---
    story.append(Paragraph("1. Project Details", styles["SectionHeading"]))
    story.append(_kv_table([
        ("Project Name", project.name),
        ("Built-up Area", f"{project.built_up_area_sqm} sq.m"),
        ("Perimeter", f"{project.perimeter_m} m"),
        ("Rate Schedule", project.rate_source or "-"),
        ("Report Generated", project.created_at.strftime("%d %b %Y") if project.created_at else "-"),
    ]))

    # --- AI Detection ---
    story.append(Paragraph("2. AI Floor Plan Detection", styles["SectionHeading"]))
    story.append(_kv_table([
        ("Rooms Detected", project.room_count or 0),
        ("Wall Segments Detected", project.wall_count or 0),
        ("Doors Detected", project.door_count or 0),
        ("Windows Detected", project.window_count or 0),
    ]))

    # --- Area Calculations ---
    story.append(Paragraph("3. Slab, Paint & Tile Area Calculation", styles["SectionHeading"]))
    story.append(_kv_table([
        ("Slab Area", f"{project.slab_area_sqm or 0} sq.m"),
        ("Paint Area (both faces, net of openings)", f"{project.paint_area_sqm or 0} sq.m"),
        ("Tile Area (floor + wet-area dado)", f"{project.tile_area_sqm or 0} sq.m"),
    ]))

    # --- Material BOQ ---
    if boq and boq.get("material_boq"):
        story.append(Paragraph("4. AI-Generated Material BOQ", styles["SectionHeading"]))
        rows = [
            [m["item"], f'{m["quantity"]} {m["unit"]}', f'Rs. {m["rate"]:,.2f}', m.get("rate_source", "-"), f'Rs. {m["total_cost"]:,.2f}']
            for m in boq["material_boq"]
        ]
        story.append(_boq_table(
            ["Material", "Quantity", "Rate", "Source", "Total Cost"],
            rows, col_widths=[110, 90, 90, 90, 100]
        ))

    # --- Labour BOQ ---
    if boq and boq.get("labour_boq"):
        story.append(Paragraph("5. Labour Cost Estimation", styles["SectionHeading"]))
        rows = [
            [l["category"], f'{l["days"]} days', f'Rs. {l["rate"]:,.2f}', f'Rs. {l["total_cost"]:,.2f}']
            for l in boq["labour_boq"]
        ]
        story.append(_boq_table(
            ["Category", "Days", "Rate/Day", "Total Cost"],
            rows, col_widths=[150, 90, 100, 140]
        ))

    # --- Cost Summary ---
    story.append(Paragraph("6. Cost Summary (GST, Wastage & Contractor Profit)", styles["SectionHeading"]))
    material_cost = boq.get("material_cost") if boq else project.material_cost
    labour_cost = boq.get("labour_cost") if boq else project.labour_cost
    wastage_amount = boq.get("wastage_amount") if boq else project.wastage_amount
    gst_amount = boq.get("gst_amount") if boq else project.gst_amount
    gst_pct = boq.get("gst_pct") if boq else 18.0
    profit_amount = boq.get("profit_amount") if boq else project.profit_amount
    profit_pct = boq.get("profit_pct") if boq else 15.0

    story.append(_kv_table([
        ("Material Cost", f"Rs. {(material_cost or 0):,.2f}"),
        ("Labour Cost", f"Rs. {(labour_cost or 0):,.2f}"),
        ("Material Wastage Allowance", f"Rs. {(wastage_amount or 0):,.2f}"),
        (f"GST @ {gst_pct}%", f"Rs. {(gst_amount or 0):,.2f}"),
        (f"Contractor Profit @ {profit_pct}%", f"Rs. {(profit_amount or 0):,.2f}"),
        ("AI-Assisted Total Estimate", f"Rs. {project.ai_total_cost:,.2f}"),
    ]))

    # --- AI Optimization ---
    if optimization and optimization.get("suggestions"):
        story.append(Paragraph("7. AI Cost Optimization Suggestions", styles["SectionHeading"]))
        rows = [
            [s["original_item"], s["suggested_alternative"], f'Rs. {s["estimated_saving"]:,.2f}']
            for s in optimization["suggestions"]
        ]
        story.append(_boq_table(
            ["Item", "Suggested Alternative", "Est. Saving"],
            rows, col_widths=[110, 220, 90]
        ))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<b>Total Potential Saving: Rs. {optimization.get('total_estimated_saving', 0):,.2f}</b>",
            styles["Normal"]
        ))

    # --- Manual vs AI comparison ---
    story.append(Paragraph("8. Manual vs AI Cost Comparison", styles["SectionHeading"]))
    story.append(_kv_table([
        ("AI-Assisted Cost Estimate", f"Rs. {project.ai_total_cost:,.2f}"),
        ("Manual Estimate Cost", f"Rs. {project.manual_total_cost:,.2f}"),
        ("Cost Variance", f"{project.variance_pct}%"),
    ]))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "This report was automatically generated by the BuildAI Construction Estimator. "
        "Rates are benchmarked against CPWD / Maharashtra PWD schedules and current market inputs; "
        "actuals may vary based on site conditions, design changes and material availability.",
        styles["SmallGrey"]
    ))

    doc.build(story)
    return pdf_path
