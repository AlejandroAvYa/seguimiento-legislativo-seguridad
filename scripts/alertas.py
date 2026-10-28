# -*- coding: utf-8 -*-
"""Avisos por correo y Microsoft Teams.

Uso:
  python scripts/alertas.py --cambios            avisa los cambios relevantes de la última actualización
  python scripts/alertas.py --resumen-diario     resumen: cambios de 24 h, urgencias por vencer, candidatos
  python scripts/alertas.py --prueba             mensaje de prueba para verificar la configuración
  python scripts/alertas.py --resumen-diario --adjunto informes/archivo.docx

Configuración (secretos del repositorio en GitHub, o variables de entorno):
  ALERTA_DESTINATARIOS   correos separados por coma
  ALERTA_SMTP_HOST, ALERTA_SMTP_PUERTO (587), ALERTA_SMTP_USUARIO, ALERTA_SMTP_CLAVE, ALERTA_REMITENTE (opcional)
  ALERTA_TEAMS_WEBHOOK   dirección del flujo de Teams "Publicar en un canal cuando se recibe una solicitud de webhook"
Si no hay nada configurado, no envía y termina sin error.
"""
import argparse
import csv
import json
import mimetypes
import os
import smtplib
import sys
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from html import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from actualizar import DATA, SALIDA, ahora, leer_csv, leer_json  # noqa: E402

RELEVANTES = {"Situación", "Etapa", "N° de ley", "Urgencia vigente", "Nuevo informe de comisión",
              "Nuevo boletín de indicaciones (Senado)", "Nueva votación en Sala del Senado",
              "Nueva votación en Sala de la Cámara", "Proyecto agregado al seguimiento", "Refundidos"}
URL_SENADO = "https://tramitacion.senado.cl/appsenado/templates/tramitacion/index.php?boletin_ini="


def titulos():
    return {p["boletin"]: p["titulo"] for p in leer_json(os.path.join(DATA, "proyectos.json"), [])}


def fmt(f):
    try:
        return datetime.strptime(f[:10], "%Y-%m-%d").strftime("%d-%m-%Y") + f[10:]
    except ValueError:
        return f


# ----------------------------------------------------------------- contenido
def bloque_cambios(cambios, tit):
    rel = [c for c in cambios if c["tipo"] in RELEVANTES]
    otros = len([c for c in cambios if c["tipo"] not in RELEVANTES])
    filas = [{"boletin": c["boletin"], "proyecto": tit.get(c["boletin"], ""), "cambio": c["tipo"],
              "detalle": (f"{c['antes']} → {c['despues']}" if c["antes"] else c["despues"])} for c in rel]
    return filas, otros


def urgencias_por_vencer(dias=7):
    hoy = ahora().strftime("%Y-%m-%d")
    lim = (ahora() + timedelta(days=dias)).strftime("%Y-%m-%d")
    return [{"boletin": p["boletin"], "proyecto": p["titulo"], "urgencia": p["urgencia_vigente"], "vence": p["urgencia_vence_estimado"]}
            for p in leer_json(os.path.join(DATA, "proyectos.json"), [])
            if p.get("situacion") == "En tramitación" and p.get("urgencia_vence_estimado") and hoy <= p["urgencia_vence_estimado"] <= lim]


def candidatos_pendientes():
    return [c for c in leer_csv(os.path.join(DATA, "candidatos.csv")) if c.get("decision") == "pendiente"]


# ----------------------------------------------------------------- formato
def tabla_html(filas, columnas):
    if not filas:
        return "<p><i>Sin registros.</i></p>"
    cab = "".join(f"<th style='background:#1F3864;color:#fff;text-align:left;padding:4px 6px'>{escape(t)}</th>" for _, t in columnas)
    cuerpo = ""
    for f in filas:
        celdas = []
        for k, _ in columnas:
            v = escape(str(f.get(k, "")))
            if k == "boletin":
                v = f"<a href='{URL_SENADO}{v}'>{v}</a>"
            celdas.append(f"<td style='border-top:1px solid #ddd;padding:4px 6px;vertical-align:top'>{v}</td>")
        cuerpo += "<tr>" + "".join(celdas) + "</tr>"
    return f"<table style='border-collapse:collapse;font-family:Verdana;font-size:12px'><tr>{cab}</tr>{cuerpo}</table>"


