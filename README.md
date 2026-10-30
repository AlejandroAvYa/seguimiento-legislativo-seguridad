# Seguimiento legislativo · Seguridad pública y prevención del delito

Base de datos que se actualiza sola, cada hora, con la tramitación de los proyectos de ley de seguridad pública que sigue el Gobierno. Incluye un dashboard, avisos por correo o Teams, un resumen diario y un informe semanal en Word.

**Qué hace en cada ejecución (cada hora)**

1. Lee la lista de boletines a seguir (`config/catalogo.csv`).
2. Consulta la ficha oficial de cada uno en el servicio web del Senado. Esta ficha cubre la tramitación en **ambas cámaras**: trámites, urgencias, informes, oficios, indicaciones y votaciones del Senado.
3. Consulta las votaciones de Sala de la Cámara en el servicio de datos abiertos de la Cámara (con el voto de cada diputado).
4. Actualiza `data/` y registra qué cambió: etapa, urgencia, informes, indicaciones, votaciones, número de ley, etc.
5. Busca proyectos de seguridad con acción del actual Gobierno que todavía no estén en el catálogo y abre un *issue* para revisarlos.
6. Guarda los cambios en el repositorio y, si hubo cambios relevantes, avisa por correo o Teams.

Además, de lunes a viernes envía un **resumen diario** y los lunes genera un **informe semanal en Word**.

---

## Estructura

```
config/catalogo.csv               Boletines que se siguen y su clasificación (se edita a mano)
config/acot.csv                   Iniciativas de la Agenda contra el Crimen Organizado y el Terrorismo (ACOT) y su boletín
config/logo.png                   Logo institucional (dashboard e informe semanal)
data/tablero.json                 Versión liviana para la portada del dashboard
data/proyectos.json               Base completa, un registro por proyecto
data/fichas/BOLETIN.json          Ficha completa de cada proyecto (la carga el dashboard, más liviano que proyectos.json)
data/votaciones.json              Votaciones en Sala de ambas cámaras, de la más reciente a la más antigua
data/proyectos.csv / .xlsx        Lo mismo en tabla y en Excel (con hojas de detalle)
data/tramites.csv, urgencias.csv  Todos los trámites y urgencias
data/hitos.csv                    Hitos (ingreso, aprobación en general, despacho, Comisión Mixta, TC…)
data/informes.csv, oficios.csv    Informes de comisión y oficios
data/boletines_indicaciones.csv   Boletines de indicaciones del Senado
data/indicaciones.csv             Cada indicación presentada en el Senado, con su autor y su texto
data/indicaciones/BOLETIN.json    Indicaciones de cada proyecto con su texto (las usa la ficha del dashboard)
data/indicaciones_por_autor.csv   Indicaciones por proyecto y autor
data/votaciones.csv, votos.csv    Votaciones en Sala del Senado y voto de cada senador
data/votaciones_camara.csv        Votaciones en Sala de la Cámara de los proyectos seguidos
data/votos_camara.csv             Voto de cada diputado en esas votaciones
data/actores.json                 Autores de mociones e indicaciones y votos por parlamentario
data/cambios.csv / cambios.json   Historial de cambios detectados
data/candidatos.csv               Proyectos detectados para revisar y su decisión
data/agenda.json                  Agenda de la semana: citaciones, tabla de Sala y plazos de indicaciones
data/acot.json                    Iniciativas ACOT con su estado
data/calendario.json              Calendario semana a semana
data/meta.json                    Fechas de actualización y estado de cada fuente
data/cache_*.json                 Datos ya descargados (no se editan)
informes/                         Informes semanales en Word (se crean solos los lunes)
scripts/actualizar.py             Proceso de actualización
scripts/senado.py, camara.py      Lectura de las fuentes oficiales
scripts/indicaciones.py           Lectura de los boletines de indicaciones (autor y texto)
scripts/gestion.py                Etapa normalizada, prioridad, acción sugerida y alertas
scripts/agenda.py                 Agenda: citaciones de comisiones, tabla de Sala, plazos de indicaciones y calendario
scripts/citaciones_camara.py      Citaciones de comisiones de la Cámara (corre en el computador en Chile)
scripts/partidos.py               Partido de cada parlamentario y composición de comisiones del Senado
scripts/alertas.py                Avisos por correo y Teams; resumen diario
scripts/informe_semanal.py        Informe semanal en Word
tests/                            Pruebas (se ejecutan antes de cada actualización)
index.html                        Dashboard
.github/workflows/actualizar.yml  Tarea horaria
.github/workflows/reportes.yml    Resumen diario e informe semanal
```

