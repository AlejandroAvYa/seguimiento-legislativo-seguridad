# -*- coding: utf-8 -*-
"""Consulta y lectura del servicio web oficial de tramitación del Senado.

Servicio: https://tramitacion.senado.cl/wspublico/tramitacion.php
  ?boletin=NNNNN        ficha completa de un proyecto (cubre ambas cámaras)
  ?fecha=DD/MM/AAAA     proyectos con movimiento desde esa fecha (máximo ~4 semanas atrás)
"""
import html
import re
import time
import urllib.error
import urllib.request
from datetime import datetime

BASE = "https://tramitacion.senado.cl/wspublico/tramitacion.php"
# Solo ASCII: el servidor del Senado rechaza (403) el agente por defecto de Python y caracteres no ASCII.
UA = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"


def descargar(url, intentos=4, timeout=60):
    """GET con reintentos y espera creciente. Devuelve el texto o lanza la última excepción."""
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise                      # error permanente: no reintentar
            ultimo = e
            time.sleep(2 * (i + 1))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            ultimo = e
            time.sleep(2 * (i + 1))
    raise ultimo


def _tag(bloque, t):
    m = re.search(r"<%s>(.*?)</%s>" % (t, t), bloque, re.S)
    return html.unescape(m.group(1).strip()) if m else ""


def _items(bloque, seccion, item):
    m = re.search(r"<%s>(.*?)</%s>" % (seccion, seccion), bloque, re.S)
    return re.findall(r"<%s>(.*?)</%s>" % (item, item), m.group(1), re.S) if m else []


def _link(url):
    """Los documentos se descargan desde tramitacion.senado.cl (www.senado.cl bloquea consultas automáticas)."""
    url = url.replace("&amp;", "&").strip()
    return re.sub(r"^https?://(www\.)?senado\.cl/appsenado/", "https://tramitacion.senado.cl/appsenado/", url)


def _num(s):
    try:
        return int(s)
    except ValueError:
        return None


def fecha_iso(s):
    """'12/06/2026' -> '2026-06-12'. Si no es una fecha válida, devuelve el texto original."""
    s = (s or "").strip()
    try:
        return datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return s


