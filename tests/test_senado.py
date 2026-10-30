# -*- coding: utf-8 -*-
import os
import sys
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(AQUI), "scripts"))
import actualizar  # noqa: E402
import senado      # noqa: E402


def cargar(nombre):
    with open(os.path.join(AQUI, "fixtures", nombre), encoding="utf-8") as f:
        return senado.leer_xml(f.read())[0]


class LectorSenado(unittest.TestCase):
    def test_campos_basicos(self):
        f = cargar("18341.xml")
        self.assertEqual(f["boletin"], "18341-25")
        self.assertEqual(f["titulo"], "Crea el registro de actos vandálicos e incivilidades")
        self.assertEqual(senado.fecha_iso(f["fecha_ingreso"]), "2026-06-12")
        self.assertTrue(f["iniciativa"].startswith("Mensaje"))
        self.assertGreater(len(f["tramites"]), 5)
        self.assertGreater(len(f["urgencias"]), 5)

    def test_indicaciones_y_urgencias_del_gobierno(self):
        urg, ind, mensaje = actualizar.accion_gobierno(cargar("18341.xml"))
        self.assertTrue(mensaje)
        self.assertIn("2026-08-21", ind)
        self.assertTrue(all(u["ingreso"] >= actualizar.INICIO_GOBIERNO for u in urg))

    def test_ley_publicada(self):
        f = cargar("15347.xml")
        self.assertIn("21.817", f["leynro"])
        self.assertEqual(actualizar.situacion(f), "Publicado como ley")

    def test_registro_completo(self):
        r = actualizar.registro({"materia": "Prueba"}, cargar("18341.xml"))
        actualizar.gestion.evaluar(r, "2026-10-28")
        for campo in actualizar.CAMPOS_PLANOS:
            self.assertIn(campo, r)
        self.assertIn("prmID=19025", r["link_camara"])
        self.assertEqual(r["autoria"], "Gob. Kast")

    def test_deteccion_de_cambios(self):
        r = actualizar.registro({}, cargar("18341.xml"))
        previo = {**r, "etapa": "Etapa anterior", "tramites": r["tramites"][:-1]}
        cambios = actualizar.detectar_cambios({"18341-25": previo}, {"18341-25": r}, "2026-01-01 00:00")
        tipos = {c["tipo"] for c in cambios}
        self.assertIn("Etapa", tipos)
        self.assertIn("Nuevo trámite", tipos)



class LectorIndicaciones(unittest.TestCase):
    def setUp(self):
        import indicaciones
        self.ind = indicaciones
        with open(os.path.join(AQUI, "fixtures", "indicaciones_15589.txt"), encoding="utf-8") as f:
            self.items = indicaciones.leer_indicaciones(f.read())

    def test_autores_y_tipos(self):
        por_numero = {x["numero"]: x for x in self.items}
        self.assertEqual(por_numero["1"]["autor"], "Longton")
        self.assertEqual(por_numero["2"]["tipo_autor"], "Ejecutivo")
        self.assertEqual(por_numero["3"]["autor"], "Vodanovic")

    def test_varias_indicaciones_en_una_frase(self):
        por_numero = {x["numero"]: x for x in self.items}
        self.assertEqual(por_numero["4"]["autor"], "Sánchez")
        self.assertEqual(por_numero["5"]["autor"], "Pascual")
        self.assertEqual(por_numero["5"]["accion"], "suprimirlo")

    def test_numeracion_con_letras(self):
        numeros = {x["numero"] for x in self.items}
        self.assertIn("1H a)", numeros)


class EstructuraEtapa(unittest.TestCase):
    def test_etapa_e_instancia(self):
        f = cargar("18341.xml")
        tramite, camara, instancia = actualizar.estructura_etapa(f)
        self.assertEqual(tramite, "Primer trámite constitucional")
        self.assertEqual(camara, "Cámara de Diputados")
        self.assertTrue(instancia.startswith("Comisión de Seguridad Ciudadana"))

    def test_despacho_aunque_la_etapa_no_cambie(self):
        self.assertEqual(actualizar.situacion(cargar("15805.xml")), "Despachado al Ejecutivo")

    def test_votaciones_e_informes(self):
        f = cargar("16481.xml")
        self.assertGreater(len(f["votaciones"]), 0)
        self.assertGreater(len(f["informes"]), 0)
        self.assertIn(f["votaciones"][0]["resultado"], ("Aprobado", "Rechazado"))


