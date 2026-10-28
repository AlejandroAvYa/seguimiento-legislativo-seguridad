# -*- coding: utf-8 -*-
"""Votaciones de la Sala de la Cámara de Diputadas y Diputados (servicio oficial de datos abiertos).

Servicio: https://opendata.camara.cl/camaradiputados/WServices/WSLegislativo.asmx
  retornarVotacionesXAnno?prmAnno=AAAA          votaciones del año (Id, Descripcion, Fecha, totales, Quorum, Resultado, Tipo)
  retornarVotacionDetalle?prmVotacionId=NNNN    detalle con el voto de cada diputado

La descripción de cada votación incluye el boletín ("Boletín N° 18341-25 …"), que se usa para cruzarla con el catálogo.
"""
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BASE = "https://opendata.camara.cl/camaradiputados/WServices/WSLegislativo.asmx"
UA = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"


def descargar(url, intentos=3, timeout=120):
    """El servicio a veces responde vacío cuando limita consultas: se reintenta con espera."""
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/xml"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                datos = r.read()
            if len(datos) < 200:
                raise ValueError("respuesta vacía (posible límite de consultas)")
            try:
                return datos.decode("utf-8")
            except UnicodeDecodeError:
                return datos.decode("windows-1252")
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise
            ultimo = e
        except Exception as e:  # noqa: BLE001
            ultimo = e
        time.sleep(3 * (i + 1))
    raise ultimo


def _limpiar(elem):
    """Quita el espacio de nombres de todas las etiquetas."""
    for e in elem.iter():
        if isinstance(e.tag, str) and "}" in e.tag:
            e.tag = e.tag.split("}", 1)[1]
    return elem


def _txt(elem, ruta):
    x = elem.find(ruta)
    return (x.text or "").strip() if x is not None and x.text else ""


def _int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def boletines_en(texto):
    """'Boletín N° 18.341-25 …' -> ['18341-25']"""
    t = (texto or "").replace(".", "")
    return sorted(set(re.findall(r"\b(\d{4,5}-\d{2})\b", t)))


def leer_votaciones(xml_texto):
    raiz = _limpiar(ET.fromstring(xml_texto))
    salida = []
    for v in raiz.iter("Votacion"):
        vid = _txt(v, "Id")
        if not vid:
            continue
        desc = _txt(v, "Descripcion")
        salida.append({
            "id": vid,
            "fecha": _txt(v, "Fecha")[:10],
            "hora": _txt(v, "Fecha")[11:16],
            "descripcion": re.sub(r"\s+", " ", desc),
            "boletines": boletines_en(desc),
            "si": _int(_txt(v, "TotalSi")), "no": _int(_txt(v, "TotalNo")),
            "abstencion": _int(_txt(v, "TotalAbstencion")), "dispensados": _int(_txt(v, "TotalDispensado")),
            "quorum": _txt(v, "Quorum"), "resultado": _txt(v, "Resultado"), "tipo": _txt(v, "Tipo"),
        })
    return salida


def leer_detalle(xml_texto):
    raiz = _limpiar(ET.fromstring(xml_texto))
    votos = []
    for voto in raiz.iter("Voto"):
        d = voto.find("Diputado")
        if d is None:
            continue
        nombre = " ".join(x for x in [_txt(d, "Nombre"), _txt(d, "ApellidoPaterno"), _txt(d, "ApellidoMaterno")] if x)
        votos.append({"diputado_id": _txt(d, "Id"), "diputado": nombre, "seleccion": _txt(voto, "OpcionVoto")})
    return votos


def votaciones_del_anno(anno):
    return leer_votaciones(descargar(f"{BASE}/retornarVotacionesXAnno?prmAnno={anno}"))


def detalle_votacion(vid):
    return leer_detalle(descargar(f"{BASE}/retornarVotacionDetalle?prmVotacionId={vid}"))