def leer_xml(texto):
    """Convierte la respuesta XML del Senado en una lista de diccionarios (uno por proyecto)."""
    proyectos = []
    for p in re.findall(r"<proyecto>(.*?)</proyecto>", texto, re.S):
        d = {k: _tag(p, k) for k in [
            "boletin", "titulo", "fecha_ingreso", "iniciativa", "camara_origen", "urgencia_actual",
            "etapa", "subetapa", "estado", "leynro", "diariooficial", "refundidos", "link_mensaje_mocion"]}
        if not d["boletin"]:
            continue
        d["autores"] = [re.sub(r"\s+", " ", html.unescape(a.strip())) for a in re.findall(r"<PARLAMENTARIO>(.*?)</PARLAMENTARIO>", p, re.S)]
        d["urgencias"] = [{
            "tipo": _tag(u, "TIPO"), "ingreso": fecha_iso(_tag(u, "FECHAINGRESO")), "retiro": fecha_iso(_tag(u, "FECHARETIRO")),
            "camara": _tag(u, "CAMARAINGRESO"), "mensaje": _tag(u, "MENSAJEINGRESO")}
            for u in re.findall(r"<urgencia>(.*?)</urgencia>", p, re.S)]
        d["tramites"] = [{
            "fecha": fecha_iso(_tag(t, "FECHA")), "sesion": _tag(t, "SESION"),
            "descripcion": re.sub(r"\s+", " ", _tag(t, "DESCRIPCIONTRAMITE")).strip(),
            "etapa": _tag(t, "ETAPDESCRIPCION"), "camara": _tag(t, "CAMARATRAMITE")}
            for t in re.findall(r"<tramite>(.*?)</tramite>", p, re.S)]
        indic = set()
        for b in re.findall(r"<tramite>(.*?)</tramite>", p, re.S) + re.findall(r"<oficio>(.*?)</oficio>", p, re.S):
            txt = _tag(b, "DESCRIPCIONTRAMITE") or _tag(b, "DESCRIPCION")
            if re.search(r"(Presidente de la Rep[uú]blica|Ejecutivo).{0,40}indicaci", txt, re.I):
                indic.add(fecha_iso(_tag(b, "FECHA")))
        d["indicaciones_ejecutivo"] = sorted(indic)
        d["link_mensaje_mocion"] = _link(d["link_mensaje_mocion"])
        d["informes"] = [{
            "fecha": fecha_iso(_tag(x, "FECHAINFORME")), "tramite": re.sub(r"\s+", " ", _tag(x, "TRAMITE")).strip(),
            "etapa": _tag(x, "ETAPA"), "link": _link(_tag(x, "LINK_INFORME"))}
            for x in _items(p, "informes", "informe")]
        d["comparados"] = [{"descripcion": re.sub(r"\s+", " ", _tag(x, "COMPARADO")).strip(), "link": _link(_tag(x, "LINK_COMPARADO"))}
                           for x in _items(p, "comparados", "comparado")]
        d["oficios"] = [{
            "numero": _tag(x, "NUMERO"), "fecha": fecha_iso(_tag(x, "FECHA")), "tramite": _tag(x, "TRAMITE"), "etapa": _tag(x, "ETAPA"),
            "tipo": _tag(x, "TIPO"), "camara": _tag(x, "CAMARA"), "descripcion": re.sub(r"\s+", " ", _tag(x, "DESCRIPCION")).strip(),
            "link": _link(_tag(x, "LINK_OFICIO"))}
            for x in _items(p, "oficios", "oficio")]
        d["boletines_indicaciones"] = [{
            "fecha": fecha_iso(_tag(x, "FECHA")), "tramite": _tag(x, "TRAMITE"), "etapa": _tag(x, "ETAPA"),
            "link": _link(_tag(x, "LINK_INDICACION")),
            "iddocto": (re.search(r"iddocto=(\d+)", _tag(x, "LINK_INDICACION")) or [None, ""])[1]}
            for x in _items(p, "indicaciones", "indicacion")]
        d["votaciones"] = []
        for x in _items(p, "votaciones", "votacion"):
            votos = [{"parlamentario": re.sub(r"\s+", " ", _tag(v, "PARLAMENTARIO")).strip(), "seleccion": _tag(v, "SELECCION")}
                     for v in re.findall(r"<VOTO>(.*?)</VOTO>", x, re.S)]
            tema = re.sub(r"\s+", " ", _tag(x, "TEMA")).strip()
            res = re.search(r"\b(APROBAD[OA]S?|RECHAZAD[OA]S?)\b", tema.upper())
            d["votaciones"].append({
                "fecha": fecha_iso(_tag(x, "FECHA")), "sesion": _tag(x, "SESION"), "tipo": _tag(x, "TIPOVOTACION"),
                "etapa": _tag(x, "ETAPA"), "quorum": _tag(x, "QUORUM"), "si": _num(_tag(x, "SI")), "no": _num(_tag(x, "NO")),
                "abstencion": _num(_tag(x, "ABSTENCION")), "pareo": _num(_tag(x, "PAREO")),
                "resultado": res.group(1).capitalize() if res else "", "tema": tema, "votos": votos})
        d["observaciones"] = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()
                              for x in _items(p, "observaciones", "observacion")]
        proyectos.append(d)
    return proyectos


def ficha(boletin):
    """Ficha de un boletín ('18341-25' o '18341'). Devuelve dict o None si el Senado no lo informa."""
    num = boletin.split("-")[0]
    lista = leer_xml(descargar(f"{BASE}?boletin={num}"))
    for p in lista:
        if p["boletin"] == boletin or "-" not in boletin:
            return p
    return lista[0] if lista else None


def con_movimiento_desde(fecha_ddmmaaaa):
    """Proyectos con algún movimiento desde la fecha indicada."""
    texto = descargar(f"{BASE}?fecha={fecha_ddmmaaaa}", timeout=180)
    if "<proyectos" not in texto:
        raise ValueError("Respuesta no válida del Senado: " + re.sub(r"<[^>]+>", " ", texto)[:200])
    return leer_xml(texto)


def documento(url):
    """Descarga un documento (bytes) desde tramitacion.senado.cl."""
    req = urllib.request.Request(_link(url), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()