class LectorCamara(unittest.TestCase):
    """Usa ejemplos construidos con la estructura del servicio de datos abiertos de la Cámara."""

    def leer(self, nombre):
        with open(os.path.join(AQUI, "fixtures", nombre), encoding="utf-8") as f:
            return f.read()

    def test_votaciones_y_boletin(self):
        import camara
        vs = camara.leer_votaciones(self.leer("camara_votaciones_ejemplo.xml"))
        self.assertEqual(len(vs), 2)
        self.assertEqual(vs[0]["boletines"], ["18341-25"])
        self.assertEqual((vs[0]["si"], vs[0]["no"], vs[0]["resultado"]), (84, 54, "Aprobado"))
        self.assertEqual(vs[1]["boletines"], [])

    def test_detalle(self):
        import camara
        votos = camara.leer_detalle(self.leer("camara_detalle_ejemplo.xml"))
        self.assertEqual(votos[0], {"diputado_id": "1001", "diputado": "Ana Pérez Soto", "seleccion": "Afirmativo"})
        self.assertEqual(votos[1]["seleccion"], "En Contra")

    def test_cruce_con_proyecto(self):
        import camara
        vs = camara.leer_votaciones(self.leer("camara_votaciones_ejemplo.xml"))
        cache = {"votaciones": {v["id"]: v for v in vs}, "detalles": {"99001": camara.leer_detalle(self.leer("camara_detalle_ejemplo.xml"))}}
        r = {"boletin": "18341-25"}
        actualizar.agregar_camara(r, cache)
        self.assertEqual(r["n_votaciones_sala_camara"], 1)
        self.assertEqual(len(r["votaciones_camara"][0]["votos"]), 2)


class Gestion(unittest.TestCase):
    def test_etapa_y_prioridad(self):
        r = actualizar.registro({"materia": "Prueba", "clasificacion": "Núcleo"}, cargar("18341.xml"))
        actualizar.gestion.evaluar(r, "2026-10-28")
        self.assertEqual(r["etapa_codigo"], "1C")                   # primer trámite, en comisión
        self.assertEqual(r["avance_estados"]["1C"], "actual")
        self.assertEqual(r["avance_estados"]["LEY"], "pendiente")
        self.assertEqual(r["avance_camaras"]["2C"], "Senado")       # origen Cámara: revisora Senado
        self.assertIn("Urgencia por vencer", {a["tipo"] for a in r["alertas"]})   # suma vence 03-11
        self.assertEqual(r["prioridad_indice"], 25 + 15 + 15 + 10 + 5)
        self.assertEqual(r["prioridad_nivel"], "Crítica")

    def test_ley_publicada(self):
        r = actualizar.registro({}, cargar("15347.xml"))
        actualizar.gestion.evaluar(r, "2026-10-28")
        self.assertEqual(r["etapa_codigo"], "LEY")
        self.assertEqual(r["avance_estados"]["LEY"], "hecha")
        self.assertNotIn("actual", r["avance_estados"].values())


class TextoIndicaciones(unittest.TestCase):
    def test_texto_capturado(self):
        import indicaciones
        with open(os.path.join(AQUI, "fixtures", "indicaciones_15589.txt"), encoding="utf-8") as f:
            items = indicaciones.leer_indicaciones(f.read())
        self.assertTrue(all(x["texto"] for x in items))
        self.assertIn("Presidente de la República", items[2]["texto"])


