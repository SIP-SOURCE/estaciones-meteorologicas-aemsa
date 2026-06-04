import json
import re
import unicodedata
from datetime import datetime, timezone

import requests


URL = "https://docs.google.com/spreadsheets/d/1muQespa15yZStWXf4OOfP3upij4IE3_XqydbhlRMvS4/gviz/tq?tqx=out:json&sheet=Mapa%20Estaciones"
SALIDA = "estaciones_meteorologicas.geojson"


def extraer_json_gviz(texto):
    match = re.search(
        r"google\.visualization\.Query\.setResponse\((.*)\);?",
        texto,
        re.DOTALL
    )
    if not match:
        raise ValueError("No se pudo interpretar la respuesta GViz.")
    return json.loads(match.group(1))


def limpiar_nombre_campo(nombre):
    if not nombre:
        return "campo"

    nombre = str(nombre).strip()
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(c for c in nombre if not unicodedata.combining(c))
    nombre = re.sub(r"[^A-Za-z0-9_]+", "_", nombre)
    nombre = re.sub(r"_+", "_", nombre).strip("_")

    if not nombre:
        nombre = "campo"

    if nombre[0].isdigit():
        nombre = f"campo_{nombre}"

    return nombre


def obtener_valor(celda):
    if celda is None:
        return None

    if "f" in celda:
        return celda["f"]

    return celda.get("v")


def main():
    print("Descargando datos...")

    r = requests.get(URL, timeout=30)
    r.raise_for_status()

    data = extraer_json_gviz(r.text)

    columnas_originales = data["table"]["cols"]
    rows = data["table"]["rows"]

    columnas = []

    for i, col in enumerate(columnas_originales):
        label = col.get("label") or f"campo_{i}"
        campo_limpio = limpiar_nombre_campo(label)

        if campo_limpio in columnas:
            campo_limpio = f"{campo_limpio}_{i}"

        columnas.append(campo_limpio)

    features = []

    for row in rows:
        atributos = {}

        for idx, campo in enumerate(columnas):
            try:
                celda = row["c"][idx]
                atributos[campo] = obtener_valor(celda)
            except Exception:
                atributos[campo] = None

        coords = atributos.get("Coordenadas")

        if not coords:
            continue

        try:
            lat_txt, lon_txt = str(coords).split(",")
            lat = float(lat_txt.strip())
            lon = float(lon_txt.strip())
        except Exception:
            continue

        if lat == 0 or lon == 0:
            continue

        atributos["Latitud"] = lat
        atributos["Longitud"] = lon
        atributos["actualizacion_geojson_utc"] = datetime.now(timezone.utc).isoformat()

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": atributos
        }

        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "name": "estaciones_meteorologicas",
        "features": features
    }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print("GeoJSON generado:", SALIDA)
    print("Total estaciones:", len(features))
    print("Campos exportados:", columnas)


if __name__ == "__main__":
    main()
