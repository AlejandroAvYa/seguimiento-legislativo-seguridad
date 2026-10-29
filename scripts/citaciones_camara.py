# -*- coding: utf-8 -*-
"""Citaciones de comisiones de la Cámara de Diputadas y Diputados (camara.cl).

camara.cl exige una verificación de navegador que rechaza servidores fuera de Chile, por lo que este script
se ejecuta en un computador en Chile (runner propio de GitHub, ver README). Escribe data/citaciones_camara.json,
que la actualización horaria incorpora a la agenda.

Uso:  python scripts/citaciones_camara.py            semana actual y siguiente
      python scripts/citaciones_camara.py --archivo pagina.html   (prueba con una página guardada)

Página: https://www.camara.cl/legislacion/comisiones/citaciones_semana.aspx?prmSemana=AAAA-SS
Estructura: article.citaciones > p.fecha (día) + table.tabla > filas con comisión | horario | sala |
            celda con una tabla interna: td.w40 (objeto de la citación) y td.w30 (invitados).
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agenda import boletines, fecha_larga  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "data", "citaciones_camara.json")
URL = "https://www.camara.cl/legislacion/comisiones/citaciones_semana.aspx?prmSemana={}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def texto(fragmento):
    t = re.sub(r"(?i)<br\s*/?>", "\n", fragmento or "")
    t = html_mod.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\s*\n\s*", "\n", t).strip()


def _celdas(fila):
    """Celdas de primer nivel de una fila (respeta las tablas internas)."""
    celdas, prof, inicio, i = [], 0, None, 0
    for m in re.finditer(r"(?is)<(/?)(td|table)\b[^>]*>", fila):
        cierre, tag = m.group(1) == "/", m.group(2).lower()
        if tag == "table":
            prof += -1 if cierre else 1
        elif prof == 0:
            if not cierre:
                inicio = m
            elif inicio is not None:
                celdas.append((inicio.group(0), fila[inicio.end():m.start()]))
                inicio = None
        i = m.end()
    return celdas


def _filas(tabla):
    """Filas de primer nivel de la tabla principal."""
    cuerpo = re.search(r"(?is)<tbody[^>]*>(.*)</tbody>", tabla)
    cuerpo = cuerpo.group(1) if cuerpo else tabla
    filas, prof, inicio = [], 0, None
    for m in re.finditer(r"(?is)<(/?)(tr|table)\b[^>]*>", cuerpo):
        cierre, tag = m.group(1) == "/", m.group(2).lower()
        if tag == "table":
            prof += -1 if cierre else 1
        elif prof == 0:
            if not cierre:
                inicio = m.end()
            elif inicio is not None:
                filas.append(cuerpo[inicio:m.start()])
                inicio = None
    return filas


def leer(pagina):
    """Sesiones de comisiones de la página semanal."""
    art = re.search(r'(?is)<article[^>]*class="[^"]*citaciones[^"]*"[^>]*>(.*)</article>', pagina)
    cuerpo = art.group(1) if art else pagina
    salida = []
    # el artículo alterna <p class="fecha"> y la tabla de ese día
    partes = re.split(r'(?is)<p[^>]*class="[^"]*fecha[^"]*"[^>]*>(.*?)</p>', cuerpo)
    for i in range(1, len(partes) - 1, 2):
        fecha = fecha_larga(texto(partes[i]))
        tabla = re.search(r'(?is)<table[^>]*class="[^"]*tabla[^"]*"[^>]*>(.*)</table>', partes[i + 1])
        if not fecha or not tabla:
            continue
        for fila in _filas(tabla.group(1)):
            c = _celdas(fila)
            if len(c) < 4:
                continue
            nombre_html = c[0][1]
            suspendida = bool(re.search(r"suspendid", texto(nombre_html), re.I))
            nombre = texto(re.sub(r"(?is)<p[^>]*>.*?</p>", "", nombre_html)).replace("\n", " ").strip()
            puntos, invitados = [], []
            for f in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", c[3][1]) or [c[3][1]]:
                obj = re.search(r'(?is)<td[^>]*class="[^"]*w40[^"]*"[^>]*>(.*?)</td>', f)
                inv = re.search(r'(?is)<td[^>]*class="[^"]*w30[^"]*"[^>]*>(.*?)</td>', f)
                if obj and texto(obj.group(1)):
                    puntos.append(texto(obj.group(1)))
                if inv and texto(inv.group(1)):
                    invitados.append(re.sub(r"^(Se ha citado a|Se ha invitado a|Invitados?):?\s*", "", texto(inv.group(1)), flags=re.I).strip())
            materia = "\n".join(f"{n}.- {p}" for n, p in enumerate(puntos, 1)) if len(puntos) > 1 else (puntos[0] if puntos else "")
            es_cei = nombre.upper().startswith("CEI")
            salida.append({
                "camara": "Cámara de Diputados", "tipo": "Comisión", "fecha": fecha,
                "instancia": nombre if es_cei or nombre.lower().startswith("comisi") else f"Comisión de {nombre}",
                "estado": "Suspendida" if suspendida else "Citada", "horario": texto(c[1][1]).replace("\n", " "),
                "lugar": texto(c[2][1]).replace("\n", ", "), "materia": materia, "boletines": boletines(materia),
                "invitados": [i for i in invitados if i], "link": "",
            })
    return salida


def es_verificacion(pagina):
    return "<title>Just a moment" in pagina or "Un momento…" in pagina[:3000] or "challenge-platform" in pagina


def descargar_http(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-CL,es;q=0.9", "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def descargar_navegador(urls):
    """Abre las páginas con el Chrome instalado en el equipo (pasa la verificación de navegador)."""
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=False, args=["--start-minimized"])
        except Exception:  # noqa: BLE001
            b = p.chromium.launch(headless=False)
        pg = b.new_context(locale="es-CL", timezone_id="America/Santiago").new_page()
        for u in urls:
            pg.goto(u, timeout=90000)
            for _ in range(40):
                if "citaciones" in pg.content():
                    break
                pg.wait_for_timeout(1000)
            res[u] = pg.content()
        b.close()
    return res


def semanas(hoy):
    d = datetime.strptime(hoy, "%Y-%m-%d")
    out = []
    for k in (0, 1):
        y, w, _ = (d + timedelta(weeks=k)).isocalendar()
        out.append(f"{y}-{w:02d}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archivo", help="leer una página guardada en vez de descargar")
    a = ap.parse_args()
    if a.archivo:
        with open(a.archivo, encoding="utf-8") as f:
            print(json.dumps(leer(f.read()), ensure_ascii=False, indent=1))
        return
    hoy = datetime.now().strftime("%Y-%m-%d")
    urls = [URL.format(s) for s in semanas(hoy)]
    paginas, metodo = {}, "http"
    try:
        for u in urls:
            paginas[u] = descargar_http(u)
        if any(es_verificacion(p) for p in paginas.values()):
            raise RuntimeError("verificación de navegador")
    except Exception as e:  # noqa: BLE001
        print(f"  Descarga directa no disponible ({e}); se usa el navegador.")
        paginas, metodo = descargar_navegador(urls), "navegador"
    items = []
    for u in urls:
        if es_verificacion(paginas[u]):
            print(f"  ERROR: la Cámara pidió verificación en {u}")
            sys.exit(1)
        items += leer(paginas[u])
    if not items:
        print("  Sin citaciones leídas (¿cambió la página?). No se escribe nada.")
        sys.exit(1)
    previo = {}
    if os.path.exists(SALIDA):
        with open(SALIDA, encoding="utf-8") as f:
            previo = json.load(f)
    # conserva los días ya pasados de la semana anterior para que la agenda no pierda la historia reciente
    lunes = (datetime.strptime(hoy, "%Y-%m-%d") - timedelta(days=datetime.strptime(hoy, "%Y-%m-%d").weekday())).strftime("%Y-%m-%d")
    nuevas_fechas = {x["fecha"] for x in items}
    items += [x for x in previo.get("items", []) if x["fecha"] >= lunes and x["fecha"] not in nuevas_fechas]
    items.sort(key=lambda x: (x["fecha"], x["horario"], x["instancia"]))
    datos = {"actualizado": datetime.now().strftime("%Y-%m-%d %H:%M"), "metodo": metodo, "semanas": semanas(hoy), "items": items}
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"  Citaciones de la Cámara: {len(items)} sesiones ({metodo})")


if __name__ == "__main__":
    main()