class Agenda(unittest.TestCase):
    def test_citaciones_senado(self):
        import agenda
        html = """<article><header><h1 class="titular serif">Miércoles, 28 de Octubre de 2026</h1></header>
        <div><table><tbody><tr><th>COMISI&Oacute;N:</th><td><strong>de Constitución, Legislación, Justicia y Reglamento</strong>
        <label>-- La sesi&oacute;n ser&aacute; transmitida --</label></td></tr><tr><th>LUGAR:</th><td>Sala 3</td></tr>
        <tr><th>HORARIO:</th><td>15:00 a 17:00</td></tr><tr><th>MATERIA:</th><td><strong>1.- ( Bol.N° <a href="x">15589-07</a>) Continuar el estudio.
        <br>A esta sesión ha sido invitado el Ministro de Seguridad Pública, señor X.</strong></td></tr></tbody></table></div>
        <div><table><tbody><tr><th>COMISI&Oacute;N:</th><td><strong>de Minería</strong><label>-- HA QUEDADO SIN EFECTO --</label></td></tr>
        <tr><th>MATERIA:</th><td>Boletín N° 18.551-04</td></tr></tbody></table></div></article>"""
        c = agenda.leer_citaciones(html)
        self.assertEqual(len(c), 2)
        self.assertEqual(c[0]["fecha"], "2026-10-28")
        self.assertEqual(c[0]["instancia"], "Comisión de Constitución, Legislación, Justicia y Reglamento")
        self.assertEqual(c[0]["boletines"], ["15589-07"])
        self.assertTrue(c[0]["invitados"][0].startswith("A esta sesión"))
        self.assertEqual(c[1]["estado"], "Suspendida")
        self.assertEqual(c[1]["boletines"], ["18551-04"])

    def test_feed_camara(self):
        import agenda
        xml = """<rss><channel><item><title>Tabla de la Sala: Cambio al sistema de registro de ADN para este lunes 21</title>
        <link>https://www.camara.cl/cms/2026/09/18/tabla/</link><pubDate>Fri, 18 Sep 2026 15:00:00 +0000</pubDate>
        <category><![CDATA[Noticias Centro de Prensa]]></category><category><![CDATA[#Sala]]></category><category><![CDATA[ADN]]></category>
        <description><![CDATA[<p>La Sala verá el proyecto (boletín 18.585-25) que habilita a las policías&#8230; [&#8230;]</p>]]></description></item>
        <item><title>Aprueban en general proyecto de apoderados</title><link>https://www.camara.cl/cms/x/</link>
        <pubDate>Wed, 28 Oct 2026 18:19:00 +0000</pubDate><category><![CDATA[#Comisión]]></category><description>Texto</description></item></channel></rss>"""
        n = agenda.leer_feed(xml)
        self.assertEqual(n[0]["tipo"], "Tabla de la Sala")
        self.assertEqual(n[0]["boletines"], ["18585-25"])
        self.assertEqual(n[0]["temas"], ["ADN"])
        self.assertEqual(n[1]["tipo"], "Comisión")
        xml2 = """<rss><item><title>Agricultura, violencia contra las mujeres y lobby en los temas de la Sala de este lunes</title><link>a</link>
        <category><![CDATA[#Sala]]></category></item><item><title>Proyectos relativos a seguridad pública despachó la Cámara esta semana</title>
        <link>b</link><category><![CDATA[#Sala]]></category></item></rss>"""
        n2 = agenda.leer_feed(xml2)
        self.assertEqual([x["tipo"] for x in n2], ["Tabla de la Sala", "Sala"])

    def test_secretaria(self):
        import agenda
        self.assertEqual(agenda.nombre_secretaria("PARA PRESENTAR EN SECRETARÍA DE LA COMISIÓN DE ECONOMíA"), "Secretaría de la Comisión de Economía")


class Partidos(unittest.TestCase):
    def test_votos_por_partido(self):
        import partidos
        votos = [{"seleccion": "Afirmativo", "p": "A"}, {"seleccion": "No Vota", "p": "A"}, {"seleccion": "En Contra", "p": "B"},
                 {"seleccion": "Abstención", "p": "B"}, {"seleccion": "Pareo", "p": "B"}]
        r = {d["partido"]: d for d in partidos.por_partido(votos, lambda v: v["p"])}
        self.assertEqual((r["A"]["si"], r["A"]["no"], r["A"]["otros"]), (1, 0, 1))
        self.assertEqual((r["B"]["no"], r["B"]["abstencion"], r["B"]["otros"]), (1, 1, 1))

    def test_cruce_senador(self):
        import partidos
        idx = partidos.indice_senadores([{"apellidos": "De Rementería Venegas", "nombre": "Tomás", "partido": "P.S."},
                                         {"apellidos": "Sepúlveda Orbenes", "nombre": "Alejandra", "partido": "Independiente"}])
        self.assertEqual(partidos.senador_de_voto("De Rementería V., Tomás", idx)["partido"], "P.S.")
        self.assertEqual(partidos.senador_de_voto("Sepúlveda O., Alejandra", idx)["partido"], "Independiente")
        self.assertIsNone(partidos.senador_de_voto("Lagos W., Ricardo", idx))


class CitacionesCamara(unittest.TestCase):
    def test_lector(self):
        import citaciones_camara as cc
        with open(os.path.join(AQUI, "fixtures", "camara_citaciones_ejemplo.html"), encoding="utf-8") as f:
            items = cc.leer(f.read())
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["estado"], "Suspendida")
        self.assertTrue(items[0]["instancia"].startswith("CEI 8"))
        self.assertEqual(items[0]["invitados"], ["Ministro de Obras Públicas, señor Louis de Grange Concha."])
        seg = items[1]
        self.assertEqual((seg["fecha"], seg["instancia"], seg["horario"]), ("2026-10-26", "Comisión de Seguridad Ciudadana", "14:50 a 16:50"))
        self.assertEqual(seg["boletines"], ["18594-25", "18211-25"])
        self.assertIn("Martín Arrau", seg["invitados"][0])
        self.assertEqual(items[2]["fecha"], "2026-10-27")
        self.assertEqual(items[2]["boletines"], ["15589-07"])
        self.assertFalse(cc.es_verificacion("<html><title>Just a moment...</title>") is False)


