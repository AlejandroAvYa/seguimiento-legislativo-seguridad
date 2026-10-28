# -*- coding: utf-8 -*-
"""Diagnóstico temporal: alternativas para la agenda de la Cámara."""
import re
import urllib.error
import urllib.request

B = "https://opendata.camara.cl/camaradiputados/WServices/"
UA = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"
NAV = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(u, ua=UA):
    req = urllib.request.Request(u, headers={"User-Agent": ua, "Accept-Language": "es-CL,es;q=0.9", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, dict(r.headers), r.read().decode("utf-8", "replace")


def limpio(t):
    return re.sub(r"\s+", " ", re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", t))


# 1. bloqueo de camara.cl: quién responde
for u in ["https://www.camara.cl/legislacion/sesiones_sala/sesiones_sala.aspx", "https://camara.cl/legislacion/sesiones_sala/sesiones_sala.aspx",
          "https://www.cdtv.cl/", "https://www.camara.cl/robots.txt"]:
    try:
        st, h, t = get(u, NAV)
        print("OK", st, len(t), u, {k: v for k, v in h.items() if k.lower() in ("server", "cf-ray", "x-cdn", "via")})
        print("   ", re.sub(r"\s+", " ", t[:600]))
        print("    links:", sorted(set(re.findall(r'href="([^"]*(?:program|vivo|comisi|sesion|agenda|tabla)[^"]*)"', t, re.I)))[:30])
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, u, {k: v for k, v in dict(e.headers).items() if k.lower() in ("server", "cf-ray", "x-cdn", "via", "x-iinfo")})
        print("   ", re.sub(r"\s+", " ", e.read().decode("utf-8", "replace")[:400]))
    except Exception as e:  # noqa: BLE001
        print("ERR", type(e).__name__, str(e)[:150], u)

# 2. datos abiertos: período actual, comisiones del período y sesiones citadas
_, _, t = get(B + "WSLegislativo.asmx/retornarPeriodoLegislativoActual")
print("PERIODO", limpio(t)[:400])
pid = re.search(r"<Id>(\d+)</Id>", limpio(t)).group(1)
_, _, t = get(B + f"WSComision.asmx/retornarComisionesXPeriodo?prmPeriodoId={pid}")
coms = re.findall(r"<Comision> <Id>(\d+)</Id> <Nombre>([^<]*)</Nombre>", limpio(t))
print("COMISIONES DEL PERIODO", len(coms))
for i, n in coms:
    print("   ", i, n)
for i, n in coms:
    if re.search(r"Seguridad|Constituci|Hacienda|Familia|Gobierno Interior", n):
        _, _, s = get(B + f"WSComision.asmx/retornarSesionesXComisionYAnno?prmComisionId={i}&prmAnno=2026")
        ses = re.findall(r"<SesionComision>.*?</SesionComision>", limpio(s))
        print("SESIONES", i, n, len(ses))
        for x in ses[-5:]:
            print("     ", x[:600])
