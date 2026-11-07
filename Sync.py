
import os
import time
import secrets
import requests

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Supabase connection
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"]
)

# LCSC API credentials
LCSC_API_KEY = os.environ["LCSC_API_KEY"]

BASE_URL = "https://ips.lcsc.com"
TABLE = "lcsc_components"

BATCH_SIZE = 100


def make_lcsc_signature(params):
    """
    IMPORTANT:
    Implement the exact signature algorithm specified
    in your approved LCSC API account documentation.

    Do not guess the signing algorithm.
    """
    raise NotImplementedError(
        "Add the official LCSC signature algorithm here."
    )


def get_signed_params(extra=None):
    params = {
        "key": LCSC_API_KEY,
        "nonce": secrets.token_hex(8),
        "timestamp": str(int(time.time() * 1000))
    }

    if extra:
        params.update(extra)

    params["signature"] = make_lcsc_signature(params)
    return params


def fetch_components(keyword, page=1):
    url = f"{BASE_URL}/rest/wmsc2agent/search/product"

    params = get_signed_params({
        "keyword": keyword,
        "current_page": page,
        "page_size": 30
    })

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()
    return response.json()


def normalize_component(item):
    return {
        "lcsc_part_number": str(
            item.get("lcscPartNumber")
            or item.get("lcsc_part_number")
            or item.get("productCode")
        ),
        "product_id": str(
            item.get("productId", "")
        ),
        "manufacturer": item.get("brandName"),
        "mpn": item.get("productModel"),
        "component_name": item.get("productName"),
        "description": item.get("description"),
        "package": item.get("encapStandard"),
        "datasheet_url": item.get("pdfUrl"),
        "image_url": item.get("productImageUrl"),
        "stock": item.get("stockNumber"),
        "price": item.get("productPrice"),
        "raw_data": item
    }


def insert_batch(components):
    if not components:
        return

    supabase.table(TABLE).upsert(
        components,
        on_conflict="lcsc_part_number"
    ).execute()

    print(f"Uploaded {len(components)} components")


def sync_keyword(keyword):
    page = 1
    batch = []

    while True:
        print(f"Fetching {keyword}, page {page}")

        result = fetch_components(keyword, page)

        # Adjust this extraction to the actual
        # response structure returned by your API.
        items = (
            result.get("data", {}).get("list", [])
            if isinstance(result.get("data"), dict)
            else []
        )

        if not items:
            break

        for item in items:
            component = normalize_component(item)

            if component["lcsc_part_number"] not in ("None", ""):
                batch.append(component)

        if len(batch) >= BATCH_SIZE:
            insert_batch(batch)
            batch = []

        if len(items) < 30:
            break

        page += 1
        time.sleep(1)

    if batch:
        insert_batch(batch)


if __name__ == "__main__":

    keywords = [
        "Resistor",
        "Capacitor",
        "Diode",
        "LED",
        "Transistor",
        "MOSFET",
        "Microcontroller",
        "Connector",
        "Sensor",
        "Integrated Circuit"
    ]

    for keyword in keywords:
        try:
            sync_keyword(keyword)
        except Exception as error:
            print(f"Error for {keyword}: {error}")

    print("LCSC synchronization finished!")

