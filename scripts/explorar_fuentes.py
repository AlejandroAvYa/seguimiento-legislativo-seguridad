# -*- coding: utf-8 -*-
"""Diagnóstico: prueba desde GitHub qué páginas de agenda y citaciones responden (uso temporal)."""
import re
import ssl
import urllib.request

UA_BOT = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"
UA_NAV = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
URLS = [
    "https://www.camara.cl/legislacion/comisiones/citaciones.aspx",
    "https://www.camara.cl/legislacion/sala_sesiones/votaciones.aspx",
    "https://www.camara.cl/legislacion/sala_sesiones/tabla.aspx",
    "https://www.camara.cl/legislacion/sala_sesiones/sesiones.aspx",
    "https://www.camara.cl/legislacion/comisiones/comisiones_permanentes.aspx",
    "https://www.camara.cl/",
    "https://opendata.camara.cl/camaradiputados/WServices/WSComision.asmx/retornarComisionesVigentes",
    "https://opendata.camara.cl/camaradiputados/WServices/WSSala.asmx/retornarSesionesXAnno?prmAnno=2026",
    "https://www.senado.cl/",
    "https://tramitacion.senado.cl/appsenado/index.php?mo=comisiones&ac=citacionesComision&tipo_consulta=1",
]
for u in URLS:
    for ua in (UA_BOT, UA_NAV):
        try:
            req = urllib.request.Request(u, headers={"User-Agent": ua, "Accept": "text/html,application/xml,*/*", "Accept-Language": "es-CL,es;q=0.9"})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = r.read()
                print(f"OK {r.status} {len(d):>8} {'nav' if ua == UA_NAV else 'bot'} {u}")
                t = d.decode("utf-8", "replace")
                links = sorted(set(re.findall(r'href="([^"]*(?:citaci|tabla|Tabla|sesion|Sesion|agenda|calendario)[^"]*)"', t)))[:25]
                for l in links:
                    print("      link:", l)
                if "opendata" in u:
                    print("      ", re.sub(r"\s+", " ", t[:1500]))
                    ids = re.findall(r"<Id>(\d+)</Id>\s*<Nombre>([^<]*Seguridad[^<]*)</Nombre>", t)
                    print("      seguridad:", ids[:5])
            break
        except Exception as e:  # noqa: BLE001
            print(f"ERR {type(e).__name__}: {str(e)[:120]} {'nav' if ua == UA_NAV else 'bot'} {u}")
