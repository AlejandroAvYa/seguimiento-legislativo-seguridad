# -*- coding: utf-8 -*-
"""Respaldo del servicio web del Senado: arma la ficha de un proyecto leyendo las páginas del sitio de tramitación.

Se usa automáticamente cuando el servicio web (wspublico/tramitacion.php) no responde o deja de informar boletines.
Entrega un diccionario con la misma forma que senado.leer_xml(), salvo:
  votaciones, oficios y observaciones: el sitio no las publica en estas páginas; se conservan las del último dato bueno.

Páginas (tramitacion.senado.cl/appsenado/index.php?mo=tramitacion&ac=...):
  datos_proy&nboletin=N    título, fechas, urgencia, cámara de origen, iniciativa, refundidos, etapa, ley
  tramites&proyid=ID       trámites (sesión, fecha, descripción, etapa / cámara)
  urgencias&proyid=ID      urgencias (tipo, inicio, mensaje, término, mensaje de retiro)
  informes&proyid=ID       informes de comisión
  indicaciones&proyid=ID   boletines de indicaciones
  comparados&proyid=ID     comparados
  autores&proyid=ID        autores
  boletin_x_fecha&boletin= estado (En tramitación, Publicado, Archivado…)
"""
import html
import re

import senado

APP = "https://tramitacion.senado.cl/appsenado/index.php?mo=tramitacion&ac="
MESES = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                      "septiembre", "octubre", "noviembre", "diciembre"], 1)}


def _txt(fragmento):
    t = re.sub(r"(?is)<br\s*/?>", " ", fragmento or "")
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t).strip()


def filas(pagina):
    """Filas de datos de las tablas de una página (sin plantillas comentadas ni encabezados)."""
    pagina = re.sub(r"(?s)<!--.*?-->", "", pagina)
    out = []
    for r in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pagina):
        celdas = re.findall(r"(?is)<td[^>]*>(.*?)</td>", r)
        if not celdas or re.search(r'(?i)type="ro"', r):
            continue
        out.append(celdas)
    return out


def _link(celda):
    m = re.search(r'href="([^"]*getDocto[^"]*)"', celda or "")
    return senado._link("https://tramitacion.senado.cl" + html.unescape(m.group(1))) if m else ""


def fecha_larga(texto):
    """'Martes 13 de Septiembre, 2022' -> '13/09/2022' (forma del servicio web)."""
    m = re.search(r"(\d{1,2}) de (\w+),? (\d{4})", texto or "", re.I)
    if not m or m.group(2).lower() not in MESES:
        return ""
    return f"{int(m.group(1)):02d}/{MESES[m.group(2).lower()]:02d}/{m.group(3)}"


def leer_datos(pagina):
    """Cabecera del proyecto (datos_proy)."""
    d = {}
    pag = re.sub(r"(?s)<!--.*?-->", "", pagina)
    m = re.search(r"proyid\s*=\s*(\d+)", pag)
    d["proyid"] = m.group(1) if m else ""
    m = re.search(r"Bolet(?:&iacute;|í)n\s+(\d+-\d+)", pag)
    d["boletin"] = m.group(1) if m else ""
    celdas = [_txt(c) for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", pag)]

    def valor(etiqueta):
        for i, c in enumerate(celdas[:-1]):
            if c.rstrip(":").lower() == etiqueta.lower():
                return celdas[i + 1]
        return ""
    d["titulo"] = valor("Título")
    d["fecha_ingreso"] = fecha_larga(valor("Fecha de Ingreso"))
    d["urgencia_actual"] = "" if valor("Urgencia Actual") == "Sin urgencia" else valor("Urgencia Actual")
    d["camara_origen"] = valor("Cámara de Origen")
    d["iniciativa"] = valor("Iniciativa")
    ref = valor("Refundido")
    m = re.search(r"Refundido con:\s*(.*?)\s*\)?\s*$", ref)
    d["refundidos"] = m.group(1).strip(" )") if m else ""
    # Etapa: "<strong>Primer trámite constitucional</strong> (Senado) <br> Segundo informe de comisión…"
    m = re.search(r"(?is)Etapa:\s*</td>\s*<td[^>]*>(.*?)</td>", pag)
    etapa, sub = "", ""
    if m:
        bloque = m.group(1)
        fuerte = re.search(r"(?is)<strong>(.*?)</strong>", bloque)
        etapa = _txt(fuerte.group(1)) if fuerte else ""
        resto = _txt(bloque[fuerte.end():] if fuerte else bloque)
        cam = re.match(r"^\(([^)]*)\)\s*(.*)$", resto)
        if cam:
            etapa = f"{etapa} ({cam.group(1)})"
            resto = cam.group(2)
        sub = resto.strip()
        # la subetapa (o el número de ley) viene en las filas siguientes, con la etiqueta vacía
        for fila in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pag[m.end():])[:3]:
            cs = re.findall(r"(?is)<td[^>]*>(.*?)</td>", fila)
            if len(cs) < 2 or _txt(cs[0]):
                break
            t = _txt(cs[1])
            if t and not re.search(r"Ley N[°º]", t) and t != "En tramitación" and not sub:
                sub = t
    d["etapa"], d["subetapa"] = etapa, sub
    m = re.search(r"(Ley N[°º]\s*[\d.]+)\s*\(Diario Oficial del (\d{2}/\d{2}/\d{4})\)", _txt(pag))
    d["leynro"], d["diariooficial"] = (m.group(1), m.group(2)) if m else ("", "")
    return d


