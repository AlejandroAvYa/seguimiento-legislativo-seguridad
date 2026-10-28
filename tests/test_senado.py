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


if __name__ == "__main__":
    unittest.main()
