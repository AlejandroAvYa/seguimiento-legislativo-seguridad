# -*- coding: utf-8 -*-
"""Vigilancia del sistema: abre, actualiza o cierra solo un issue "Estado del sistema" en GitHub.

Se ejecuta al final de cada actualización (también si falló). Lee data/meta.json y el resultado del paso
de actualización (variable RESULTADO: success | failure | cancelled).

  hay problema   -> crea el issue con la etiqueta "estado-sistema" o actualiza su descripción
                    (comenta solo cuando cambia el diagnóstico, para no llenar de avisos)
  todo en orden  -> comenta "Resuelto" y cierra el issue abierto

El diagnóstico queda también en salida/salud.md para la tarea de mantención.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETIQUETA = "estado-sistema"
TITULO = "Estado del sistema: hay un problema en la actualización"
REPO_URL = f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'AlejandroAvYa/seguimiento-legislativo-seguridad')}"
HORAS_CAMARA = 30          # sin votaciones de la Cámara por más de este tiempo = problema


def leer(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return defecto


def diagnostico(meta, resultado, hoy):
    """Lista de (clave, texto) con los problemas vigentes."""
    out = []
    if resultado and resultado != "success":
        run = os.environ.get("GITHUB_RUN_ID")
        enlace = f" ([registro]({REPO_URL}/actions/runs/{run}))" if run else ""
        out.append(("falla-actualizacion", f"La última actualización terminó con error{enlace}. El dashboard sigue mostrando los datos anteriores."))
    f = meta.get("fuentes", {})
    s = f.get("senado", {})
    e = s.get("estado", "")
    if e.startswith("respaldo"):
        out.append(("senado-respaldo", f"El servicio web del Senado no responde desde {s.get('servicio_web_sin_respuesta_desde', '?')}. "
                                       "El sistema lee las fichas desde el sitio de tramitación (respaldo automático); faltan solo las votaciones nuevas del Senado."))
    elif e.startswith("sin conexión"):
        out.append(("senado-caido", f"El Senado no responde ni por el servicio web ni por el sitio. Último dato: {s.get('ultima_hora_exitosa', '?')}."))
    elif e.startswith("ok con"):
        out.append(("senado-parcial", f"Senado: {e}."))
    c = f.get("camara_votaciones", {})
    ult = c.get("ultima_consulta_exitosa", "")
    if ult and (hoy - datetime.strptime(ult, "%Y-%m-%d")).total_seconds() > HORAS_CAMARA * 3600:
        out.append(("camara", f"Votaciones de la Cámara sin actualizar desde {ult} ({c.get('estado', '')})."))
    return out


def gh(*args, entrada=None):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, input=entrada)
    if r.returncode != 0:
        print("  gh:", r.stderr.strip()[:300])
    return r.stdout.strip()


def cuerpo(problemas, marca):
    lineas = [f"Diagnóstico automático al {marca} (hora de Chile).", ""]
    lineas += [f"- {t}" for _, t in problemas]
    lineas += ["", "Este aviso se actualiza en cada corrida y se cierra solo cuando todo vuelve a la normalidad. "
               "La tarea de mantención lo revisa dos veces al día y corrige lo que dependa del sistema.",
               "", f"<!-- claves: {','.join(k for k, _ in problemas)} -->"]
    return "\n".join(lineas)


def main():
    meta = leer(os.path.join(RAIZ, "data", "meta.json"), {})
    resultado = os.environ.get("RESULTADO", "success")
    ahora = datetime.now(timezone(timedelta(hours=-3)))
    marca = ahora.strftime("%Y-%m-%d %H:%M")
    problemas = diagnostico(meta, resultado, ahora.replace(tzinfo=None))
    os.makedirs(os.path.join(RAIZ, "salida"), exist_ok=True)
    with open(os.path.join(RAIZ, "salida", "salud.md"), "w", encoding="utf-8") as f:
        f.write(cuerpo(problemas, marca) if problemas else f"Sin problemas al {marca}.\n")
    print(f"  Salud: {len(problemas)} problema(s)")
    for _, t in problemas:
        print("   -", t)
    if "--sin-github" in sys.argv:
        return
    gh("label", "create", ETIQUETA, "--color", "eb3c46", "--description", "Aviso automático del estado del sistema", "--force")
    abiertos = json.loads(gh("issue", "list", "--label", ETIQUETA, "--state", "open", "--json", "number,body") or "[]")
    if problemas:
        claves = ",".join(k for k, _ in problemas)
        if abiertos:
            n, previo = abiertos[0]["number"], abiertos[0].get("body", "")
            gh("issue", "edit", str(n), "--body-file", "-", entrada=cuerpo(problemas, marca))
            if f"claves: {claves} -->" not in previo:
                gh("issue", "comment", str(n), "--body", "Cambió el diagnóstico:\n\n" + "\n".join(f"- {t}" for _, t in problemas))
        else:
            gh("issue", "create", "--title", TITULO, "--label", ETIQUETA, "--body-file", "-", entrada=cuerpo(problemas, marca))
    else:
        for i in abiertos:
            gh("issue", "comment", str(i["number"]), "--body", f"Resuelto: la actualización del {marca} terminó sin problemas. Se cierra automáticamente.")
            gh("issue", "close", str(i["number"]), "--reason", "completed")


if __name__ == "__main__":
    main()
