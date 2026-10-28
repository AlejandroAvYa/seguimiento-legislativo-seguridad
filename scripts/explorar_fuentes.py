# -*- coding: utf-8 -*-
"""Diagnóstico temporal: feed de noticias de la Cámara y comisiones del período."""
import re
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"


def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


for u in ["https://www.camara.cl/cms/feed/", "https://www.camara.cl/cms/?s=tabla+semanal&feed=rss2",
          "https://www.camara.cl/cms/feed/?s=tabla", "https://www.camara.cl/cms/tag/tabla-semanal/feed/",
          "https://www.camara.cl/cms/category/noticias-centro-de-prensa/feed/", "https://www.camara.cl/cms/feed/?paged=2",
          "https://www.camara.cl/cms/2024/10/14/dos-sesiones-para-acusaciones-y-dos-para-legislar-presenta-la-tabla-semanal-tentativa/feed/"]:
    try:
        t = get(u)
        items = re.findall(r"(?s)<item>(.*?)</item>", t)
        print("OK", len(t), len(items), u)
        for it in items[:12]:
            ti = re.search(r"<title>(.*?)</title>", it)
            cats = re.findall(r"<category><!\[CDATA\[(.*?)\]\]>", it)
            ce = re.search(r"(?s)<content:encoded><!\[CDATA\[(.*?)\]\]>", it)
            print("   -", ti.group(1) if ti else "", "| cats:", cats[:6], "| contenido:", len(ce.group(1)) if ce else 0)
        if items:
            ce = re.search(r"(?s)<content:encoded><!\[CDATA\[(.*?)\]\]>", items[0])
            print("   EJEMPLO:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ce.group(1) if ce else ""))[:1200])
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, u)
    except Exception as e:  # noqa: BLE001
        print("ERR", type(e).__name__, u)

B = "https://opendata.camara.cl/camaradiputados/WServices/"
for q in ["WSComision.asmx/retornarComisionesXPeriodo?prmPeriodoId=11", "WSComision.asmx/retornarComisionesXPeriodo?prmPeriodoID=11"]:
    try:
        t = re.sub(r"\s+", " ", get(B + q))
        coms = re.findall(r"<Comision> <Id>(\d+)</Id> <Nombre>([^<]*)</Nombre>", re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", t))
        print("OK", q, len(coms), coms[:60])
        for i, n in coms:
            if re.search(r"Seguridad|Constituci", n):
                s = re.sub(r"\s+", " ", get(B + f"WSComision.asmx/retornarSesionesXComisionYAnno?prmComisionId={i}&prmAnno=2026"))
                ses = re.findall(r"<SesionComision>.*?</SesionComision>", re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", s))
                print("  SESIONES", n, len(ses))
                for x in ses[-4:]:
                    print("     ", x[:500])
        break
    except Exception as e:  # noqa: BLE001
        print("ERR", type(e).__name__, str(e)[:100], q)
