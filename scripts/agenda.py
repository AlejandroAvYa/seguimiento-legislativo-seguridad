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
    m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚáéíóú]+)\s+de\s+(\d{4})", t or "", re.I)
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
    """Identifica una sesión. En Sala basta el número de sesión (el texto de la instancia puede variar)."""
    m = re.search(r"N° (\d+)", x.get("instancia", "")) if x.get("tipo") == "Sala" else None
    ident = m.group(1) if m else x.get("instancia", "") + "|" + x.get("horario", "")
    return "|".join([x.get("camara", ""), x.get("tipo", ""), x.get("fecha", ""), ident])


def lunes_de(hoy):
    from datetime import datetime, timedelta
    d = datetime.strptime(hoy, "%Y-%m-%d")
    return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")


def actualizar(previa, seguidos, hoy, sesiones_camara=None, citaciones_camara=None):
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
    if citaciones_camara is not None:            # leídas en un computador en Chile (data/citaciones_camara.json)
        items += citaciones_camara
        consultadas.add("camara_comisiones")
    origen = {"senado_citaciones": ("Senado", "Comisión"), "senado_sala": ("Senado", "Sala"), "camara_sala": ("Cámara de Diputados", "Sala"),
              "camara_comisiones": ("Cámara de Diputados", "Comisión")}
    nuevas_claves = {clave(x) for x in items}
    for x in previa.get("items", []):
        fuente = next((k for k, v in origen.items() if v == (x.get("camara"), x.get("tipo"))), "")
        # días ya pasados de esta semana, o todo lo anterior si la fuente no respondió
        if x.get("fecha", "") >= lunes and clave(x) not in nuevas_claves and (x["fecha"] < hoy or fuente not in consultadas):
            items.append(x)
    items = [x for x in items if x.get("fecha", "") >= lunes]
    unicos = {}
    for x in items:                       # sin duplicados: prevalece la versión más reciente (la primera)
        unicos.setdefault(clave(x), x)
    items = list(unicos.values())
    for x in items:
        x["seguidos"] = [b for b in x.get("boletines", []) if b in seguidos]
    items.sort(key=lambda x: (x["fecha"], x.get("horario", ""), x.get("camara", ""), x.get("instancia", "")))
    previas = {clave(x) for x in previa.get("items", [])}
    nuevas = [x for x in items if x["seguidos"] and x["fecha"] >= hoy and clave(x) not in previas and x.get("estado") != "Suspendida"]
    plazos = [p for p in plazos if p.get("fecha", "") >= hoy]
    for p in plazos:
        p["seguido"] = p["boletin"] in seguidos
    notas = previa.get("noticias_camara", [])
    try:
        notas = acumular_noticias(notas, noticias_camara(), hoy)
        estados["camara_prensa"] = {"estado": "ok", "n": len(notas)}
    except Exception as e:  # noqa: BLE001
        estados["camara_prensa"] = {"estado": f"sin conexión: {type(e).__name__}"[:80]}
    for n in notas:
        n["seguidos"] = [b for b in n.get("boletines", []) if b in seguidos]
    return {"desde": lunes, "items": items, "plazos_indicaciones": plazos, "noticias_camara": notas}, estados, nuevas


def agenda_de(boletin, agenda):
    """Sesiones de la semana y plazos de indicaciones de un proyecto."""
    ses = [{k: x.get(k, "") for k in ("fecha", "horario", "camara", "tipo", "instancia", "estado", "lugar")}
           for x in agenda.get("items", []) if boletin in x.get("boletines", [])]
    plz = [{k: p[k] for k in ("fecha", "hora", "donde")} for p in agenda.get("plazos_indicaciones", []) if p["boletin"] == boletin]
    return ses, plz


# ----------------------------------------------------------------- Cámara: notas de prensa (feed RSS)
FEEDS_CAMARA = ["https://www.camara.cl/cms/feed/?s=tabla", "https://www.camara.cl/cms/feed/?s=comisi%C3%B3n", "https://www.camara.cl/cms/feed/"]
DIAS_SEM = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}


def leer_feed(xml):
    """Notas del feed de prensa de la Cámara: título, enlace, fecha, categorías y resumen."""
    from email.utils import parsedate_to_datetime
    salida = []
    for it in re.findall(r"(?s)<item>(.*?)</item>", xml):
        def campo(etq):
            m = re.search(rf"(?s)<{etq}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{etq}>", it)
            return html.unescape(m.group(1)).strip() if m else ""
        cats = [html.unescape(c) for c in re.findall(r"<category><!\[CDATA\[(.*?)\]\]>", it)]
        try:
            fecha = parsedate_to_datetime(campo("pubDate")).astimezone().strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            fecha = ""
        resumen = re.sub(r"\s+", " ", texto(campo("description"))).replace("[…]", "…").strip()
        titulo = texto(campo("title"))
        # nota que anuncia la tabla: menciona la tabla, o los temas de la Sala de "este lunes"/"esta semana", sin informar lo ya despachado
        anuncia = re.search(r"\btabla\b", titulo + " " + " ".join(cats), re.I) or re.search(r"temas de la Sala|(?:este|el) (?:lunes|martes|miércoles)", titulo, re.I)
        es_tabla = bool(anuncia) and ("#Sala" in cats or re.search(r"\bSala\b", titulo)) and not re.search(r"despach|aprob", titulo, re.I)
        tipo = "Tabla de la Sala" if es_tabla else ("Comisión" if "#Comisión" in cats or re.search(r"[Cc]omisi[oó]n", titulo) else
                                                    ("Sala" if "#Sala" in cats else "Otra"))
        salida.append({"fecha": fecha, "titulo": titulo, "link": campo("link"), "tipo": tipo, "resumen": resumen[:700],
                       "temas": [c for c in cats if c not in ("Destacado Centro Prensa", "Noticias Centro de Prensa", "Noticias Destacadas",
                                                              "Portada Multimedia Inicio Web", "#Sala", "#Comisión")][:6],
                       "boletines": boletines(titulo + " " + resumen)})
    return salida


