"""Hospital usage report PDF (reportlab). Pure rendering — numbers are computed by the caller."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

FOREST = colors.HexColor("#1E3F2A")
SAND = colors.HexColor("#F4F0EA")
LINE = colors.HexColor("#E5E4E2")


def render_usage_report(report: dict) -> bytes:
    buf = io.BytesIO()
    brand = colors.HexColor(report.get("primary_color") or "#1E3F2A")
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"{report['account_name']} usage report {report['period_label']}")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], alignment=0, textColor=brand, fontSize=22, spaceAfter=4)
    sub = ParagraphStyle("sub", parent=styles["Normal"], textColor=colors.HexColor("#525252"), fontSize=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=colors.HexColor("#1A1A1A"), fontSize=13, spaceBefore=14)
    story = [
        Paragraph(report["account_name"], h1),
        Paragraph(f"Usage report · {report['period_label']} · Account {report['account_id']}", sub),
        Spacer(1, 10),
    ]

    kpis = report["kpis"]
    cells = [[Paragraph(f"<font size=8 color='#525252'>{k['label'].upper()}</font><br/>"
                        f"<font size=18><b>{k['value']}</b></font><br/>"
                        f"<font size=8 color='#525252'>{k.get('sub', '')}</font>", styles["Normal"]) for k in kpis[i:i + 3]]
             for i in range(0, len(kpis), 3)]
    grid = Table(cells, colWidths=[58 * mm] * 3)
    grid.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SAND), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                              ("INNERGRID", (0, 0), (-1, -1), 4, colors.white),
                              ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [grid]

    for title, header, rows in report["tables"]:
        story.append(Paragraph(title, h2))
        if not rows:
            story.append(Paragraph("No activity in this period.", sub))
            continue
        t = Table([header] + rows, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SAND]),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.append(t)

    story += [Spacer(1, 18), Paragraph(f"Generated {report['generated_at']} by Sihha AI. Counts cover staff and "
                                       "customers linked to this account. No patient names or clinical details are included.", sub)]
    doc.build(story)
    return buf.getvalue()
