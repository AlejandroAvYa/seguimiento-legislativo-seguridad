# -*- coding: utf-8 -*-
"""Incorpora o descarta un boletín a partir de una solicitud (issue) creada desde el dashboard.

Uso (en GitHub Actions):  python scripts/gestionar_boletin.py cuerpo_issue.md
Lee del formulario: acción, boletín y, para incorporar, nombre corto, clasificación, materia, descripción y nota.
  Incorporar  -> valida el boletín en el Senado y lo agrega a config/catalogo.csv
  Descartar   -> lo quita de config/catalogo.csv (si estaba) y lo deja como "descartado" en data/candidatos.csv
Escribe salida/respuesta_gestion.md con el resultado, que la tarea publica como comentario.
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import senado  # noqa: E402
from actualizar import CONFIG, DATA, SALIDA, ahora, leer_csv  # noqa: E402

CAMPOS_CAT = ["boletin", "nombre_corto", "clasificacion", "materia", "descripcion", "acot", "nota",
              "responsable", "posicion_ejecutivo", "ultima_gestion", "proximo_paso"]
CAMPOS_CAND = ["boletin", "titulo", "fecha_deteccion", "motivo", "decision", "observacion"]
VACIO = {"", "_no response_", "none", "ninguno", "-"}


def leer_formulario(cuerpo):
    """Formulario de issue de GitHub: '### Etiqueta\\n\\nvalor' -> {etiqueta en minúsculas: valor}."""
    campos = {}
    for m in re.finditer(r"(?ms)^###\s+(.+?)\s*\n(.*?)(?=^###\s|\Z)", cuerpo):
        valor = m.group(2).strip()
        campos[m.group(1).strip().lower()] = "" if valor.lower() in VACIO else valor
    return campos


def campo(campos, *claves):
    for c in claves:
        for k, v in campos.items():
            if k.startswith(c):
                return v
    return ""


def normalizar_boletin(texto):
    m = re.search(r"(\d{1,2})\.?(\d{3})\s*-\s*(\d{2})", texto or "")
    return f"{m.group(1)}{m.group(2)}-{m.group(3)}" if m else ""


def clasificacion(texto):
    t = (texto or "").strip().lower()
    return "Núcleo" if t.startswith(("núcleo", "nucleo")) else "Conexo" if t.startswith("conexo") else "Por clasificar"


def escribir_csv(ruta, filas, campos_):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos_, extrasaction="ignore")
        w.writeheader()
        for r in filas:
            w.writerow({k: r.get(k, "") for k in campos_})


def procesar(campos, autor=""):
    accion = campo(campos, "acción", "accion").lower()
    boletin = normalizar_boletin(campo(campos, "boletín", "boletin"))
    if not boletin:
        return False, "No se reconoce el número de boletín. Debe tener el formato `12345-07`."
    ruta_cat = os.path.join(CONFIG, "catalogo.csv")
    catalogo = leer_csv(ruta_cat)
    en_cat = next((r for r in catalogo if r["boletin"].strip() == boletin), None)
    ruta_cand = os.path.join(DATA, "candidatos.csv")
    candidatos = leer_csv(ruta_cand)
    cand = next((c for c in candidatos if c["boletin"] == boletin), None)
    hoy = ahora().strftime("%Y-%m-%d")

    if accion.startswith("incorporar"):
        if en_cat:
            return False, f"El boletín **{boletin}** ya está en seguimiento ({en_cat.get('nombre_corto') or 'sin nombre corto'})."
        try:
            f = senado.ficha(boletin)
        except Exception as e:  # noqa: BLE001
            return False, f"No se pudo consultar el Senado para validar el boletín {boletin} ({type(e).__name__}). Vuelve a intentarlo más tarde."
        if not f:
            return False, f"El Senado no informa el boletín **{boletin}**. Revisa el número."
        fila = {
            "boletin": boletin,
            "nombre_corto": campo(campos, "nombre corto") or f["titulo"][:70],
            "clasificacion": clasificacion(campo(campos, "clasificación", "clasificacion")),
            "materia": campo(campos, "materia") or "Por clasificar",
            "descripcion": campo(campos, "descripción", "descripcion"),
            "nota": campo(campos, "nota", "motivo"),
        }
        catalogo.append(fila)
        escribir_csv(ruta_cat, catalogo, CAMPOS_CAT)
        if cand:
            cand["decision"] = "incorporado"
            cand["observacion"] = f"Incorporado el {hoy}" + (f" por {autor}" if autor else "")
            escribir_csv(ruta_cand, candidatos, CAMPOS_CAND)
        return True, (f"Boletín **{boletin}** incorporado al seguimiento: {f['titulo']}\n\n"
                      f"- Nombre corto: {fila['nombre_corto']}\n- Clasificación: {fila['clasificacion']}\n- Materia: {fila['materia']}\n\n"
                      "Aparecerá en el dashboard en unos minutos, con toda su tramitación.")

    if accion.startswith("descartar") or accion.startswith("quitar"):
        motivo = campo(campos, "nota", "motivo") or "Descartado desde el dashboard"
        cambios = []
        if en_cat:
            catalogo = [r for r in catalogo if r["boletin"].strip() != boletin]
            escribir_csv(ruta_cat, catalogo, CAMPOS_CAT)
            cambios.append("se quitó del seguimiento")
        titulo = (en_cat or {}).get("nombre_corto", "") or (cand or {}).get("titulo", "")
        if cand:
            cand["decision"], cand["observacion"] = "descartado", motivo
        else:
            if not titulo:
                try:
                    f = senado.ficha(boletin)
                    titulo = f["titulo"] if f else ""
                except Exception:  # noqa: BLE001
                    titulo = ""
            candidatos.append({"boletin": boletin, "titulo": titulo, "fecha_deteccion": hoy, "motivo": "Registrado desde el dashboard",
                               "decision": "descartado", "observacion": motivo})
        escribir_csv(ruta_cand, candidatos, CAMPOS_CAND)
        cambios.append("quedó como descartado (no volverá a proponerse como candidato)")
        return True, f"Boletín **{boletin}**: " + " y ".join(cambios) + f".\n\nMotivo: {motivo}"

    return False, "La acción debe ser **Incorporar** o **Descartar**."


def main():
    with open(sys.argv[1], encoding="utf-8") as f:
        cuerpo = f.read()
    autor = os.environ.get("AUTOR", "")
    ok, mensaje = procesar(leer_formulario(cuerpo), autor)
    os.makedirs(SALIDA, exist_ok=True)
    with open(os.path.join(SALIDA, "respuesta_gestion.md"), "w", encoding="utf-8") as f:
        f.write(("✔ " if ok else "✖ ") + mensaje + "\n")
    print(mensaje)
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
        f.write(f"ok={'true' if ok else 'false'}\n")


if __name__ == "__main__":
    main()
