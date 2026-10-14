"""PDF rendering for the printable participant sign-in sheet.

Uses reportlab's Platypus API — no system dependencies, and the built-in
Helvetica font covers French accents.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Localised labels for the sheet. French is the default.
LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "name": "Nom",
        "club": "Club",
        "gender": "Sexe",
        "weight": "Poids",
        "category": "Catégorie",
        "group": "Poule",
        "presence": "Présence",
        "count": "{n} participant(s)",
        "allClubs": "Tous les clubs",
        "allGenders": "Tous les sexes",
        "allPools": "Toutes les poules",
        "unassigned": "Non affectés",
    },
    "en": {
        "name": "Name",
        "club": "Club",
        "gender": "Gender",
        "weight": "Weight",
        "category": "Category",
        "group": "Group",
        "presence": "Presence",
        "count": "{n} participant(s)",
        "allClubs": "All clubs",
        "allGenders": "All genders",
        "allPools": "All pools",
        "unassigned": "Unassigned",
    },
}


@dataclass
class PdfRow:
    name: str
    club: str
    gender: str
    weight: float | None


def build_participants_pdf(
    *,
    title: str,
    subtitle: str,
    filter_summary: str,
    rows: list[PdfRow],
    lang: str = "fr",
) -> bytes:
    """Render the participant list to PDF bytes."""
    labels = LABELS.get(lang, LABELS["fr"])
    styles = getSampleStyleSheet()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        title=title,
    )

    elements: list = [Paragraph(title, styles["Title"])]
    if subtitle:
        elements.append(Paragraph(subtitle, styles["Normal"]))
    summary_line = f"{filter_summary} — {labels['count'].format(n=len(rows))}"
    elements.append(Paragraph(summary_line, styles["Normal"]))
    elements.append(Spacer(1, 8))

    header = [
        "#",
        labels["name"],
        labels["club"],
        labels["gender"],
        labels["weight"],
        labels["presence"],
    ]
    data = [header]
    for i, r in enumerate(rows, start=1):
        data.append(
            [
                str(i),
                r.name,
                r.club,
                r.gender,
                f"{r.weight:g} kg" if r.weight is not None else "—",
                "",  # presence — left blank to tick by hand
            ]
        )

    # Column widths sum to ~186mm (A4 width minus margins).
    col_widths = [
        10 * mm,
        60 * mm,
        45 * mm,
        16 * mm,
        24 * mm,
        31 * mm,
    ]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9edf5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#888888")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 1), (0, -1), "CENTER"),  # row numbers
                ("ALIGN", (3, 0), (4, -1), "CENTER"),  # gender + weight
                # Roomy rows so presence can be ticked by hand.
                ("TOPPADDING", (0, 1), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return buf.getvalue()
