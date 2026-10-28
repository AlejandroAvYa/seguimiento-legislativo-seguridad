# -*- coding: utf-8 -*-
"""Agenda legislativa: citaciones de comisiones, tabla de Sala y plazos de indicaciones.

Fuentes (sitio de tramitación del Senado, accesible desde GitHub):
  citaciones   https://tramitacion.senado.cl/appsenado/index.php?mo=comisiones&ac=citacionesComision&tipo_consulta=1
  tabla Sala   https://tramitacion.senado.cl/appsenado/index.php?mo=sesionessala&ac=doctosSesion&tipo=27
  plazos       https://tramitacion.senado.cl/appsenado/index.php?mo=sesionessala&ac=plazosIndicaciones
Cámara (datos abiertos): sesiones citadas de Sala y de comisiones, con fecha y hora. La Cámara no publica en
datos abiertos la materia ni los invitados de sus citaciones; esa página (camara.cl) bloquea consultas desde
servidores fuera de Chile.
"""
import html
import re
import time
import urllib.error
import urllib.request

BASE = "https://tramitacion.senado.cl/appsenado/index.php"
UA = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"
MESES = {m: i + 1 for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                                          "septiembre", "octubre", "noviembre", "diciembre"])}


def descargar(url, intentos=3, timeout=60):
    ultimo = None
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise
            ultimo = e
        except Exception as e:  # noqa: BLE001
            ultimo = e
        time.sleep(3 * (i + 1))
    raise ultimo


def texto(fragmento):
    t = re.sub(r"(?i)<br\s*/?>", "\n", fragmento or "")
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def fecha_larga(t):
    """'Miércoles, 28 de Octubre de 2026' -> '2026-10-28'"""
    m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+(\d{4})", t or "")
    if not m or m.group(2).lower() not in MESES:
        return ""
    return f"{m.group(3)}-{MESES[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def boletines(t):
    """'Boletín N° 18.551-04', 'Bol.N° 17974-15' -> ['18551-04', '17974-15']"""
    vistos = []
    for b in re.findall(r"(?<![\d.])(\d{1,2}\.?\d{3}-\d{2})(?!\d)", t or ""):
        b = b.replace(".", "")
        if b not in vistos:
            vistos.append(b)
    return vistos


def invitados(t):
    """Oraciones que mencionan invitados a la sesión."""
    frases = re.split(r"(?<=\.)\s+(?=[A-ZÁÉÍÓÚÑ])|\n", t or "")
    salida = []
    for f in frases:
        f = f.strip()
        if re.search(r"invitad", f, re.I) and len(f) > 20 and f not in salida:
            salida.append(f)
    return salida


def leer_citaciones(pagina):
    salida = []
    for art in re.findall(r"(?is)<article>(.*?)</article>", pagina):
        mf = re.search(r'(?is)<h1 class="titular[^"]*">(.*?)</h1>', art)
        fecha = fecha_larga(texto(mf.group(1))) if mf else ""
        if not fecha:
            continue
        for tabla in re.findall(r"(?is)<table[^>]*>(.*?)</table>", art):
            filas = {}
            for th, td in re.findall(r"(?is)<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", tabla):
                filas[texto(th).rstrip(":").upper()] = td
            if not any(k.startswith("COMISI") for k in filas):
                continue
            cel = next(v for k, v in filas.items() if k.startswith("COMISI"))
            nombre = texto((re.search(r"(?is)<strong>(.*?)</strong>", cel) or re.search(r"(?s)(.*)", cel)).group(1))
            aviso = texto((re.search(r"(?is)<label[^>]*>(.*?)</label>", cel) or re.search(r"()", "")).group(1)).strip("- ").strip()
            materia = texto(filas.get("MATERIA", ""))
            salida.append({
                "camara": "Senado", "tipo": "Comisión", "fecha": fecha,
                "instancia": ("Comisión " + nombre) if nombre.lower().startswith("de ") else nombre,
                "estado": "Suspendida" if re.search(r"sin efecto|suspend", aviso, re.I) else "Citada",
                "aviso": aviso, "lugar": texto(filas.get("LUGAR", "")), "horario": texto(filas.get("HORARIO", "")),
                "materia": materia, "boletines": boletines(materia), "invitados": invitados(materia),
            })
    return salida