def tabla_texto(filas, columnas):
    if not filas:
        return "Sin registros.\n"
    return "".join("- " + " | ".join(str(f.get(k, "")) for k, _ in columnas) + "\n" for f in filas)


def construir(secciones, titulo):
    html = f"<div style='font-family:Verdana;font-size:13px'><h2 style='color:#1F3864'>{escape(titulo)}</h2>"
    texto = titulo + "\n\n"
    for i, (nombre, filas, columnas, nota) in enumerate(secciones, 1):
        html += f"<h3 style='background:#1F3864;color:#fff;padding:4px 8px'>{i}. {escape(nombre)}</h3>"
        html += tabla_html(filas, columnas) + (f"<p style='color:#555'>{escape(nota)}</p>" if nota else "")
        texto += f"{i}. {nombre}\n" + tabla_texto(filas, columnas) + (nota + "\n" if nota else "") + "\n"
    pages = os.environ.get("ALERTA_URL_DASHBOARD", "")
    pie = "Fuente: registro oficial de tramitación del Senado y datos abiertos de la Cámara."
    enlace = f" Dashboard: <a href='{escape(pages)}'>{escape(pages)}</a>" if pages else ""
    html += f"<p style='color:#555;font-size:11px'>{escape(pie)}{enlace}</p></div>"
    texto += pie + (f"\nDashboard: {pages}" if pages else "")
    return html, texto


# ----------------------------------------------------------------- envío
def enviar_correo(asunto, html, texto, adjunto=None):
    dest = [d.strip() for d in os.environ.get("ALERTA_DESTINATARIOS", "").split(",") if d.strip()]
    host = os.environ.get("ALERTA_SMTP_HOST", "")
    if not dest or not host:
        print("  Correo: no configurado (falta ALERTA_DESTINATARIOS o ALERTA_SMTP_HOST)")
        return False
    usuario = os.environ.get("ALERTA_SMTP_USUARIO", "")
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = os.environ.get("ALERTA_REMITENTE") or usuario
    msg["To"] = ", ".join(dest)
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    if adjunto and os.path.exists(adjunto):
        tipo = (mimetypes.guess_type(adjunto)[0] or "application/octet-stream").split("/")
        with open(adjunto, "rb") as f:
            msg.add_attachment(f.read(), maintype=tipo[0], subtype=tipo[1], filename=os.path.basename(adjunto))
    puerto = int(os.environ.get("ALERTA_SMTP_PUERTO", "587"))
    if puerto == 465:
        servidor = smtplib.SMTP_SSL(host, puerto, timeout=60)
    else:
        servidor = smtplib.SMTP(host, puerto, timeout=60)
        if os.environ.get("ALERTA_SMTP_SIN_TLS") != "1":
            servidor.starttls()
    with servidor:
        if usuario:
            servidor.login(usuario, os.environ.get("ALERTA_SMTP_CLAVE", ""))
        servidor.send_message(msg)
    print(f"  Correo enviado a {len(dest)} destinatario(s)")
    return True


