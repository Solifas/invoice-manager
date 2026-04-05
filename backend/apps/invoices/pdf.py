from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Invoice


def _money(invoice: Invoice, value: Decimal) -> str:
    return f"{invoice.currency} {value:.2f}"


def build_invoice_pdf(invoice: Invoice) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#18212c"),
        spaceAfter=8,
    )
    label_style = ParagraphStyle(
        "InvoiceLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#5f6c7b"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "InvoiceBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#18212c"),
    )

    story = [
        Paragraph("Invoice", label_style),
        Paragraph(invoice.invoice_number, title_style),
        Paragraph(f"Status: {invoice.get_status_display()}", body_style),
        Spacer(1, 10),
    ]

    summary_table = Table(
        [
            [
                Paragraph("<b>Billed to</b>", label_style),
                Paragraph("<b>Invoice details</b>", label_style),
            ],
            [
                Paragraph(
                    "<br/>".join(
                        [
                            invoice.client.name,
                            invoice.client.email,
                            invoice.client.address or "",
                        ]
                    ),
                    body_style,
                ),
                Paragraph(
                    "<br/>".join(
                        [
                            f"Issue date: {invoice.issue_date}",
                            f"Due date: {invoice.due_date}",
                            f"Currency: {invoice.currency}",
                            f"Tax: {'No tax' if invoice.tax_type == 'none' else f'{invoice.tax_rate}%'}",
                        ]
                    ),
                    body_style,
                ),
            ],
        ],
        colWidths=[86 * mm, 86 * mm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3fb")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dde6")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dde6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 12)])

    items_data = [
        ["Description", "Qty", "Unit price", "Line total"],
        *[
            [
                item.description,
                str(item.quantity),
                _money(invoice, item.unit_price),
                _money(invoice, item.line_total),
            ]
            for item in invoice.line_items.all()
        ],
    ]
    items_table = Table(items_data, colWidths=[92 * mm, 20 * mm, 34 * mm, 34 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18212c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dde6")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.extend([items_table, Spacer(1, 12)])

    totals_table = Table(
        [
            ["Subtotal", _money(invoice, invoice.subtotal)],
            ["Tax", _money(invoice, invoice.tax_amount)],
            ["Total", _money(invoice, invoice.total_amount)],
        ],
        colWidths=[44 * mm, 34 * mm],
        hAlign="RIGHT",
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffdf8")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dde6")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dde6")),
                ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    story.extend([totals_table, Spacer(1, 14)])

    if invoice.notes:
        story.extend(
            [
                Paragraph("Notes", label_style),
                Paragraph(invoice.notes.replace("\n", "<br/>"), body_style),
            ]
        )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
