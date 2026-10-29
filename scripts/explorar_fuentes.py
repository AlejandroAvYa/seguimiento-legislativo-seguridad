# -*- coding: utf-8 -*-
"""Diagnóstico temporal: ¿un navegador real pasa la verificación de camara.cl desde GitHub?"""
import re
import sys
from playwright.sync_api import sync_playwright

URLS = ["https://www.camara.cl/legislacion/sesiones_sala/sesiones_sala.aspx",
        "https://www.camara.cl/legislacion/comisiones/comisiones_permanentes.aspx"]
headless = "--headless" in sys.argv
with sync_playwright() as p:
    b = p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(locale="es-CL", timezone_id="America/Santiago",
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                        viewport={"width": 1366, "height": 900})
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    pg = ctx.new_page()
    for u in URLS:
        try:
            pg.goto(u, timeout=60000)
            for _ in range(30):
                if "moment" not in pg.title().lower():
                    break
                pg.wait_for_timeout(1000)
            html = pg.content()
            print("MODO", "headless" if headless else "con pantalla", "|", pg.title(), "|", len(html), u)
            links = sorted(set(re.findall(r'href="([^"]*(?:citaci|tabla|sesion|prmID|verDoc)[^"]*)"', html, re.I)))[:40]
            for l in links:
                print("   link:", l)
            print("   texto:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:1500])
        except Exception as e:  # noqa: BLE001
            print("ERR", type(e).__name__, str(e)[:200], u)
    b.close()
