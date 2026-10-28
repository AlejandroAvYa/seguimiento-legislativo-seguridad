# -*- coding: utf-8 -*-
"""Lectura de gestión sobre cada proyecto: etapa normalizada, prioridad, acción sugerida y alertas.

Todo se calcula con reglas fijas a partir de los datos oficiales, para que cualquiera pueda revisar
por qué un proyecto quedó en un nivel. Las reglas están documentadas en el dashboard (Fuentes y metodología).
"""
import re
from datetime import datetime, timedelta

# Etapas del cuadro de avance, en orden
ETAPAS = [
    {"codigo": "1C", "grupo": "Primer trámite", "nombre": "Comisión"},
    {"codigo": "1S", "grupo": "Primer trámite", "nombre": "Sala"},
    {"codigo": "2C", "grupo": "Segundo trámite", "nombre": "Comisión"},
    {"codigo": "2S", "grupo": "Segundo trámite", "nombre": "Sala"},
    {"codigo": "3T", "grupo": "Tercer trámite", "nombre": "Cámara de origen"},
    {"codigo": "CM", "grupo": "Comisión Mixta", "nombre": "o insistencia"},
    {"codigo": "TC", "grupo": "Control y promulgación", "nombre": "TC · veto · Ejecutivo"},
    {"codigo": "LEY", "grupo": "Ley", "nombre": "Publicada"},
]
ORDEN = [e["codigo"] for e in ETAPAS]

DIAS_DETENIDO = 180          # sin cambio de etapa por más de estos días
DIAS_SIN_MOVIMIENTO = 30     # con urgencia y sin trámites en estos días
MARGEN_ESTRECHO = 0.10       # votación con diferencia menor al 10 % de los votos emitidos


def _otra(camara):
    return "Senado" if camara.startswith("C") else "Cámara de Diputados"


def _cod_tramite(texto, instancia=""):
    t = (texto or "").lower()
    if t.startswith("primer"):
        return "1S" if instancia == "Sala" else "1C"
    if t.startswith("segundo"):
        return "2S" if instancia == "Sala" else "2C"
    if t.startswith("tercer") or "finalización" in t or "finalizacion" in t:
        return "3T"
    if "mixta" in t or "insist" in t:
        return "CM"
    if "tribunal constitucional" in t or "aprobacion presidencial" in t or "aprobación presidencial" in t or "observaci" in t or "veto" in t:
        return "TC"
    return ""


def avance(p):
    """Etapa actual normalizada y estado de cada etapa del cuadro (hecha, actual, omitida, pendiente)."""
    sit = p["situacion"]
    etapas_vistas = [t.get("etapa", "") for t in p.get("tramites", [])]
    if sit == "Publicado como ley":
        actual = "LEY"
    elif sit == "Despachado al Ejecutivo":
        actual = "TC"
    else:
        actual = _cod_tramite(p.get("tramite_constitucional", ""), p.get("instancia_actual", ""))
        if not actual:                                    # archivado, retirado, rechazado: última etapa conocida
            for e in reversed(etapas_vistas):
                actual = _cod_tramite(e)
                if actual:
                    break
        actual = actual or "1C"
    i_act = ORDEN.index(actual)
    # hubo tercer trámite solo si la cámara de origen votó modificaciones (no basta la cuenta del oficio)
    hubo_3t = any(t.get("etapa", "").lower().startswith("tercer") and re.search(r"Aprob|Rechaz", t.get("descripcion", ""))
                  for t in p.get("tramites", []))
    hubo_cm = any(_cod_tramite(e) == "CM" for e in etapas_vistas)
    origen = p.get("camara_origen", "")
    estados = {}
    for i, c in enumerate(ORDEN):
        if i < i_act:
            if c == "3T" and not hubo_3t:
                estados[c] = "omitida"
            elif c == "CM" and not hubo_cm:
                estados[c] = "omitida"
            else:
                estados[c] = "hecha"
        elif i == i_act:
            estados[c] = "detenida" if sit in ("Archivado", "Retirado", "Rechazado") else ("hecha" if c == "LEY" else "actual")
        else:
            estados[c] = "pendiente"
    camaras = {"1C": origen, "1S": origen, "2C": _otra(origen) if origen else "", "2S": _otra(origen) if origen else "",
               "3T": origen, "CM": "Ambas cámaras", "TC": "", "LEY": ""}
    # fecha de inicio de cada trámite (primer registro con esa etapa)
    inicio = {}
    for t in p.get("tramites", []):
        c = _cod_tramite(t.get("etapa", ""))
        if c and re.match(r"\d{4}-\d{2}-\d{2}$", t.get("fecha", "")):
            grupo = c[0] if c[0] in "12" else c
            inicio.setdefault(grupo, t["fecha"])
    if p.get("fecha_ingreso"):
        inicio["1"] = p["fecha_ingreso"]
    if p.get("ley_fecha_diario_oficial"):
        inicio["LEY"] = p["ley_fecha_diario_oficial"]
    nombre = next(e for e in ETAPAS if e["codigo"] == actual)
    texto = f"{nombre['grupo']} · {nombre['nombre']}" if actual not in ("LEY", "TC", "CM", "3T") else nombre["grupo"]
    if actual in ("1C", "1S", "2C", "2S", "3T") and camaras.get(actual):
        texto += f" ({camaras[actual]})"
    return {"etapa_codigo": actual, "etapa_texto": texto, "avance_estados": estados, "avance_camaras": camaras,
            "avance_inicio": inicio}