def enviar_teams(titulo, secciones):
    url = os.environ.get("ALERTA_TEAMS_WEBHOOK", "")
    if not url:
        print("  Teams: no configurado (falta ALERTA_TEAMS_WEBHOOK)")
        return False
    cuerpo = [{"type": "TextBlock", "text": titulo, "weight": "Bolder", "size": "Medium", "wrap": True}]
    for i, (nombre, filas, columnas, nota) in enumerate(secciones, 1):
        cuerpo.append({"type": "TextBlock", "text": f"{i}. {nombre}", "weight": "Bolder", "wrap": True, "spacing": "Medium"})
        lineas = [" · ".join(str(f.get(k, "")) for k, _ in columnas) for f in filas[:25]] or ["Sin registros."]
        if len(filas) > 25:
            lineas.append(f"… y {len(filas) - 25} más")
        cuerpo.append({"type": "TextBlock", "text": "\n\n".join(lineas), "wrap": True, "size": "Small"})
        if nota:
            cuerpo.append({"type": "TextBlock", "text": nota, "wrap": True, "isSubtle": True, "size": "Small"})
    tarjeta = {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": cuerpo}}]}
    req = urllib.request.Request(url, data=json.dumps(tarjeta).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f"  Teams: respuesta {r.status}")
    return True


def despachar(asunto, secciones, adjunto=None):
    html, texto = construir(secciones, asunto)
    os.makedirs(SALIDA, exist_ok=True)
    with open(os.path.join(SALIDA, "ultimo_aviso.html"), "w", encoding="utf-8") as f:
        f.write(html)
    errores = []
    for canal in (lambda: enviar_correo(asunto, html, texto, adjunto), lambda: enviar_teams(asunto, secciones)):
        try:
            canal()
        except Exception as e:  # noqa: BLE001
            errores.append(f"{type(e).__name__}: {e}")
            print(f"  ERROR al enviar: {type(e).__name__}: {e}")
    return errores


COLS_CAMBIO = [("boletin", "Boletín"), ("proyecto", "Proyecto"), ("cambio", "Cambio"), ("detalle", "Detalle")]
COLS_URG = [("boletin", "Boletín"), ("proyecto", "Proyecto"), ("urgencia", "Urgencia"), ("vence", "Vence (estimado)")]
COLS_CAND = [("boletin", "Boletín"), ("titulo", "Proyecto"), ("motivo", "Motivo")]


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cambios", action="store_true")
    g.add_argument("--resumen-diario", action="store_true")
    g.add_argument("--prueba", action="store_true")
    ap.add_argument("--adjunto")
    a = ap.parse_args()
    tit = titulos()
    hoy = ahora().strftime("%d-%m-%Y")

    if a.prueba:
        despachar(f"Prueba de avisos – Seguimiento legislativo ({hoy})",
                  [("Configuración", [{"detalle": "Si recibes este mensaje, los avisos están bien configurados."}], [("detalle", "Detalle")], "")])
        return

    if a.cambios:
        cambios = leer_json(os.path.join(SALIDA, "cambios_nuevos.json"), [])
        filas, otros = bloque_cambios(cambios, tit)
        nuevos_cand = os.path.exists(os.path.join(SALIDA, "alerta_candidatos.md"))
        if not filas and not nuevos_cand:
            print("  Sin cambios relevantes: no se envía aviso.")
            return
        secciones = [("Cambios relevantes", filas, COLS_CAMBIO, f"Además se registraron {otros} trámites menores." if otros else "")]
        if nuevos_cand:
            nuevos = [c for c in candidatos_pendientes() if c.get("fecha_deteccion") == ahora().strftime("%Y-%m-%d")]
            secciones.append(("Proyectos nuevos para revisar", nuevos, COLS_CAND, "Detalle en el aviso (issue) del repositorio."))
        despachar(f"Seguimiento legislativo: {len(filas)} cambio(s) relevante(s) – {hoy}", secciones)
        return

    # resumen diario
    desde = (ahora() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
    cambios = [c for c in leer_csv(os.path.join(DATA, "cambios.csv")) if c["fecha_deteccion"] >= desde]
    filas, otros = bloque_cambios(cambios, tit)
    meta = leer_json(os.path.join(DATA, "meta.json"), {})
    fuentes = [{"detalle": f"{k}: {v.get('estado', 's/i')} (última consulta exitosa: {fmt(v.get('ultima_consulta_exitosa', '—'))})"}
               for k, v in meta.get("fuentes", {}).items()]
    secciones = [
        ("Cambios de las últimas 24 horas", filas, COLS_CAMBIO, f"Además se registraron {otros} trámites menores." if otros else ""),
        ("Urgencias que vencen en los próximos 7 días", urgencias_por_vencer(), COLS_URG,
         "Plazo estimado desde el ingreso de la urgencia; el plazo legal corre desde la cuenta en Sala."),
        ("Proyectos nuevos pendientes de revisión", candidatos_pendientes(), COLS_CAND, ""),
        ("Estado de las fuentes", fuentes, [("detalle", "Fuente")], ""),
    ]
    despachar(f"Resumen diario – Seguimiento legislativo ({hoy})", secciones, a.adjunto)


if __name__ == "__main__":
    main()