class SepararAutores(unittest.TestCase):
    def test_coma_y(self):
        self.assertEqual(actualizar.separar_autores("Pugh, Aravena, y Edwards, Macaya y Ossandón"),
                         ["Pugh", "Aravena", "Edwards", "Macaya", "Ossandón"])

    def test_ejecutivo(self):
        self.assertEqual(actualizar.separar_autores("Presidente de la República"), ["Presidente de la República"])


class PrimeraCargaCamara(unittest.TestCase):
    def test_no_avisa_historicas(self):
        prev = {"titulo": "x", "tramites": [], "votaciones_camara": []}
        nuevo = dict(prev, votaciones_camara=[{"fecha": "2024-01-01", "tipo": "General", "resultado": "Aprobado",
                                               "si": 1, "no": 0, "abstencion": 0}])
        self.assertEqual(actualizar.detectar_cambios({"1": prev}, {"1": nuevo}, "m", False), [])
        self.assertEqual(len(actualizar.detectar_cambios({"1": prev}, {"1": nuevo}, "m", True)), 1)


class GestionBoletines(unittest.TestCase):
    CUERPO = ("### Acción\n\n{accion}\n\n### Boletín\n\n{boletin}\n\n### Nombre corto (opcional, solo para incorporar)\n\n{nombre}\n\n"
              "### Clasificación (opcional, solo para incorporar)\n\n_No response_\n\n### Materia (opcional, solo para incorporar)\n\n_No response_\n\n"
              "### Descripción (opcional, solo para incorporar)\n\n_No response_\n\n### Nota o motivo\n\n{nota}")

    def setUp(self):
        import shutil
        import tempfile
        import gestionar_boletin as g
        self.g, self.dir = g, tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        with open(os.path.join(self.dir, "catalogo.csv"), "w", encoding="utf-8") as f:
            f.write(",".join(g.CAMPOS_CAT) + "\n18341-25,Registro de incivilidades,Núcleo,Orden público,,,,,,,\n")
        with open(os.path.join(self.dir, "candidatos.csv"), "w", encoding="utf-8") as f:
            f.write(",".join(g.CAMPOS_CAND) + '\n17000-07,"Título, con coma",2026-10-01,Mensaje,pendiente,\n')
        self._orig = (g.CONFIG, g.DATA, g.senado.ficha)
        g.CONFIG = g.DATA = self.dir
        g.senado.ficha = lambda b: {"titulo": "Proyecto de prueba sobre seguridad"} if b.startswith("17") else None
        self.addCleanup(self._restaurar)

    def _restaurar(self):
        self.g.CONFIG, self.g.DATA, self.g.senado.ficha = self._orig

    def _filas(self, nombre):
        return actualizar.leer_csv(os.path.join(self.dir, nombre))

    def _procesar(self, accion, boletin, nombre="_No response_", nota="_No response_"):
        return self.g.procesar(self.g.leer_formulario(self.CUERPO.format(accion=accion, boletin=boletin, nombre=nombre, nota=nota)), "prueba")

    def test_incorporar_candidato(self):
        ok, msg = self._procesar("Incorporar", "17.000-07", nombre="Proyecto corto")
        self.assertTrue(ok, msg)
        cat = {r["boletin"]: r for r in self._filas("catalogo.csv")}
        self.assertEqual(cat["17000-07"]["nombre_corto"], "Proyecto corto")
        self.assertEqual(cat["17000-07"]["clasificacion"], "Por clasificar")
        cand = self._filas("candidatos.csv")[0]
        self.assertEqual((cand["decision"], cand["titulo"]), ("incorporado", "Título, con coma"))

    def test_no_duplica_ni_acepta_inexistentes(self):
        self.assertFalse(self._procesar("Incorporar", "18341-25")[0])
        self.assertFalse(self._procesar("Incorporar", "99999-07")[0])
        self.assertFalse(self._procesar("Incorporar", "abc")[0])
        self.assertEqual(len(self._filas("catalogo.csv")), 1)

    def test_descartar_seguido(self):
        ok, msg = self._procesar("Descartar", "18341-25", nota="Ya no es prioridad")
        self.assertTrue(ok, msg)
        self.assertEqual(self._filas("catalogo.csv"), [])
        cand = {r["boletin"]: r for r in self._filas("candidatos.csv")}
        self.assertEqual((cand["18341-25"]["decision"], cand["18341-25"]["observacion"]), ("descartado", "Ya no es prioridad"))
        self.assertEqual(cand["18341-25"]["titulo"], "Registro de incivilidades")


if __name__ == "__main__":
    unittest.main()