def _margen(v):
    try:
        si, no = int(v.get("si") or 0), int(v.get("no") or 0)
        ab = int(v.get("abstencion") or 0)
    except (TypeError, ValueError):
        return None
    emitidos = si + no + ab
    return (si - no) / emitidos if emitidos else None


def alertas(p, hoy):
    """Alertas de riesgo con su explicación. hoy en formato AAAA-MM-DD."""
    salida = []
    if p["situacion"] != "En tramitación":
        return salida
    vence = p.get("urgencia_vence_estimado", "")
    if vence:
        dias = (datetime.strptime(vence, "%Y-%m-%d") - datetime.strptime(hoy, "%Y-%m-%d")).days
        if 0 <= dias <= 7:
            salida.append({"tipo": "Urgencia por vencer", "detalle": f"{p['urgencia_vigente']} vence el {vence} (en {dias} días)."})
        elif dias < 0:
            salida.append({"tipo": "Urgencia con plazo cumplido",
                           "detalle": f"{p['urgencia_vigente']}: el plazo se cumplió el {vence} y no hay renovación registrada."})
    if p.get("urgencia_vigente", "Sin urgencia") != "Sin urgencia" and p.get("ultimo_tramite_fecha"):
        sin_mov = (datetime.strptime(hoy, "%Y-%m-%d") - datetime.strptime(p["ultimo_tramite_fecha"], "%Y-%m-%d")).days
        if sin_mov > DIAS_SIN_MOVIMIENTO:
            salida.append({"tipo": "Urgencia sin movimiento", "detalle": f"Tiene urgencia, pero su último trámite fue hace {sin_mov} días."})
    if isinstance(p.get("dias_en_etapa"), int) and p["dias_en_etapa"] > DIAS_DETENIDO:
        salida.append({"tipo": "Detenido en la misma etapa", "detalle": f"Lleva {p['dias_en_etapa']} días en {p.get('instancia_actual') or 'la etapa actual'}."})
    for camara, lista in (("del Senado", p.get("votaciones", [])), ("de la Cámara", p.get("votaciones_camara", []))):
        if lista:
            v = lista[-1]
            m = _margen(v)
            rechazo = re.search(r"rechaz", str(v.get("resultado", "")), re.I)
            if rechazo:
                salida.append({"tipo": "Votación rechazada",
                               "detalle": f"La última votación registrada en la Sala {camara} ({v['fecha']}) fue rechazada ({v['si']} a favor, "
                                          f"{v['no']} en contra). Puede referirse a la idea de legislar o a una norma en particular."})
            elif m is not None and abs(m) < MARGEN_ESTRECHO:
                salida.append({"tipo": "Votación estrecha",
                               "detalle": f"La última votación en la Sala {camara} ({v['fecha']}) se aprobó por estrecho margen: {v['si']} a favor y {v['no']} en contra."})
    return salida


PUNTOS_URGENCIA = {"Discusión inmediata": 40, "Suma": 25, "Simple": 12}