def leer_tramites(pagina):
    out = []
    for c in filas(pagina):
        if len(c) < 4 or not re.match(r"\d{2}/\d{2}/\d{4}", _txt(c[1])):
            continue
        etapa, _, camara = _txt(c[3]).partition(" / ")
        out.append({"fecha": senado.fecha_iso(_txt(c[1])), "sesion": _txt(c[0]).replace(" ", "") or "/",
                    "descripcion": _txt(c[2]), "etapa": etapa.strip(), "camara": camara.strip()})
    return out


def leer_urgencias(pagina):
    out = []
    for c in filas(pagina):
        if len(c) < 5 or not re.match(r"\d{2}/\d{2}/\d{4}", _txt(c[1])):
            continue
        out.append({"tipo": _txt(c[0]), "ingreso": senado.fecha_iso(_txt(c[1])), "retiro": senado.fecha_iso(_txt(c[3])),
                    "camara": "", "mensaje": _txt(c[2])})
    return sorted(out, key=lambda u: u["ingreso"])


def leer_informes(pagina):
    out = []
    for c in filas(pagina):
        if len(c) < 4 or not re.match(r"\d{2}/\d{2}/\d{4}", _txt(c[0])):
            continue
        out.append({"fecha": senado.fecha_iso(_txt(c[0])), "tramite": _txt(c[1]), "etapa": _txt(c[2]), "link": _link(c[3])})
    return sorted(out, key=lambda x: x["fecha"])


def leer_indicaciones(pagina):
    out = []
    for c in filas(pagina):
        if len(c) < 4 or not re.match(r"\d{2}/\d{2}/\d{4}", _txt(c[0])):
            continue
        link = _link(c[3])
        out.append({"fecha": senado.fecha_iso(_txt(c[0])), "tramite": _txt(c[1]), "etapa": _txt(c[2]), "link": link,
                    "iddocto": (re.search(r"iddocto=(\d+)", link) or [None, ""])[1]})
    return sorted(out, key=lambda x: x["fecha"])


def leer_comparados(pagina):
    return [{"descripcion": _txt(c[0]), "link": _link(c[1])} for c in filas(pagina) if len(c) >= 2 and _link(c[1])]


def leer_autores(pagina):
    return [_txt(c[1]) for c in filas(pagina) if len(c) >= 2 and re.match(r"^\d+$", _txt(c[0]))]


def leer_estado(pagina, boletin):
    for c in filas(pagina):
        t = [_txt(x) for x in c]
        if boletin in t:
            i = t.index(boletin)
            if len(t) > i + 2:
                return t[i + 2]
    return ""


def ficha(boletin, previo=None):
    """Ficha armada desde el sitio de tramitación. Devuelve None si el sitio tampoco informa el boletín."""
    num = boletin.split("-")[0]
    d = leer_datos(senado.descargar(f"{APP}datos_proy&nboletin={num}"))
    if not d["proyid"] or not d["titulo"]:
        return None
    pid = d.pop("proyid")
    b = d["boletin"] or boletin
    get = lambda ac: senado.descargar(f"{APP}{ac}&proyid={pid}")  # noqa: E731
    tramites = leer_tramites(get("tramites"))
    if not tramites:
        return None
    previo = previo or {}
    f = {
        **d, "boletin": b,
        "estado": leer_estado(senado.descargar(f"{APP}boletin_x_fecha&desde=0&hasta=0&boletin={b}"), b),
        "link_mensaje_mocion": senado._link(f"https://tramitacion.senado.cl/appsenado/index.php?mo=tramitacion&ac=getDocto&iddocto={pid}&tipodoc=mensaje_mocion"),
        # el sitio lista solo a los autores principales; el servicio web incluía también a quienes adhieren
        "autores": (previo.get("autoria", "").split("; ") if previo.get("iniciativa") == "Moción" and previo.get("autoria")
                    else leer_autores(get("autores"))),
        "urgencias": leer_urgencias(get("urgencias")),
        "tramites": tramites,
        "informes": leer_informes(get("informes")),
        "comparados": leer_comparados(get("comparados")),
        "boletines_indicaciones": leer_indicaciones(get("indicaciones")),
        # no disponibles en estas páginas: se conservan del último dato bueno
        "oficios": previo.get("oficios", []),
        "votaciones": [{k: v for k, v in x.items() if k != "por_partido"} for x in previo.get("votaciones", [])],
        "observaciones": ["Observaciones del Ejecutivo registradas"] if previo.get("veto") == "Sí" else [],
        "_fuente": "sitio",
    }
    indic = set()
    for t in f["tramites"]:
        if re.search(r"(Presidente de la Rep[uú]blica|Ejecutivo).{0,40}indicaci", t["descripcion"], re.I):
            indic.add(t["fecha"])
    f["indicaciones_ejecutivo"] = sorted(indic)
    return f