def noticias_camara():
    vistos, salida = set(), []
    for u in FEEDS_CAMARA:
        for n in leer_feed(descargar(u)):
            if n["link"] and n["link"] not in vistos and n["tipo"] in ("Tabla de la Sala", "Comisión", "Sala"):
                vistos.add(n["link"])
                salida.append(n)
    return salida


def acumular_noticias(previas, nuevas, hoy, dias=21):
    """El feed solo trae las últimas notas: se acumulan las de las últimas semanas."""
    from datetime import datetime, timedelta
    desde = (datetime.strptime(hoy, "%Y-%m-%d") - timedelta(days=dias)).strftime("%Y-%m-%d")
    por_link = {n["link"]: n for n in previas}
    por_link.update({n["link"]: n for n in nuevas})
    return sorted([n for n in por_link.values() if n.get("fecha", "") >= desde], key=lambda n: n["fecha"], reverse=True)


# ----------------------------------------------------------------- calendario legislativo
def senado_sesiones_sala():
    """Sesiones de Sala del Senado de la legislatura en curso (fecha y tipo)."""
    # la página de cualquier legislatura trae el selector; la primera opción es la legislatura en curso
    pag = descargar(f"{BASE}?mo=sesionessala&listado=1&ac=listado&legi=504")
    m = re.search(r'<option\s+value="(\d+)"\s*>\s*\d{3}\s*\(', pag)
    if m and m.group(1) != "504":
        pag = descargar(f"{BASE}?mo=sesionessala&listado=1&ac=listado&legi={m.group(1)}")
    salida = []
    for fila in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", pag):
        c = [texto(x) for x in re.findall(r"(?is)<td[^>]*>(.*?)</td>", fila)]
        if len(c) >= 3 and fecha_larga(c[2]):
            salida.append({"numero": c[0], "tipo": c[1], "fecha": fecha_larga(c[2])})
    return salida


def feriados(anno):
    """Feriados legales: API de Gobierno Digital; si no responde, api.boostr.cl."""
    import json as _json
    try:
        datos = _json.loads(descargar(f"https://apis.digital.gob.cl/fl/feriados/{anno}", intentos=2, timeout=30))
        return [{"fecha": d["fecha"], "nombre": d["nombre"], "fuente": "apis.digital.gob.cl"} for d in datos]
    except Exception:  # noqa: BLE001
        datos = _json.loads(descargar(f"https://api.boostr.cl/holidays/{anno}.json", intentos=2, timeout=30))
        return [{"fecha": d["date"], "nombre": d["title"], "fuente": "api.boostr.cl"} for d in datos.get("data", [])]


def calendario(hoy, camara_sesiones, senado_sesiones, agenda, proyectos, lista_feriados, atras=8, adelante=4):
    """Semana a semana: sesiones de Sala de cada cámara, citaciones, feriados y urgencias que vencen."""
    from datetime import datetime, timedelta
    lunes = datetime.strptime(lunes_de(hoy), "%Y-%m-%d")
    semanas = []
    for k in range(-atras, adelante + 1):
        ini = lunes + timedelta(weeks=k)
        fin = ini + timedelta(days=6)
        a, b = ini.strftime("%Y-%m-%d"), fin.strftime("%Y-%m-%d")
        en = lambda f: a <= (f or "") <= b  # noqa: E731
        cam = [s for s in camara_sesiones if en(s["fecha"])]
        sen = [s for s in senado_sesiones if en(s["fecha"])]
        sen_fut = [x for x in agenda.get("items", []) if x.get("camara") == "Senado" and x.get("tipo") == "Sala" and en(x["fecha"])]
        com = [x for x in agenda.get("items", []) if x.get("camara") == "Senado" and x.get("tipo") == "Comisión" and en(x["fecha"]) and x.get("estado") != "Suspendida"]
        com_c = [x for x in agenda.get("items", []) if x.get("camara") != "Senado" and x.get("tipo") == "Comisión" and en(x["fecha"]) and x.get("estado") != "Suspendida"]
        urg = [{"boletin": p["boletin"], "urgencia": p["urgencia_vigente"], "vence": p["urgencia_vence_estimado"]}
               for p in proyectos if p.get("situacion") == "En tramitación" and en(p.get("urgencia_vence_estimado"))]
        semanas.append({
            "desde": a, "hasta": b, "pasada": b < hoy, "actual": a <= hoy <= b,
            "camara_sala": len(cam), "camara_dias": sorted({s["fecha"] for s in cam}),
            "senado_sala": max(len(sen), len({x["instancia"] for x in sen_fut})), "senado_dias": sorted({s["fecha"] for s in sen} | {x["fecha"] for x in sen_fut}),
            "senado_comisiones": len(com), "senado_comisiones_seguidos": sum(1 for x in com if x.get("seguidos")),
            "camara_comisiones": len(com_c), "camara_comisiones_seguidos": sum(1 for x in com_c if x.get("seguidos")),
            "feriados": [f for f in lista_feriados if en(f["fecha"])],
            "urgencias_vencen": urg,
        })
    return semanas