def prioridad(p, hoy, alertas_p):
    """Índice 0–100, nivel, acción sugerida y los motivos del puntaje."""
    sit = p["situacion"]
    if sit == "Publicado como ley":
        return {"prioridad_indice": "", "prioridad_nivel": "Ley publicada", "accion_sugerida": "Seguimiento de la implementación y de los reglamentos",
                "prioridad_motivos": []}
    if sit == "Despachado al Ejecutivo":
        accion = "Seguir el control del Tribunal Constitucional, la promulgación y la publicación" if p.get("etapa_codigo") == "TC" else "Seguir la promulgación y la publicación"
        return {"prioridad_indice": "", "prioridad_nivel": "Despachado", "accion_sugerida": accion, "prioridad_motivos": []}
    if sit in ("Archivado", "Retirado", "Rechazado"):
        return {"prioridad_indice": "", "prioridad_nivel": "Fuera de tramitación", "accion_sugerida": "Sin acción, salvo decisión de reponerlo",
                "prioridad_motivos": []}
    puntos, motivos = 0, []
    u = p.get("urgencia_vigente", "Sin urgencia")
    if u in PUNTOS_URGENCIA:
        puntos += PUNTOS_URGENCIA[u]
        motivos.append(f"Urgencia {u.lower()} (+{PUNTOS_URGENCIA[u]})")
    tipos = {a["tipo"] for a in alertas_p}
    if "Urgencia por vencer" in tipos:
        puntos += 15
        motivos.append("Urgencia vence en 7 días o menos (+15)")
    cod = p.get("etapa_codigo", "")
    if cod in ("1S", "2S"):
        puntos += 12
        motivos.append("En Sala (+12)")
    elif cod in ("3T", "CM"):
        puntos += 18
        motivos.append("En trámite final (+18)")
    elif cod in ("2C",):
        puntos += 6
        motivos.append("En segundo trámite (+6)")
    if p.get("clasificacion") == "Núcleo":
        puntos += 15
        motivos.append("Proyecto núcleo de seguridad (+15)")
    elif p.get("clasificacion"):
        puntos += 5
        motivos.append(f"Proyecto {p['clasificacion'].lower()} (+5)")
    if p.get("mensaje_gobierno_actual"):
        puntos += 10
        motivos.append("Mensaje del actual Gobierno (+10)")
    elif p.get("n_urgencias_gobierno_actual"):
        puntos += 5
        motivos.append("Con urgencias del actual Gobierno (+5)")
    prox = proxima_sesion(p, hoy)
    if prox:
        puntos += 8
        motivos.append(f"Citado a sesión el {prox['fecha'][8:10]}-{prox['fecha'][5:7]} (+8)")
    if p.get("ultimo_tramite_fecha"):
        dias = (datetime.strptime(hoy, "%Y-%m-%d") - datetime.strptime(p["ultimo_tramite_fecha"], "%Y-%m-%d")).days
        if dias <= 14:
            puntos += 5
            motivos.append("Movimiento en los últimos 14 días (+5)")
    puntos = min(puntos, 100)
    nivel = "Crítica" if puntos >= 70 else "Alta" if puntos >= 50 else "Media" if puntos >= 30 else "Baja"
    return {"prioridad_indice": puntos, "prioridad_nivel": nivel, "accion_sugerida": accion_sugerida(p, tipos, hoy), "prioridad_motivos": motivos}


def proxima_sesion(p, hoy, dias=7):
    """Primera sesión citada (comisión o Sala) en los próximos días, según la agenda."""
    lim = (datetime.strptime(hoy, "%Y-%m-%d") + timedelta(days=dias)).strftime("%Y-%m-%d")
    ses = [x for x in p.get("agenda", []) if hoy <= x.get("fecha", "") <= lim and x.get("estado") != "Suspendida"]
    return sorted(ses, key=lambda x: (x["fecha"], x.get("horario", "")))[0] if ses else None


def accion_sugerida(p, tipos, hoy=""):
    cod = p.get("etapa_codigo", "")
    u = p.get("urgencia_vigente", "Sin urgencia")
    prox = proxima_sesion(p, hoy) if hoy else None
    if prox and prox.get("tipo") == "Sala":
        return f"Preparar la votación: está en tabla de la Sala ({prox['camara']}) el {prox['fecha'][8:10]}-{prox['fecha'][5:7]}"
    if prox:
        return f"Preparar la sesión de {prox['instancia']} del {prox['fecha'][8:10]}-{prox['fecha'][5:7]}"
    if "Urgencia con plazo cumplido" in tipos:
        return "Decidir si se renueva o se retira la urgencia"
    if "Urgencia por vencer" in tipos and u == "Discusión inmediata":
        return "Coordinar la votación antes del vencimiento o renovar la urgencia"
    if cod == "CM":
        return "Preparar la propuesta del Ejecutivo para la Comisión Mixta"
    if cod == "3T":
        return "Asegurar los votos para aprobar las modificaciones en la cámara de origen"
    if cod in ("1S", "2S"):
        return "Asegurar los votos para la votación en Sala"
    if "Detenido en la misma etapa" in tipos and u == "Sin urgencia":
        return "Evaluar si se le pone urgencia o se deja de impulsar"
    if "Urgencia sin movimiento" in tipos:
        return "Pedir que la comisión ponga el proyecto en tabla"
    if p.get("n_indicaciones_senado_ejecutivo_gobierno_actual"):
        return "Seguir la votación de las indicaciones del Ejecutivo en comisión"
    if u in ("Discusión inmediata", "Suma"):
        return "Seguimiento semanal de la comisión"
    return "Seguimiento mensual"


def evaluar(p, hoy):
    """Agrega al registro la etapa normalizada, las alertas y la prioridad."""
    p.update(avance(p))
    al = alertas(p, hoy)
    p["alertas"] = al
    p["n_alertas"] = len(al)
    p.update(prioridad(p, hoy, al))
    return p