def citaciones_senado():
    return leer_citaciones(descargar(f"{BASE}?mo=comisiones&ac=citacionesComision&tipo_consulta=1"))


def leer_listado_tabla(pagina):
    """Sesiones de Sala con tabla publicada: número, tipo, fecha, horario e iddocto."""
    salida = []
    for fila in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pagina):
        m = re.search(r"getDoctoSesion&(?:amp;)?iddocto=(\d+)", fila)
        if not m:
            continue
        celdas = [texto(c) for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", fila)]
        txt = " ".join(celdas)
        mh = re.search(r"de (\d{1,2}:\d{2})\s+a\s+(\d{1,2}:\d{2})", txt)
        salida.append({"iddocto": m.group(1), "numero": celdas[0] if celdas else "", "tipo_sesion": celdas[2] if len(celdas) > 2 else "",
                       "fecha": fecha_larga(txt), "horario": f"{mh.group(1)} a {mh.group(2)}" if mh else ""})
    return salida


def tabla_sala_senado():
    lista = leer_listado_tabla(descargar(f"{BASE}?mo=sesionessala&ac=doctosSesion&tipo=27"))
    salida = []
    for s in lista:
        pag = descargar(f"{BASE}?mo=sesionessala&ac=getDoctoSesion&iddocto={s['iddocto']}")
        cuerpo = re.search(r'(?is)<div id="main">(.*)', pag)
        t = texto(cuerpo.group(1) if cuerpo else pag)
        t = t.split("Avenida Pedro Montt")[0]
        t = re.sub(r"(?s)^.*?(?=Circular|TABLA|Tabla|Sesi[oó]n)", "", t, count=1)
        salida.append({"camara": "Senado", "tipo": "Sala", "fecha": s["fecha"], "instancia": f"Sala del Senado · sesión {s['tipo_sesion'].lower()} N° {s['numero']}".replace("  ", " "),
                       "estado": "Citada", "horario": s["horario"], "lugar": "", "materia": t[:6000], "boletines": boletines(t),
                       "invitados": [], "link": f"{BASE}?mo=sesionessala&ac=getDoctoSesion&iddocto={s['iddocto']}"})
    return salida


def leer_plazos(pagina):
    salida, secretaria = [], "Secretaría del Senado"
    cuerpo = pagina.split("Plazos de Indicaciones", 1)[-1]
    for fila in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", cuerpo):
        celdas = [texto(c) for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", fila)]
        txt = " ".join(celdas)
        if re.match(r"(?i)\s*para presentar", txt):
            secretaria = nombre_secretaria(txt)
            continue
        bs = boletines(celdas[0] if celdas else "")
        f = fecha_larga(txt)
        if bs and f:
            mh = re.search(r"\b(\d{1,2}:\d{2})\b", txt)
            salida.append({"boletin": bs[0], "materia": celdas[1] if len(celdas) > 1 else "", "fecha": f,
                           "hora": mh.group(1) if mh else "", "donde": secretaria})
    return salida


def nombre_secretaria(t):
    """'PARA PRESENTAR EN SECRETARÍA DE LA COMISIÓN DE ECONOMíA' -> 'Secretaría de la Comisión de Economía'"""
    t = re.sub(r"(?i)^\s*para presentar en\s+", "", t.strip()).lower()
    menores = {"de", "la", "el", "los", "las", "y", "e", "en", "del", "para", "a"}
    palabras = [w if (w in menores and i) else w[:1].upper() + w[1:] for i, w in enumerate(t.split())]
    t = " ".join(palabras)
    return t if t != "Secretaría" else "Secretaría del Senado"


def plazos_indicaciones_senado():
    return leer_plazos(descargar(f"{BASE}?mo=sesionessala&ac=plazosIndicaciones"))


# ----------------------------------------------------------------- integración
def clave(x):
    return "|".join([x.get("camara", ""), x.get("tipo", ""), x.get("fecha", ""), x.get("instancia", ""), x.get("horario", "")])


def lunes_de(hoy):
    from datetime import datetime, timedelta
    d = datetime.strptime(hoy, "%Y-%m-%d")
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def actualizar(previa, seguidos, hoy, sesiones_camara=None):
    """Arma la agenda desde el lunes de esta semana en adelante.

    previa: agenda anterior (se conservan los días ya pasados de la semana, que el Senado deja de publicar).
    seguidos: boletines del catálogo. sesiones_camara: función opcional que devuelve sesiones de Sala de la Cámara.
    Devuelve (agenda, estados por fuente, citaciones nuevas de proyectos seguidos).
    """
    lunes = lunes_de(hoy)
    items, estados, plazos = [], {}, previa.get("plazos_indicaciones", [])
    fuentes = [("senado_citaciones", citaciones_senado), ("senado_sala", tabla_sala_senado)]
    if sesiones_camara:
        fuentes.append(("camara_sala", sesiones_camara))
    consultadas = set()
    for nombre, f in fuentes:
        try:
            nuevos = f()
            items += nuevos
            consultadas.add(nombre)
            estados[nombre] = {"estado": "ok", "n": len(nuevos)}
        except Exception as e:  # noqa: BLE001
            estados[nombre] = {"estado": f"sin conexión: {type(e).__name__}"[:80]}
    try:
        plazos = plazos_indicaciones_senado()
        estados["senado_plazos"] = {"estado": "ok", "n": len(plazos)}
    except Exception as e:  # noqa: BLE001
        estados["senado_plazos"] = {"estado": f"sin conexión: {type(e).__name__}"[:80]}
    origen = {"senado_citaciones": ("Senado", "Comisión"), "senado_sala": ("Senado", "Sala"), "camara_sala": ("Cámara de Diputados", "Sala")}
    nuevas_claves = {clave(x) for x in items}
    for x in previa.get("items", []):
        fuente = next((k for k, v in origen.items() if v == (x.get("camara"), x.get("tipo"))), "")
        # días ya pasados de esta semana, o todo lo anterior si la fuente no respondió
        if x.get("fecha", "") >= lunes and clave(x) not in nuevas_claves and (x["fecha"] < hoy or fuente not in consultadas):
            items.append(x)
    items = [x for x in items if x.get("fecha", "") >= lunes]
    for x in items:
        x["seguidos"] = [b for b in x.get("boletines", []) if b in seguidos]
    items.sort(key=lambda x: (x["fecha"], x.get("horario", ""), x.get("camara", ""), x.get("instancia", "")))
    previas = {clave(x) for x in previa.get("items", [])}
    nuevas = [x for x in items if x["seguidos"] and x["fecha"] >= hoy and clave(x) not in previas and x.get("estado") != "Suspendida"]
    plazos = [p for p in plazos if p.get("fecha", "") >= hoy]
    for p in plazos:
        p["seguido"] = p["boletin"] in seguidos
    return {"desde": lunes, "items": items, "plazos_indicaciones": plazos}, estados, nuevas


def agenda_de(boletin, agenda):
    """Sesiones de la semana y plazos de indicaciones de un proyecto."""
    ses = [{k: x.get(k, "") for k in ("fecha", "horario", "camara", "tipo", "instancia", "estado", "lugar")}
           for x in agenda.get("items", []) if boletin in x.get("boletines", [])]
    plz = [{k: p[k] for k in ("fecha", "hora", "donde")} for p in agenda.get("plazos_indicaciones", []) if p["boletin"] == boletin]
    return ses, plz
