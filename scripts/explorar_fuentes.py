# -*- coding: utf-8 -*-
"""Diagnóstico temporal: sesiones de comisiones y de Sala de la Cámara en datos abiertos."""
import re
import urllib.request

B = "https://opendata.camara.cl/camaradiputados/WServices/"
UA = "Mozilla/5.0 (compatible; seguimiento-legislativo-seguridad/1.0)"


def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


t = re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", get(B + "WSComision.asmx/retornarComisionesVigentes"))
coms = re.findall(r"<Comision>\s*<Id>(\d+)</Id>\s*<Nombre>([^<]*)</Nombre>", t)
print("COMISIONES", len(coms))
for i, n in coms:
    print("  ", i, n)
for i, n in coms:
    if re.search(r"Seguridad|Constituci|Hacienda", n):
        s = get(B + f"WSComision.asmx/retornarSesionesXComisionYAnno?prmComisionId={i}&prmAnno=2026")
        s = re.sub(r"\s+", " ", re.sub(r'\sxmlns(:\w+)?="[^"]*"', "", s))
        ses = re.findall(r"<SesionComision>.*?</SesionComision>", s)
        print("SESIONES", n, len(ses))
        for x in ses[-4:]:
            print("     ", x[:700])
s = re.sub(r"\s+", " ", get(B + "WSSala.asmx/retornarSesionesXAnno?prmAnno=2026"))
ses = re.findall(r"<Sesion>.*?</Sesion>", s)
print("SALA", len(ses))
for x in ses[-6:]:
    print("     ", x[:400])
