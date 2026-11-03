# -*- coding: utf-8 -*-
"""Resumen en lenguaje simple de cada proyecto: en qué está, qué se ha indicado o votado y qué falta.

Dos partes:
  automática  se arma cada hora con los datos oficiales (trámites, hitos, votaciones, indicaciones, agenda).
  redactada   config/resumenes/BOLETIN.md, escrita por el equipo (principales contenidos, observaciones en Sala…).
              Formato:
                  fecha: 2026-11-02
                  ## Principales contenidos
                  - **Personal de seguridad:** regula el régimen laboral…
                  ## Observaciones en Sala
                  - Los senadores…
"""
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "config", "resumenes")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def fecha(f, hoy="", dia=False):
    """'2026-10-21' -> '21 de octubre' (agrega el año si no es el de hoy)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}", f or ""):
        return f or ""
    a, m, d = f[:4], int(f[5:7]), int(f[8:10])
    txt = f"{d} de {MESES[m - 1]}" + ("" if hoy[:4] == a else f" de {a}")
    if dia:
        from datetime import date
        txt = f"{DIAS_SEMANA[date(int(a), m, d).weekday()]} {txt}"
    return txt


def boletin_texto(b):
    n, s = (b.split("-") + [""])[:2]
    return f"{int(n):,}".replace(",", ".") + (f"-{s}" if s else "")


def camaras(p):
    origen = "Senado" if (p.get("camara_origen") or "").startswith("Senado") else "Cámara de Diputados"
    return origen, ("Cámara de Diputados" if origen == "Senado" else "Senado")


def el(c):
    return f"el {c}" if c == "Senado" else f"la {c}"


def al(c):
    return f"al {c}" if c == "Senado" else f"a la {c}"


def cap(t):
    return t[:1].upper() + t[1:]


def sala(c):
    return "la Sala del Senado" if c == "Senado" else "la Sala de la Cámara"


def _cam(c):
    return "Senado" if (c or "").startswith("Senado") else "Cámara de Diputados"


# ------------------------------------------------------------------ estado de tramitación
def recorrido(p, hoy):
    """Frases con lo aprobado en cada cámara, a partir de los hitos oficiales."""
    por_etapa = []
    for h in p.get("hitos") or []:
        clave = (h.get("etapa", ""), _cam(h.get("camara")))
        if not por_etapa or por_etapa[-1][0] != clave:
            por_etapa.append((clave, []))
        por_etapa[-1][1].append(h)
    frases = []
    for (etapa, cam), hs in por_etapa:
        nombres = {h["hito"]: h["fecha"] for h in hs}
        partes = []
        if "Aprobado en general y particular" in nombres:
            partes.append(f"en general y en particular el {fecha(nombres['Aprobado en general y particular'], hoy)}")
        else:
            if "Aprobado en general" in nombres:
                partes.append(f"en general el {fecha(nombres['Aprobado en general'], hoy)}")
            if "Aprobado en particular" in nombres:
                partes.append(f"en particular el {fecha(nombres['Aprobado en particular'], hoy)}")
        if partes:
            txt = f"{cap(el(cam))} lo aprobó " + " y ".join(partes)
            if "Despachado con modificaciones a la cámara de origen" in nombres:
                txt += ", con modificaciones"
            elif "Aprobado sin modificaciones por la cámara revisora" in nombres:
                txt += ", sin modificaciones"
            frases.append(txt + ".")
        elif "Aprobado sin modificaciones por la cámara revisora" in nombres:
            frases.append(f"{cap(el(cam))} lo aprobó sin modificaciones el {fecha(nombres['Aprobado sin modificaciones por la cámara revisora'], hoy)}.")
        if "Rechazado en general" in nombres:
            frases.append(f"{cap(el(cam))} lo rechazó en general el {fecha(nombres['Rechazado en general'], hoy)}.")
        if "Rechazo de modificaciones (pasa a Comisión Mixta)" in nombres:
            frases.append(f"{cap(el(cam))} rechazó las modificaciones el {fecha(nombres['Rechazo de modificaciones (pasa a Comisión Mixta)'], hoy)}, por lo que se formó una Comisión Mixta.")
        if "Insistencia" in nombres:
            frases.append(f"Hubo insistencia {('del ' if cam == 'Senado' else 'de la ') + cam} el {fecha(nombres['Insistencia'], hoy)}.")
        if "Enviado al Tribunal Constitucional" in nombres:
            frases.append(f"Fue enviado al Tribunal Constitucional el {fecha(nombres['Enviado al Tribunal Constitucional'], hoy)}.")
    # tercer trámite: la cámara de origen se pronuncia sobre las modificaciones
    for t in p.get("tramites") or []:
        if t.get("etapa", "").startswith("Tercer") and re.search(r"aprobadas las modificaciones", t.get("descripcion", ""), re.I):
            frases.append(f"{cap(el(_cam(t.get('camara'))))} aprobó esas modificaciones el {fecha(t['fecha'], hoy)}.")
            break
    return frases


def notas_tramite(p, hoy):
    """Aclaraciones que vienen en el texto del trámite (indicaciones retiradas, inadmisibles, TC)."""
    out = []
    for t in p.get("tramites") or []:
        d = t.get("descripcion", "")
        if re.search(r"retirad\w* y declarad\w* inadmisible|declarad\w* inadmisibles?|fueron retiradas", d, re.I) and "indicacion" in d.lower():
            out.append(f"En la discusión en particular en {el(_cam(t.get('camara')))}, las indicaciones fueron retiradas o declaradas inadmisibles ({fecha(t['fecha'], hoy)}).")
        elif re.search(r"Tribunal Constitucional", d) and re.search(r"requerimiento|resoluci|sentencia", d, re.I):
            out.append(f"Tribunal Constitucional: {limpiar(d)[:220]} ({fecha(t['fecha'], hoy)}).")
    return out[-2:]


def limpiar(d):
    d = re.sub(r"\s+\.", ".", d or "")
    return re.sub(r"\s{2,}", " ", d).strip(" .")


def estado(p, hoy):
    sit = p.get("situacion", "")
    frases = []
    hitos = {h["hito"]: h["fecha"] for h in p.get("hitos") or []}
    if sit == "Publicado como ley":
        frases.append(f"El proyecto es ley: {p.get('ley_numero') or 'ley publicada'}"
                      + (f", publicada en el Diario Oficial el {fecha(p['ley_fecha_diario_oficial'], hoy)}." if p.get("ley_fecha_diario_oficial") else "."))
    elif sit == "Despachado al Ejecutivo":
        f = hitos.get("Despachado al Ejecutivo") or p.get("ultimo_tramite_fecha", "")
        frases.append(f"El proyecto terminó su tramitación en el Congreso" + (f" el {fecha(f, hoy)}." if f else "."))
    elif sit in ("Archivado", "Retirado", "Rechazado"):
        frases.append(f"El proyecto está {sit.lower()}" + (f" desde el {fecha(p.get('ultimo_tramite_fecha'), hoy)}." if p.get("ultimo_tramite_fecha") else "."))
    else:
        origen, revisora = camaras(p)
        cod = p.get("etapa_codigo", "")
        donde = p.get("instancia_actual") or p.get("subetapa") or ""
        tramite = {"1C": "primer trámite", "1S": "primer trámite", "2C": "segundo trámite", "2S": "segundo trámite",
                   "3T": "tercer trámite", "CM": "Comisión Mixta", "TC": "etapa final"}.get(cod, "tramitación")
        cam = _cam(p.get("camara_actual")) if p.get("camara_actual") else (origen if cod.startswith("1") else revisora)
        txt = f"Está en {tramite}" + (f" en {el(cam)}" if cod not in ("CM", "TC") and not cod.endswith("S") else "")
        if cod.endswith("S"):
            txt += f", en la Sala {'del Senado' if cam == 'Senado' else 'de la Cámara de Diputados'}" + (f" ({donde[0].lower() + donde[1:]})" if re.search(r"discusi", donde, re.I) else "")
        elif donde and cod.endswith("C"):
            txt += f", en la {donde[0].lower() + donde[1:]}" if donde.lower().startswith("comisi") else f" ({donde[0].lower() + donde[1:]})"
        elif donde:
            txt += f" ({donde[0].lower() + donde[1:]})"
        if p.get("fecha_inicio_etapa"):
            txt += f", desde el {fecha(p['fecha_inicio_etapa'], hoy)}"
            if str(p.get("dias_en_etapa", "")).isdigit():
                txt += f" ({p['dias_en_etapa']} días)"
        frases.append(txt + ".")
    frases += recorrido(p, hoy)
    frases += notas_tramite(p, hoy)
    if sit == "En tramitación":
        u = p.get("urgencia_vigente")
        if u and u != "Sin urgencia":
            v = p.get("urgencia_vence_estimado", "")
            frases.append(f"Tiene urgencia {u.lower() if u != 'Suma' else 'suma'}"
                          + (f"; el plazo estimado {'vence' if v >= hoy else 'venció'} el {fecha(v, hoy)}." if v else "."))
        prox = sorted([x for x in p.get("agenda") or [] if x.get("fecha", "") >= hoy and x.get("estado") != "Suspendida"],
                      key=lambda x: (x["fecha"], x.get("horario", "")))
        if prox:
            x = prox[0]
            hora = (x.get("horario") or "").split(" a ")[0]
            frases.append(f"Próxima sesión citada: {x.get('instancia', '')}, el {fecha(x['fecha'], hoy, dia=True)}" + (f" a las {hora}" if hora else "") + ".")
        else:
            mov = [t for t in p.get("tramites") or [] if not re.search(r"urgencia|^Oficio|^Cuenta oficio|^Cuenta del Mensaje", t.get("descripcion", ""), re.I)]
            if mov:
                t = mov[-1]
                frases.append(f"Último trámite, sin contar urgencias: {limpiar(t['descripcion'])[:180]} ({fecha(t['fecha'], hoy)}).")
        n_urg = int(p.get("n_urgencias_en_etapa") or 0)
        if n_urg >= 3:
            frases.append(f"Desde su último avance se han presentado o renovado {n_urg} urgencias.")
    return frases


# ------------------------------------------------------------------ indicaciones y votaciones
def indicado(p, hoy):
    out = []
    n = int(p.get("n_indicaciones_senado") or 0)
    if n:
        ej, pa = int(p.get("n_indicaciones_senado_ejecutivo") or 0), int(p.get("n_indicaciones_senado_parlamentarias") or 0)
        autores = [a["autor"] for a in (p.get("indicaciones_por_autor") or []) if a.get("tipo_autor") == "Parlamentario"][:4]
        txt = f"En el Senado se presentaron {n} indicaciones"
        det = []
        if ej:
            det.append(f"{ej} del Ejecutivo")
        if pa:
            det.append(f"{pa} parlamentarias" + (f" ({', '.join(autores)})" if autores else ""))
        if pa == n:
            out.append(txt + ", todas parlamentarias" + (f" ({', '.join(autores)})" if autores else "") + ".")
        elif ej == n:
            out.append(txt + ", todas del Ejecutivo.")
        else:
            out.append(txt + (": " + " y ".join(det) if det else "") + ".")
    for pl in p.get("plazo_indicaciones") or []:
        if pl.get("fecha", "") >= hoy:
            out.append(f"El plazo para presentar indicaciones vence el {fecha(pl['fecha'], hoy, dia=True)}" + (f" a las {pl['hora']}" if pl.get("hora") else "") + ".")
            break
    for clave, cam in (("votaciones_camara", "Cámara de Diputados"), ("votaciones", "Senado")):
        vs = sorted(p.get(clave) or [], key=lambda v: v.get("fecha", ""))
        if not vs:
            continue
        ult = vs[-1]
        mismas = [v for v in vs if v.get("fecha") == ult.get("fecha")]
        rech = [v for v in vs if re.search(r"rechaz", v.get("resultado", ""), re.I)]
        if len(mismas) == 1:
            txt = (f"Última votación en {sala(cam)} ({fecha(ult['fecha'], hoy)}): "
                   f"{ult.get('si', 0)} a favor, {ult.get('no', 0)} en contra y {ult.get('abstencion', 0)} abstenciones ({(ult.get('resultado') or '').lower()}).")
        else:
            ap = sum(1 for v in mismas if re.search(r"aprob", v.get("resultado", ""), re.I))
            txt = f"El {fecha(ult['fecha'], hoy)}, {sala(cam)} votó {len(mismas)} veces: " + (
                "todas aprobadas." if ap == len(mismas) else "todas rechazadas." if not ap else f"{ap} aprobadas y {len(mismas) - ap} rechazadas.")
        if rech and not (len(mismas) > 1 and all(v in mismas for v in rech)):
            txt += (f" Antes hubo una votación rechazada en esa Sala ({fecha(rech[-1]['fecha'], hoy)})." if len(rech) == 1
                    else f" En esa Sala hubo {len(rech)} votaciones rechazadas; la última, el {fecha(rech[-1]['fecha'], hoy)}.")
        out.append(txt)
    inf = [i for i in p.get("informes") or [] if i.get("fecha")]
    if inf:
        i = sorted(inf, key=lambda x: x["fecha"])[-1]
        out.append(f"Último informe: {i.get('tramite', 'informe de comisión')} ({fecha(i['fecha'], hoy)}).")
    return out


# ------------------------------------------------------------------ qué falta
def falta(p, hoy):
    sit = p.get("situacion", "")
    origen, revisora = camaras(p)
    if sit == "Publicado como ley":
        return ["Nada en el Congreso. Queda la implementación: reglamentos y plazos que fije la ley."]
    if sit in ("Archivado", "Retirado"):
        return ["Para retomarlo se requiere pedir su desarchivo o ingresar un nuevo proyecto."] if sit == "Archivado" else ["No sigue en tramitación."]
    if sit == "Rechazado":
        return ["No sigue en tramitación. Un proyecto rechazado en general en la cámara de origen no puede renovarse sino después de un año (artículo 68 de la Constitución)."]
    if sit == "Despachado al Ejecutivo":
        tc = any("Tribunal Constitucional" in (t.get("descripcion") or "") for t in p.get("tramites") or [])
        txt = ["Queda pendiente su promulgación y publicación en el Diario Oficial.",
               "Si contiene normas de rango orgánico constitucional, antes debe pasar por el control preventivo del Tribunal Constitucional."
               if not tc else "Hay actuaciones del Tribunal Constitucional registradas; su promulgación depende de que concluyan.",
               "El Presidente de la República tiene 30 días desde que recibe el proyecto para promulgarlo o formular observaciones (veto)."]
        return txt
    cod, sub = p.get("etapa_codigo", ""), (p.get("subetapa") or "").lower()
    luego_revisora = (f"Después debe pasar por {el(revisora)} (comisión y Sala). Si esa cámara introduce cambios, vuelve {al(origen)} en tercer trámite "
                      "y, si hay discrepancias, a Comisión Mixta. Al final, promulgación y publicación.")
    final_revisora = (f"Si {el(revisora)} lo aprueba sin cambios, queda despachado al Ejecutivo; si introduce modificaciones, vuelve {al(origen)} "
                      "en tercer trámite (y a Comisión Mixta si hay discrepancias).")
    if cod in ("1C", "2C"):
        cam = origen if cod == "1C" else revisora
        if "segundo informe" in sub or "particular" in sub:
            primero = f"Falta el segundo informe de la comisión (discusión en particular) y la votación en particular en {sala(cam)}."
        else:
            primero = f"Falta que la comisión despache su informe y que {sala(cam)} lo vote."
        return [primero, luego_revisora if cod == "1C" else final_revisora]
    if cod in ("1S", "2S"):
        cam = origen if cod == "1S" else revisora
        etapa = "en particular" if "particular" in sub else "en general" if "general" in sub else ""
        primero = f"Falta la votación {etapa + ' ' if etapa else ''}en {sala(cam)}."
        if etapa == "en general":
            primero += " Si se aprueba, se abre plazo de indicaciones y vuelve a comisión para la discusión en particular, salvo que se vote en general y particular a la vez."
        return [primero, luego_revisora if cod == "1S" else final_revisora]
    if cod == "3T":
        return [f"Falta que {el(origen)} se pronuncie sobre las modificaciones de {el(revisora)}. Si las aprueba, queda despachado; si las rechaza, se forma una Comisión Mixta."]
    if cod == "CM":
        return ["Falta el informe de la Comisión Mixta y su votación en ambas Salas. Luego, promulgación y publicación."]
    return ["Falta completar la etapa final: control del Tribunal Constitucional si corresponde, promulgación y publicación."]


# ------------------------------------------------------------------ redacción del equipo
def leer_redactado(boletin, carpeta=CARPETA):
    ruta = os.path.join(carpeta, f"{boletin}.md")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return parsear_redactado(f.read())


def parsear_redactado(texto):
    out = {"fecha": "", "autor": "", "secciones": []}
    actual = None
    for linea in texto.splitlines():
        l = linea.strip()
        m = re.match(r"^(fecha|autor)\s*:\s*(.+)$", l, re.I)
        if m and actual is None:
            out[m.group(1).lower()] = m.group(2).strip()
            continue
        m = re.match(r"^#{1,3}\s+(.+)$", l)
        if m:
            actual = {"titulo": m.group(1).strip().strip("*"), "items": [], "parrafos": []}
            out["secciones"].append(actual)
            continue
        if not l or actual is None:
            continue
        m = re.match(r"^[-•*]\s+(.+)$", l)
        if m:
            actual["items"].append(m.group(1).strip())
        else:
            actual["parrafos"].append(l)
    return out if out["secciones"] else None


def generar(p, hoy):
    r = {"estado": estado(p, hoy), "indicado": indicado(p, hoy), "falta": falta(p, hoy), "redactado": leer_redactado(p["boletin"])}
    red = r["redactado"]
    if red and red.get("fecha"):
        posteriores = [h for h in p.get("hitos") or [] if h.get("fecha", "") > red["fecha"]]
        if posteriores:
            r["aviso"] = f"Hubo avances después de la redacción del {fecha(red['fecha'], hoy)} (último: {posteriores[-1]['hito'].lower()}, {fecha(posteriores[-1]['fecha'], hoy)})."
    return r
