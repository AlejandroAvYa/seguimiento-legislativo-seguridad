# -*- coding: utf-8 -*-
"""Partido de cada parlamentario y composición de las comisiones del Senado.

Fuentes oficiales:
  Senado   https://tramitacion.senado.cl/wspublico/senadores_vigentes.php  (partido actual de cada senador)
           https://tramitacion.senado.cl/wspublico/comisiones.php          (integrantes de cada comisión)
  Cámara   https://opendata.camara.cl/.../WSDiputado.asmx/retornarDiputados (militancias con fechas)
"""
import re
import unicodedata
import xml.etree.ElementTree as ET

import camara
import senado

SIN_DATO = "Sin información de partido"


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", t).split()


def _xml(texto):
    return ET.fromstring(re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", texto, count=0).encode("utf-8"))


def _t(e, ruta):
    x = e.find(ruta)
    return (x.text or "").strip() if x is not None and x.text else ""


def senadores():
    """Senadores en ejercicio con su partido (listado del sitio de tramitación del Senado, completo)."""
    import html as _html
    pag = senado.descargar("https://tramitacion.senado.cl/appsenado/index.php?mo=senadores&ac=listado")
    cuerpo = pag.split("Visita el Senado", 1)[-1]
    txt = _html.unescape(re.sub(r"<[^>]+>", "\n", re.sub(r"(?is)<script.*?</script>", "", cuerpo)))
    txt = re.sub(r"[ \t]+", " ", txt)
    salida = []
    for m in re.finditer(r"\n\s*([^\n,]{3,60}),\s*([^\n]{2,60})\n\s*Regi[oó]n:(.*?)Partido:\s*\n?\s*([^\n]+)", txt, re.S):
        salida.append({"apellidos": m.group(1).strip(), "nombre": m.group(2).strip(), "partido": m.group(4).strip() or SIN_DATO})
    return salida


def comisiones_senado():
    raiz = _xml(senado.descargar("https://tramitacion.senado.cl/wspublico/comisiones.php"))
    salida = []
    for c in raiz.iter("comision"):
        salida.append({"id": _t(c, "id"), "nombre": _t(c, "nombre"), "tipo": _t(c, "tipo"),
                       "integrantes": [{"id": _t(i, "PARLID"), "nombre": f"{_t(i, 'NOMBRE')} {_t(i, 'APELLIDO_PATERNO')} {_t(i, 'APELLIDO_MATERNO')}".strip(),
                                        "funcion": _t(i, "FUNCION")} for i in c.iter("integrante")]})
    return salida


def diputados():
    """Id -> nombre y militancias [(inicio, termino, partido)] de todos los diputados."""
    raiz = _xml(camara.descargar(f"{camara.BASE.replace('WSLegislativo', 'WSDiputado')}/retornarDiputados"))
    salida = {}
    for d in raiz.iter("Diputado"):
        did = _t(d, "Id")
        if not did:
            continue
        mil = []
        for m in d.iter("Militancia"):
            p = m.find("Partido")
            nombre = (_t(p, "Alias") or _t(p, "Nombre")) if p is not None else ""
            mil.append([_t(m, "FechaInicio")[:10], _t(m, "FechaTermino")[:10], nombre])
        salida[did] = {"nombre": f"{_t(d, 'Nombre')} {_t(d, 'ApellidoPaterno')} {_t(d, 'ApellidoMaterno')}".strip(), "militancias": mil}
    return salida


def partido_diputado(info, fecha):
    """Partido vigente en la fecha de la votación (o el último conocido)."""
    if not info or not info.get("militancias"):
        return SIN_DATO
    mil = sorted(info["militancias"], key=lambda m: m[0] or "")
    for ini, fin, p in mil:
        if (not ini or ini <= fecha) and (not fin or fin >= fecha) and p:
            return p
    return mil[-1][2] or SIN_DATO


def indice_senadores(lista):
    return [(norm(s["apellidos"]), norm(s["nombre"]), s) for s in lista]


def senador_de_voto(nombre, idx):
    """Cruza 'De Rementería V., Tomás' con 'De Rementería Venegas, Tomás'."""
    m = re.match(r"^\s*(.+?)\s*,\s*(.+)$", nombre or "")
    if not m:
        return None
    ap = norm(m.group(1).replace(".", " "))
    nom = norm(m.group(2))
    if not ap or not nom:
        return None
    ini = ap[-1] if len(ap[-1]) == 1 else ""
    pat = ap[:-1] if ini else ap
    for aps, noms, s in idx:
        if aps[:len(pat)] == pat and noms and noms[0] == nom[0]:
            if not ini or (len(aps) > len(pat) and aps[len(pat)].startswith(ini)):
                return s
    return None


def por_partido(votos, partido_de):
    """Votos de una votación agrupados por partido: [{partido, si, no, abstencion, otros}]."""
    res = {}
    for v in votos:
        p = partido_de(v) or SIN_DATO
        d = res.setdefault(p, {"partido": p, "si": 0, "no": 0, "abstencion": 0, "otros": 0})
        s = (v.get("seleccion") or "").lower()
        if s.startswith("no vota") or s.startswith("pareo") or s.startswith("dispens"):
            clave = "otros"
        else:
            clave = "si" if s.startswith(("si", "sí", "afirm")) else "no" if s.startswith(("no", "en contra")) else "abstencion" if s.startswith("abst") else "otros"
        d[clave] += 1
    return sorted(res.values(), key=lambda d: (d["partido"] == SIN_DATO, -(d["si"] + d["no"] + d["abstencion"] + d["otros"]), d["partido"]))


def comision_de(instancia, comisiones):
    """Busca en las comisiones del Senado la que corresponde a 'Comisión de Constitución, ...'."""
    objetivo = " ".join(norm(re.sub(r"^Comisi[oó]n\s+(de\s+)?", "", instancia or "", flags=re.I)))
    if not objetivo:
        return None
    for c in comisiones:
        nombre = " ".join(norm(re.sub(r"^(Comisi[oó]n\s+)?(de\s+)?", "", c["nombre"], flags=re.I)))
        if nombre and (nombre == objetivo or nombre.startswith(objetivo) or objetivo.startswith(nombre)):
            return c
    return None