---

## Instalación paso a paso

Se hace una sola vez. Toma unos 20 minutos.

### Paso 1. Crear el repositorio

1. Entrar a <https://github.com> con tu cuenta (o crear una gratis).
2. Arriba a la derecha: **+** → **New repository**.
3. Nombre: `seguimiento-legislativo-seguridad`.
4. Visibilidad:
   - **Public** (recomendado): Actions sin límite de minutos y GitHub Pages gratis. Los datos son públicos de todas formas.
   - **Private**: 2.000 minutos de Actions al mes en el plan gratuito (la tarea horaria usa entre 750 y 1.500) y Pages solo con plan pagado.
5. **No** marcar "Add a README". Clic en **Create repository**.

### Paso 2. Subir los archivos

Descomprimir el .zip. Luego:

**Opción A: con Git (recomendada).** En una terminal, dentro de la carpeta descomprimida:

```bash
git init -b main
git add -A
git commit -m "Carga inicial"
git remote add origin https://github.com/TU_USUARIO/seguimiento-legislativo-seguridad.git
git push -u origin main
```

**Opción B: desde el navegador.**

1. En el repositorio vacío: **uploading an existing file**.
2. Arrastrar **todo el contenido** de la carpeta (no la carpeta misma) y clic en **Commit changes**.
3. Revisar que exista `.github/workflows/` con `actualizar.yml` y `reportes.yml`. Windows y macOS ocultan las carpetas que empiezan con punto y a veces no se suben. Si faltan:
   **Add file** → **Create new file** → nombre `.github/workflows/actualizar.yml` → pegar el contenido → **Commit changes**. Repetir con `reportes.yml`.

### Paso 3. Dar permiso de escritura a Actions

**Settings** → **Actions** → **General**:

- *Actions permissions*: **Allow all actions and reusable workflows**.
- *Workflow permissions*: **Read and write permissions** → **Save**.

### Paso 4. Primera ejecución y verificación de la Cámara

