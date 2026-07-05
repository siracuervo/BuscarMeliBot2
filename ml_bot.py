"""
Bot de búsqueda de vehículos en Mercado Libre (Argentina) — versión scraping.

IMPORTANTE: la API pública de búsqueda de Mercado Libre dejó de funcionar sin
autenticación desde abril de 2025. Este script en cambio lee directamente la
página web de resultados (scraping), tal como la vería un navegador.
Mercado Libre bloquea el acceso automatizado en su robots.txt, así que:
  - usamos headers de navegador real
  - esperamos unos segundos entre pedidos
  - está pensado para correr con poca frecuencia (cada 3+ horas)
Aun así puede dejar de funcionar en cualquier momento si Mercado Libre cambia
el diseño de la página o empieza a bloquear la IP desde la que corre. Si eso
pasa, hay que revisar y ajustar los selectores de HTML en `parse_cards()`.

La URL de búsqueda ya viene con los filtros aplicados desde la propia web de
Mercado Libre (año, precio, km, transmisión), así que el bot no tiene que
adivinar esos filtros: solo lee la lista y detecta publicaciones nuevas.

Pensado para correr periódicamente vía GitHub Actions, pero también
se puede correr a mano con: python ml_bot.py
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------------
# CONFIGURACIÓN DE LA BÚSQUEDA
# ------------------------------------------------------------------
# Esta URL ya tiene aplicados: Chevrolet Onix, desde 2020, precio 0-24.000.000 ARS,
# 9.999-55.555 km, transmisión automática. Para cambiar los filtros, navegá en
# autos.mercadolibre.com.ar, aplicalos ahí, y pegá la URL resultante acá.
SEARCH_URL = (
    "https://autos.mercadolibre.com.ar/chevrolet/onix/automatica/desde-2020/"
    "_PriceRange_0ARS-24000000ARS_KILOMETERS_9999km-55555km_NoIndex_True"
)

MAX_PAGES = 3                       # tope de paginación por corrida (seguridad)
DELAY_BETWEEN_REQUESTS = (3, 7)     # segundos, rango aleatorio (mín, máx)

# ------------------------------------------------------------------
# CONFIGURACIÓN DE TELEGRAM (se leen de variables de entorno / secrets)
# ------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SEEN_IDS_FILE = Path(__file__).parent / "seen_ids.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

ITEM_ID_RE = re.compile(r"(MLA-?\d{6,})", re.IGNORECASE)


def sleep_a_bit() -> None:
    time.sleep(random.uniform(*DELAY_BETWEEN_REQUESTS))


def load_seen_ids() -> set:
    if SEEN_IDS_FILE.exists():
        try:
            return set(json.loads(SEEN_IDS_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_seen_ids(ids: set) -> None:
    SEEN_IDS_FILE.write_text(
        json.dumps(sorted(ids), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def extract_item_id(url: str) -> str:
    match = ITEM_ID_RE.search(url)
    return match.group(1).upper().replace("MLA-", "MLA") if match else url


def fetch_html(url: str) -> str | None:
    resp = requests.get(url, headers=HEADERS, timeout=25)
    if resp.status_code != 200:
        print(f"[WARN] {url} devolvió status {resp.status_code}")
        return None
    return resp.text


def parse_cards(html: str) -> list:
    """
    Extrae las publicaciones de una página de resultados.

    NOTA: los nombres de clases CSS de Mercado Libre cambian con el tiempo.
    Si esto deja de encontrar resultados, hay que:
      1. Correr el bot localmente y guardar `debug.html` (ver abajo en main()).
      2. Abrir ese archivo, buscar el bloque de una publicación individual.
      3. Actualizar los selectores de esta función.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Intentamos varios selectores conocidos/históricos de ML, en orden.
    candidate_selectors = [
        "li.ui-search-layout__item",
        "div.ui-search-result__wrapper",
        "div.ui-search-result",
        "article",
    ]
    cards = []
    for selector in candidate_selectors:
        found = soup.select(selector)
        if found:
            cards = found
            break

    listings = []
    for card in cards:
        link_tag = card.select_one("a[href]")
        if not link_tag:
            continue
        link = link_tag.get("href", "")
        if "mercadolibre.com" not in link and "mercadolibre.com.ar" not in link:
            continue

        title_tag = (
            card.select_one("h2")
            or card.select_one(".ui-search-item__title")
            or link_tag
        )
        title = title_tag.get_text(strip=True) if title_tag else "Sin título"

        full_text = card.get_text(" ", strip=True)

        price_match = re.search(r"\$\s*([\d\.]{4,12})", full_text)
        price = price_match.group(1) if price_match else "?"

        year_match = re.search(r"\b(19|20)\d{2}\b", full_text)
        year = year_match.group(0) if year_match else "?"

        km_match = re.search(r"([\d\.]{1,3}(?:\.\d{3})*)\s*Km", full_text, re.IGNORECASE)
        km = km_match.group(1) if km_match else "?"

        transmission = "?"
        lowered = full_text.lower()
        if "automátic" in lowered or "automatic" in lowered:
            transmission = "Automática"
        elif "manual" in lowered:
            transmission = "Manual"

        listings.append(
            {
                "id": extract_item_id(link),
                "title": title,
                "link": link.split("#")[0],
                "price": price,
                "year": year,
                "km": km,
                "transmission": transmission,
            }
        )
    return listings


def find_next_page_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    next_link = soup.select_one('a[title="Siguiente"]') or soup.select_one(
        "a.andes-pagination__link[rel='next']"
    )
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])
    return None


def notify_telegram(item: dict) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[INFO] (sin Telegram configurado) Nuevo match: {item['link']}")
        return

    text = (
        f"🚗 *{item['title']}*\n"
        f"Año: {item['year']} | Km: {item['km']} | {item['transmission']}\n"
        f"Precio: $ {item['price']}\n"
        f"{item['link']}"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code != 200:
        print(f"[WARN] error enviando a Telegram: {resp.status_code} {resp.text[:300]}")


def main() -> int:
    seen_ids = load_seen_ids()
    all_listings = []

    url = SEARCH_URL
    for page in range(MAX_PAGES):
        html = fetch_html(url)
        if not html:
            break

        # Guardamos el HTML crudo para poder diagnosticar los selectores.
        Path("debug.html").write_text(html, encoding="utf-8")

        listings = parse_cards(html)
        print(f"[INFO] página {page + 1}: {len(listings)} publicaciones encontradas.")
        all_listings.extend(listings)

        next_url = find_next_page_url(html, url)
        if not next_url or not listings:
            break
        url = next_url
        sleep_a_bit()

    print(f"[INFO] {len(all_listings)} publicaciones totales encontradas.")

    new_matches = 0
    for item in all_listings:
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        new_matches += 1
        notify_telegram(item)

    save_seen_ids(seen_ids)
    print(f"[INFO] {new_matches} publicaciones nuevas notificadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
