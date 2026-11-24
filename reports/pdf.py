"""PDF summary built with ReportLab (server-side, no browser dependency)."""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PRIMARY = colors.HexColor("#123D2B")
ACCENT = colors.HexColor("#A3D9B1")
BORDER = colors.HexColor("#DCE6DE")
TEXT = colors.HexColor("#25352D")


def ksh(value):
    return f"KSh {value:,.2f}"


def _table(rows, widths):
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F4")]),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def render_pdf(user, report):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Financial summary – {report['range'].label}", author="Student Finance",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=PRIMARY, fontSize=18)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=PRIMARY, fontSize=13, spaceBefore=10)
    body = ParagraphStyle("body", parent=styles["BodyText"], textColor=TEXT, fontSize=10)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#66756C"))

    t = report["totals"]
    rng = report["range"]
    story = [
        Paragraph("Financial summary", h1),
        Paragraph(f"{user.get_full_name() or user.username} &middot; {rng.label} "
                  f"({rng.start:%d %b %Y} – {rng.end:%d %b %Y})", body),
        Paragraph(f"Generated {report['generated']:%d %b %Y %H:%M}", small),
        Spacer(1, 8),
        _table(
            [
                ["Measure", "Amount"],
                ["Total income", ksh(t["income"])],
                ["Total expenses", ksh(t["expenses"])],
                ["Net (income − expenses)", ksh(t["net"])],
                ["Net savings allocated (virtual)", ksh(t["savings"])],
                ["Average daily spending", ksh(report["avg_daily_spend"] or 0)],
            ],
            [110 * mm, 60 * mm],
        ),
        Paragraph("Spending by category", h2),
    ]
    cat_rows = [["Category", "Share", "Amount"]] + [
        [r["category"], f"{r['share']:.1f}%", ksh(r["total"])] for r in report["categories"]
    ]
    story.append(_table(cat_rows if len(cat_rows) > 1 else cat_rows + [["No expenses", "", ""]], [90 * mm, 30 * mm, 50 * mm]))

    story.append(Paragraph("Income by source", h2))
    inc_rows = [["Source", "Amount"]] + [[r["source"], ksh(r["total"])] for r in report["income_sources"]]
    story.append(_table(inc_rows if len(inc_rows) > 1 else inc_rows + [["No income", ""]], [120 * mm, 50 * mm]))

    story.append(Paragraph("Expense records", h2))
    exp_rows = [["Date", "Category", "Description", "Amount"]] + [
        [e.date.strftime("%d %b"), e.category.name, Paragraph((e.description or "")[:70], small), ksh(e.amount)]
        for e in report["expenses"][:400]
    ]
    story.append(_table(exp_rows if len(exp_rows) > 1 else exp_rows + [["", "No expenses", "", ""]], [20 * mm, 35 * mm, 80 * mm, 35 * mm]))
    story += [
        Spacer(1, 10),
        Paragraph(
            "Savings goals are virtual allocations for planning; no money is held or moved by this application. "
            "This report contains only the signed-in student's own records.", small,
        ),
    ]
    doc.build(story)
    return buffer.getvalue()
