"""Bilan 5G Word autonome, sans bibliothèque externe."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Iterable
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Project, ProjectItem, Site

ORANGE = "FFC000"
GREEN = "C6EFCE"
MONTHS = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def _text(value: object, fallback: str = "") -> str:
    return fallback if value is None else (str(value).strip() or fallback)


def _contains(value: object, terms: str) -> bool:
    return any(term in _text(value).lower() for term in terms.split("|"))


def _run(value: object, *, bold: bool = False, underline: bool = False, color: str | None = None, size: int = 19) -> str:
    props = ["<w:rFonts w:ascii=\"Arial\" w:hAnsi=\"Arial\"/>", f"<w:sz w:val=\"{size}\"/>"]
    if bold: props.append("<w:b/>")
    if underline: props.append("<w:u w:val=\"single\"/>")
    if color: props.append(f"<w:color w:val=\"{color}\"/>")
    shown = escape(_text(value, "-"))
    space = ' xml:space="preserve"' if shown.startswith(" ") or shown.endswith(" ") else ""
    return f"<w:r><w:rPr>{''.join(props)}</w:rPr><w:t{space}>{shown}</w:t></w:r>"


def _paragraph(*runs: str, shade: str | None = None, bullet: bool = False, after: int = 80) -> str:
    props = [f"<w:spacing w:before=\"0\" w:after=\"{after}\" w:line=\"220\" w:lineRule=\"auto\"/>"]
    if shade: props.append(f"<w:shd w:fill=\"{shade}\"/>")
    if bullet: props.append("<w:ind w:left=\"360\" w:hanging=\"180\"/>")
    prefix = _run("• ", size=18) if bullet else ""
    return f"<w:p><w:pPr>{''.join(props)}</w:pPr>{prefix}{''.join(runs)}</w:p>"


def _cell(value: object, width: int, *, header: bool = False, positive: bool = False) -> str:
    fill = ORANGE if header else (GREEN if positive else None)
    shading = f"<w:shd w:fill=\"{fill}\"/>" if fill else ""
    align = "<w:jc w:val=\"center\"/>" if header else ""
    return (
        f"<w:tc><w:tcPr><w:tcW w:w=\"{width}\" w:type=\"dxa\"/>{shading}"
        "<w:tcMar><w:top w:w=\"70\" w:type=\"dxa\"/><w:start w:w=\"90\" w:type=\"dxa\"/>"
        "<w:bottom w:w=\"110\" w:type=\"dxa\"/><w:end w:w=\"110\" w:type=\"dxa\"/></w:tcMar>"
        "<w:vAlign w:val=\"center\"/></w:tcPr>"
        f"<w:p><w:pPr>{align}<w:spacing w:before=\"0\" w:after=\"0\" w:line=\"250\" w:lineRule=\"auto\"/></w:pPr>"
        f"{_run(value, bold=header, size=19 if header else 18)}</w:p></w:tc>"
    )


def _table(headers: list[str], rows: Iterable[list[object]], widths: list[int], positive_columns: set[int] | None = None) -> str:
    total = sum(widths)
    borders = "".join(f"<w:{side} w:val=\"single\" w:sz=\"4\" w:space=\"0\" w:color=\"555555\"/>" for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f"<w:gridCol w:w=\"{width}\"/>" for width in widths)
    top = "".join(_cell(label, widths[idx], header=True) for idx, label in enumerate(headers))
    content = []
    for values in rows:
        content.append("<w:tr>" + "".join(_cell(value, widths[idx], positive=bool(positive_columns and idx in positive_columns and _contains(value, "ok|ouvert"))) for idx, value in enumerate(values)) + "</w:tr>")
    return f"<w:tbl><w:tblPr><w:tblW w:w=\"{total}\" w:type=\"dxa\"/><w:tblLayout w:type=\"fixed\"/><w:tblBorders>{borders}</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid><w:tr><w:trPr><w:tblHeader/></w:trPr>{top}</w:tr>{''.join(content)}</w:tbl>"


def _summary(db: Session):
    projects = list(db.scalars(select(Project).order_by(Project.created_at.desc())))
    sites = list(db.scalars(select(Site)))
    items = list(db.scalars(select(ProjectItem)))
    by_project: dict[int, list[ProjectItem]] = {}
    for item in items: by_project.setdefault(item.project_id, []).append(item)
    opened = [item for item in items if _contains(item.statut_ouverture_meteo or item.meteo, "ouvert|open")]
    closed = [item for item in items if item not in opened]
    swapped = sum(_contains(item.swap_vers_tf, "oui|tf") for item in items)
    activated = sum(_contains(item.etat_deploiement, "ok|terminé|termine|oui") for item in items) or sum(_text(site.has_5g) == "✓" for site in sites)
    report: list[list[object]] = []
    for project in projects:
        project_items = by_project.get(project.id, [])
        if not project_items: continue
        actions = sorted({_text(item.type_5g) for item in project_items if _text(item.type_5g)}) or ["New 5G" if project.type == "5g" else "Swap vers MM"]
        for action in actions:
            group = [item for item in project_items if _text(item.type_5g) == action] or project_items
            objective = project.objectif or len(group)
            swaps = sum(_contains(item.swap_vers_tf, "oui|tf") for item in group)
            state = "etat_deploiement" if project.type == "5g" else "gc"
            done = sum(_contains(getattr(item, state), "ok|terminé|termine|oui") for item in group)
            on_meteo = sum(item in opened for item in group)
            note = next((_text(item.plan_action) for item in group if _text(item.plan_action)), "") or ("Objectif atteint ou suivi quotidien requis" if on_meteo >= objective else f"Reste {max(objective-on_meteo, 0)} site(s) à traiter")
            report.append([project.name, action, objective, swaps, done, on_meteo, f"{round(100*on_meteo/objective) if objective else 0}%", note])
    return swapped, activated, opened, closed, report


def build_bilan_5g_docx(db: Session) -> bytes:
    """Crée le bilan Word à partir de l'état actuel de la base locale."""
    today = date.today()
    swapped, activated, opened, closed, report = _summary(db)
    body = [_paragraph(_run("Bilan 5G", bold=True, underline=True, size=26), shade="FFF200", after=160), _paragraph(_run(f"Veuillez trouver ci-après l'état d'avancement des activations NR 5G jusqu'au {today.strftime('%d/%m')}.", size=20), after=160), _paragraph(_run("Bilan 5G :", bold=True, underline=True, size=20), after=30)]
    for label, value in (("Sites swappés", swapped), ("Sites activés", activated), ("Sites ouverts sur météo", len(opened))): body.append(_paragraph(_run(f"{label} : {value}", bold=True, size=18), bullet=True, after=15))
    body += [_paragraph(_run(f"État d'avancement au mois de {MONTHS[today.month-1]}", bold=True, underline=True, size=19), _run(f" : {len(opened)} sites ouverts sur météo", bold=True, color="00A651", size=19), after=70), _table(["Projet", "Type d'action", "Objectif", "Swap done", "Sites activés", "Sites ouverts sur météo", f"% avancement au {today.strftime('%d/%m')}", "Point d'attention & Next step"], report or [["-", "-", 0, 0, 0, 0, "0%", "Aucun projet à suivre"]], [1300, 1150, 700, 850, 900, 1100, 920, 7768]), _paragraph(_run("", size=8), after=30), _paragraph(_run("Sites ouverts sur météo (confirmer la résolution de pb) :", bold=True, underline=True, size=19), after=60)]
    open_rows = [[item.site_code, item.config, item.hw, item.etat_deploiement, item.kpis, item.status or item.plan_action, item.statut_ouverture_meteo or item.meteo, item.owner] for item in opened]
    body += [_table(["Site Name", "Config Site", "État HW", "État d'activation", "KPIs", "Status", "Status ouverture sur météo", "Owner"], open_rows or [["-", "-", "-", "-", "-", "-", "-", "-"]], [1250, 1650, 850, 1200, 2100, 2300, 2550, 2788], {1, 2, 3, 4, 5, 6}), _paragraph(_run("", size=8), after=30), _paragraph(_run("Sites non ouverts sur météo (reliquat du mois précédent à inclure dans le plan du mois suivant) :", bold=True, underline=True, size=19), after=60)]
    closed_rows = [[item.site_code, item.config, item.hw, item.etat_deploiement, item.kpis, item.status or item.plan_action] for item in closed]
    body += [_table(["Site Name", "Config site", "État HW", "État activation", "État KPIs", "Status"], closed_rows or [["-", "-", "-", "-", "-", "-"]], [1600, 2200, 1350, 1700, 2600, 5238], {1, 2, 3, 4, 5}), "<w:sectPr><w:pgSz w:w=\"15840\" w:h=\"12240\" w:orient=\"landscape\"/><w:pgMar w:top=\"605\" w:right=\"576\" w:bottom=\"605\" w:left=\"576\" w:header=\"360\" w:footer=\"360\" w:gutter=\"0\"/></w:sectPr>"]
    doc = "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body>" + "".join(body) + "</w:body></w:document>"
    files = {"[Content_Types].xml": "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"><Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/><Default Extension=\"xml\" ContentType=\"application/xml\"/><Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/></Types>", "_rels/.rels": "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"><Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/></Relationships>", "word/document.xml": doc}
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items(): archive.writestr(name, content.encode("utf-8"))
    return output.getvalue()