1. Pestaña **Actions**. Si aparece un aviso, clic en **I understand my workflows, go ahead and enable them**.
2. A la izquierda: **Actualizar proyectos de ley** → **Run workflow** → **Run workflow**.
3. La primera vez tarda más (de 5 a 15 minutos), porque descarga las votaciones de la Cámara desde 2022. Debe terminar con ✓ verde.
4. Entrar a la ejecución → paso **Consultar Senado y Cámara y actualizar datos**. Buscar la línea:
   - `Cámara: N votaciones de proyectos seguidos` → **la Cámara quedó conectada**.
   - `AVISO Cámara: no se pudo consultar…` → ver el apartado [Si la Cámara no conecta](#si-la-cámara-no-conecta). El resto de los datos se actualiza igual.

Desde ese momento se ejecuta sola cada hora.

### Paso 5. Publicar el dashboard

1. **Settings** → **Pages**.
2. *Source*: **Deploy from a branch**. *Branch*: **main**, carpeta **/ (root)** → **Save**.
3. En un par de minutos queda en `https://TU_USUARIO.github.io/seguimiento-legislativo-seguridad/`.
4. (Opcional, para que los correos incluyan el enlace) **Settings** → **Secrets and variables** → **Actions** → pestaña **Variables** → **New repository variable**: nombre `URL_DASHBOARD`, valor la dirección anterior.

En la cabecera del dashboard se ve el estado de cada fuente (verde: al día; rosado: sin conexión, con la fecha de la última consulta exitosa).

### Paso 6. Configurar los avisos por correo

**Settings** → **Secrets and variables** → **Actions** → pestaña **Secrets** → **New repository secret**. Crear uno por cada fila:

| Secreto | Gmail | Correo institucional (Microsoft 365) |
|---|---|---|
| `ALERTA_DESTINATARIOS` | `persona1@dominio.cl,persona2@dominio.cl` | igual |
| `ALERTA_SMTP_HOST` | `smtp.gmail.com` | `smtp.office365.com` |
| `ALERTA_SMTP_PUERTO` | `587` | `587` |
| `ALERTA_SMTP_USUARIO` | tu cuenta Gmail completa | la cuenta que envía |
| `ALERTA_SMTP_CLAVE` | **contraseña de aplicación** (ver abajo) | la clave de esa cuenta |
| `ALERTA_REMITENTE` | (opcional) | (opcional) |

- **Gmail:** requiere verificación en dos pasos activada. Luego, en <https://myaccount.google.com/apppasswords> crear una contraseña de aplicación (16 letras) y usar esa, no la clave normal. Se recomienda una cuenta Gmail creada solo para esto.
- **Microsoft 365:** muchas instituciones tienen bloqueado el envío SMTP autenticado. Si falla, pedir a informática que habilite "SMTP AUTH" para esa casilla o usar Gmail o Teams.

Para probar: **Actions** → **Resumen diario e informe semanal** → **Run workflow**. Debe llegar un correo en un par de minutos.

### Paso 7. (Opcional) Avisos en Microsoft Teams

1. En Teams, en el canal donde quieres los avisos: **⋯** → **Workflows** (Flujos de trabajo).
2. Elegir la plantilla **"Post to a channel when a webhook request is received"** ("Publicar en un canal cuando se recibe una solicitud de webhook").
3. Seguir los pasos y **copiar la dirección** que entrega al final.
4. En GitHub crear el secreto `ALERTA_TEAMS_WEBHOOK` con esa dirección.

Se puede usar solo correo, solo Teams o ambos. Si no se configura ninguno, los avisos simplemente no se envían.

### Paso 8. Avisos de candidatos y de fallas

- **Candidatos nuevos:** en el repositorio, **Watch** → **Custom** → marcar **Issues** → **Apply**.
- **Fallas:** GitHub envía un correo automáticamente cuando una ejecución programada falla.

---

## El dashboard

Se abre en `https://TU_USUARIO.github.io/seguimiento-legislativo-seguridad/` y tiene siete vistas:

| Vista | Para qué sirve |
|---|---|
| Panorama | Resumen en cifras, atención inmediata, movimientos recientes y el **cuadro de avance**: cada proyecto en una fila y las ocho etapas en columnas (primer trámite comisión y Sala, segundo trámite comisión y Sala, tercer trámite, Comisión Mixta, control y promulgación, ley). La etapa actual se marca con la cámara (S, C o M) y el color de la urgencia. |
| Ficha del proyecto | Se abre con un clic en cualquier proyecto: avance por etapa con fechas, qué hace, dónde está, prioridad y alertas, gestión MSP, línea de tiempo, indicaciones (por autor, por artículo y el texto de cada una), votaciones de ambas cámaras con el voto de cada parlamentario, informes, oficios y todos los trámites. |
| Resumen para autoridades | Una pantalla para el Subsecretario, el Ministro y sus asesores: qué requiere decisión, qué pasa esta semana en el Congreso, qué avanzó en 7 días y qué urgencias vencen. |
| Agenda de la semana | Citaciones de comisiones del Senado con materia e invitados, tabla de la Sala del Senado, sesiones de Sala de la Cámara y plazos para presentar indicaciones. Por defecto muestra solo lo que toca proyectos seguidos. |
| Agenda ACOT | Las 29 iniciativas de la ACOT: cuadro de avance de las que tienen boletín y estado de las anunciadas sin boletín. En el panorama, el botón "Solo ACOT" filtra el cuadro. |
| Urgencias y alertas | Urgencias que vencen en 7 y 30 días, plazos cumplidos sin renovación y alertas de riesgo. |
| Indicaciones | Proyectos y autores con más indicaciones. |
| Votaciones y actores | Votaciones recientes y tablas de senadores, diputados y autores. |
| Cambios recientes | Todo lo que cambió, por día. |
| Leyes y despachos | Despachados al Ejecutivo, leyes publicadas y proyectos fuera de tramitación. |
| Gestión de boletines | Incorporar o descartar un boletín escribiendo su número, y decidir sobre los candidatos detectados. |
| Fuentes y método | Estado de las fuentes, definición de cada etapa y reglas de prioridad y alertas. |

La barra superior incluye los elementos del Kit Digital de Gobierno: línea institucional azul y roja, botones para aumentar o reducir el texto y modo de alto contraste, y enlace para saltar al contenido.

Las citaciones de comisiones de la Cámara (con materia e invitados) solo se publican en camara.cl, que bloquea consultas desde servidores fuera de Chile. Para incluirlas hay que ejecutar la actualización desde un computador en Chile (ver "Si la Cámara no conecta").

La agenda incluye un calendario semana a semana (sesiones de Sala de cada cámara, citaciones, feriados y urgencias que vencen). La ficha muestra el ritmo de tramitación frente a la mediana de los proyectos seguidos, las urgencias presentadas desde el último avance, los integrantes de la comisión del Senado donde está el proyecto y los votos por partido de cada votación.

La prioridad (crítica, alta, media, baja) y la acción sugerida se calculan con reglas fijas en `scripts/gestion.py`, descritas en la vista Fuentes y método.

---

## Qué avisos llegan y cuándo

| Aviso | Cuándo | Contenido |
|---|---|---|
| Cambios relevantes | Cada hora, solo si hubo cambios | Cambio de etapa o situación, urgencia, ley publicada, informe nuevo, boletín de indicaciones nuevo, votación nueva (Senado o Cámara), proyecto agregado |
| Resumen diario | Lunes a viernes, 08:05 en horario de verano (07:05 en invierno) | Cambios de las últimas 24 horas, urgencias que vencen en 7 días, candidatos pendientes |
| Informe semanal | Lunes, junto al resumen | Word adjunto al correo, guardado en `informes/` y descargable desde la ejecución en Actions |

El informe semanal también se puede generar a pedido: **Actions** → **Resumen diario e informe semanal** → **Run workflow** → marcar *Generar también el informe semanal en Word*.

Los cambios menores (cada trámite nuevo) no generan aviso, pero quedan en `data/cambios.csv` y en el dashboard.

---

## Citaciones de comisiones de la Cámara (computador en Chile)

camara.cl rechaza las consultas desde servidores fuera de Chile, así que las citaciones de comisiones de la Cámara las lee un computador de la SPD. Basta con que esté encendido de lunes a viernes entre las 9 y las 20 horas. Si está apagado, la tarea espera y corre al encenderlo; el resto del sistema sigue funcionando en GitHub.

Instalación (una vez, en Windows):

1. Tener instalados **Git para Windows** y **Google Chrome**.
2. En GitHub: **Settings → Actions → Runners → New self-hosted runner → Windows**. GitHub muestra los comandos con un código de registro válido por una hora.
3. Abrir **PowerShell** y ejecutar los comandos de la sección *Download* (crean la carpeta `C:\actions-runner` y descargan el programa).
4. Ejecutar el comando de la sección *Configure*. Cuando pregunte:
   - *runner group*: Enter.
   - *name of runner*: `spd-camara` (o Enter).
   - *additional labels*: escribir **`camara`** (importante).
   - *work folder*: Enter.
   - *run as service*: **N** (la tarea abre Chrome y necesita la sesión de Windows iniciada).
5. Iniciar el runner con `.\run.cmd`. Para que parta solo al encender el equipo, crear un acceso directo a `C:\actions-runner\run.cmd` en la carpeta de inicio de Windows (Win+R → `shell:startup`).
6. Probar: **Actions → Citaciones de comisiones de la Cámara → Run workflow**.

El equipo no debe suspenderse en ese horario (la pantalla puede bloquearse, pero la sesión debe quedar iniciada).

## Si la Cámara no conecta

La información de la Cámara llega por dos vías:

- **Tramitación en la Cámara** (trámites, urgencias, informes, oficios, despacho): viene de la ficha del Senado, que registra ambas cámaras. **No depende de la Cámara** y está asegurada.
- **Votaciones en Sala de la Cámara** (con el voto de cada diputado): vienen de `opendata.camara.cl`.

Si `opendata.camara.cl` no responde desde GitHub, el sistema conserva las votaciones ya descargadas, marca la fuente como "sin conexión" en el dashboard y en `data/meta.json`, y sigue actualizando todo lo demás. Cuando la Cámara vuelve a responder, se pone al día sola.

Si la falla persiste varios días, la solución es ejecutar la tarea en un computador propio en Chile (un *runner* propio):

1. En el repositorio: **Settings** → **Actions** → **Runners** → **New self-hosted runner**.
2. Elegir el sistema operativo del computador (Linux, Windows o macOS) y ejecutar en ese computador los comandos que muestra GitHub (descarga, `config` y `run`). Para que quede permanente, instalarlo como servicio (en Linux: `sudo ./svc.sh install && sudo ./svc.sh start`; en Windows lo ofrece el propio instalador).
3. El computador debe tener **Python 3.10 o superior** y **Git** (en Windows, Git para Windows, que incluye Git Bash).
4. **Settings** → **Secrets and variables** → **Actions** → **Variables** → **New repository variable**: nombre `EJECUTOR`, valor `self-hosted`.

Desde ese momento ambas tareas corren en ese computador. Para volver a los servidores de GitHub, borrar la variable `EJECUTOR`. El computador tiene que estar encendido y con internet para que las tareas corran.

---

## Uso diario

### Ver qué cambió

- Dashboard: panel **Cambios recientes** y **Urgencias que vencen en 7 días**. Al hacer clic en un proyecto se ve su etapa, línea de tiempo, indicaciones por autor, informes, votaciones de ambas cámaras y documentos.
- Pestaña **Actores** del dashboard: autores de mociones, autores de indicaciones y votos de senadores y diputados en los proyectos seguidos.
- `data/cambios.csv` (o la hoja *Cambios* del Excel).
- El historial de commits: cada commit muestra exactamente qué datos cambiaron.

### Incorporar, descartar o quitar un boletín

Desde el dashboard, vista **Gestión de boletines**:

1. Escribir el número de boletín (por ejemplo `18806-07`) y elegir **Incorporar** o **Descartar**. La vista avisa si ya está en seguimiento, si es candidato o si fue descartado antes.
2. Para incorporar se puede agregar nombre corto, clasificación y materia; para descartar, el motivo.
3. Presionar **Continuar en GitHub**: se abre el formulario ya completo; basta con presionar **Create**.
4. La tarea "Incorporar o descartar boletín" valida el número en el Senado, actualiza `config/catalogo.csv` y `data/candidatos.csv`, responde en la misma solicitud, la cierra y lanza la actualización del dashboard.

Los candidatos pendientes aparecen en la misma vista con botones **Incorporar** y **Descartar**, y también en el issue "Candidatos nuevos para revisar". La ficha de cada proyecto tiene el botón **Quitar del seguimiento**. Solo se procesan solicitudes de cuentas con acceso al repositorio (dueño o colaboradores); para sumar a alguien: Settings → Collaborators.

Un boletín descartado no vuelve a proponerse como candidato. Criterio de detección de candidatos: movimiento en los últimos 6 días, con urgencia, indicaciones del Ejecutivo o mensaje del actual Gobierno (desde el 11-03-2026), y título con términos de seguridad (lista `PALABRAS_CLAVE` en `scripts/actualizar.py`).

Edición manual, si se prefiere: `config/catalogo.csv` tiene las columnas `boletin, nombre_corto, clasificacion, materia, descripcion, acot, nota, responsable, posicion_ejecutivo, ultima_gestion, proximo_paso` (solo el boletín es obligatorio; las cuatro últimas son los campos de "Gestión MSP" de la ficha).

### Logo en el informe semanal

Subir el logo como `config/logo.png`. Se incluye solo en el encabezado.

---

## Datos para otras herramientas

Todos los archivos se pueden leer directamente desde internet:

```
https://raw.githubusercontent.com/TU_USUARIO/seguimiento-legislativo-seguridad/main/data/proyectos.csv
https://raw.githubusercontent.com/TU_USUARIO/seguimiento-legislativo-seguridad/main/data/proyectos.json
```

Sirve para conectar Excel (Datos → Desde la web), Power BI o Looker Studio y que se refresquen solos. En repositorio privado estas direcciones requieren autenticación.

Campos principales de `proyectos.json` / `proyectos.csv`:

| Campo | Contenido |
|---|---|
| `boletin`, `titulo` | Número de boletín y título oficial |
| `clasificacion`, `materia`, `descripcion`, `acot`, `nota` | Clasificación manual del catálogo |
| `iniciativa`, `autoria`, `fecha_ingreso`, `camara_origen` | Origen del proyecto |
| `situacion` | En tramitación / Despachado al Ejecutivo / Publicado como ley / Rechazado / Archivado / Retirado |
| `etapa`, `subetapa` | Estado según el Senado, textual |
| `tramite_constitucional`, `camara_actual`, `instancia_actual` | Trámite (primero, segundo, tercero, Comisión Mixta, TC…), cámara y comisión o Sala |
| `fecha_inicio_etapa`, `dias_en_etapa`, `dias_desde_ingreso` | Tiempos de tramitación |
| `urgencia_vigente`, `urgencia_vigente_desde`, `urgencia_vence_estimado`, `urgencia_plazo` | Urgencia actual y su plazo estimado |
| `n_urgencias_gobierno_actual`, `indicaciones_ejecutivo_gobierno_actual`, `mensaje_gobierno_actual` | Acciones del actual Gobierno |
| `ley_numero`, `ley_fecha_diario_oficial`, `veto` | Resultado final |
| `ultimo_tramite_fecha`, `ultimo_tramite`, `ultimo_tramite_camara` | Último movimiento |
| `n_indicaciones_senado`, `..._ejecutivo`, `..._parlamentarias`, `..._ejecutivo_gobierno_actual` | Indicaciones en el Senado por tipo de autor |
| `n_informes_comision`, `ultimo_informe` | Informes de comisión |
| `n_votaciones_sala_senado`, `ultima_votacion_sala_senado` | Votaciones en Sala del Senado |
| `n_votaciones_sala_camara`, `ultima_votacion_sala_camara` | Votaciones en Sala de la Cámara |
| `hitos`, `informes`, `oficios`, `boletines_indicaciones`, `votaciones`, `votaciones_camara`, `indicaciones_por_autor`, `tramites`, `urgencias` | Listas completas (solo en el JSON) |
| `link_senado`, `link_camara`, `link_texto` | Fichas oficiales y texto original |

`data/meta.json` → `fuentes` indica el estado de cada fuente (`ok` o `sin conexión`) y la fecha de su última consulta exitosa. Las fechas van en formato `AAAA-MM-DD`.

---

## Frecuencia y límites

- **Frecuencia:** cada hora, al minuto 17 (hora UTC). Se cambia en `.github/workflows/actualizar.yml`; por ejemplo, `17 */3 * * *` cada 3 horas. En horas de alta demanda GitHub puede atrasar algunos minutos una ejecución. No hay "tiempo real": la fuente es el registro oficial, que se actualiza a medida que se registran los trámites.
- **Horario del resumen diario:** se define en hora UTC en `.github/workflows/reportes.yml` (`5 11 * * 1-5`). Con el cambio de hora en Chile se mueve una hora; si se quiere otra hora, cambiar el `11`.
- **Inactividad:** GitHub desactiva tareas programadas en repositorios sin actividad por 60 días. Aquí no ocurre, porque `meta.json` cambia a diario.
- **Fallas del Senado:** si un boletín no responde, se conserva su último dato. Si falla más del 30 % de las consultas, la ejecución se detiene sin modificar nada y queda en rojo.
- **Fallas de la Cámara:** se conservan las votaciones ya descargadas y la fuente queda marcada como "sin conexión". Nunca detiene la actualización del Senado.
- **Votaciones de la Cámara:** solo de la Sala y desde 2022. La primera carga no genera avisos por votaciones antiguas; desde la segunda, cada votación nueva se avisa.
- **Indicaciones:** el detalle por autor viene de los boletines de indicaciones del Senado. En la Cámara no existe un documento equivalente (las indicaciones de diputados quedan dentro de los informes de comisión), por lo que de la Cámara solo se registran los oficios del Ejecutivo con indicaciones.
- **Actores:** los nombres se muestran como los informa cada fuente; no se cruzan entre Senado y Cámara.
- **Plazo de urgencia:** es una estimación desde el ingreso de la urgencia; el plazo legal corre desde que se da cuenta en la Sala.
- **Aún no incluido:** tabla semanal y citaciones de comisiones de la Cámara (la página web de la Cámara bloquea consultas desde servidores en el extranjero; requeriría el runner propio en Chile).
- **Lo manual sigue siendo manual:** la clasificación, la materia y la descripción vienen del catálogo. El estado, las urgencias y los trámites vienen siempre de las fuentes oficiales.

---

## Probar en un computador propio (opcional)

Requiere Python 3.10 o superior.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v          # pruebas
python scripts/actualizar.py                     # actualización real
python scripts/alertas.py --prueba               # prueba de correo/Teams (con las variables ALERTA_* definidas)
python scripts/informe_semanal.py                # informe semanal en informes/
python -m http.server 8000                       # luego abrir http://localhost:8000
```

Opciones de `actualizar.py`: `--sin-candidatos` (no busca proyectos nuevos) y `--sin-excel` (no genera el Excel).
