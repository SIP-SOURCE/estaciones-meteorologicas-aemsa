import json
import re
from datetime import datetime, timezone

import requests


URL = "https://docs.google.com/spreadsheets/d/1muQespa15yZStWXf4OOfP3upij4IE3_XqydbhlRMvS4/gviz/tq?tqx=out:json&sheet=Mapa%20Estaciones"
SALIDA = "estaciones_meteorologicas.geojson"


def extraer_json_gviz(texto):
    match = re.search(r"google\.visualization\.Query\.setResponse\((.*)\);?", texto, re.DOTALL)
    if not match:
        raise ValueError("No se pudo interpretar la respuesta GViz de Google Sheets.")
    return json.loads(match.group(1))


def valor(row, idx, campo="v"):
    try:
        celda = row["c"][idx]
        if celda is None:
            return None
        return celda.get(campo)
    except Exception:
        return None


def main():
    print("Descargando Google Sheet...")
    r = requests.get(URL, timeout=30)
    r.raise_for_status()

    data = extraer_json_gviz(r.text)
    rows = data["table"]["rows"]

    features = []

    for row in rows:
        nombre = valor(row, 0, "v")
        coords_text = valor(row, 1, "v")

        if not nombre or not coords_text:
            continue

        try:
            lat_txt, lon_txt = str(coords_text).split(",")
            lat = float(lat_txt.strip())
            lon = float(lon_txt.strip())
        except Exception:
            continue

        if lat == 0 or lon == 0:
            continue

        fecha = valor(row, 2, "f") or valor(row, 2, "v")
        precipitacion = valor(row, 6, "v")
        direccion = valor(row, 8, "v")
        viento = valor(row, 9, "v")

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "estacion": nombre,
                "fecha": fecha,
                "precipitacion_mm": precipitacion,
                "direccion_viento_grados": direccion,
                "viento_kmh": viento,
                "actualizado_geojson_utc": datetime.now(timezone.utc).isoformat()
            }
        }

        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "name": "estaciones_meteorologicas",
        "features": features
    }

    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"GeoJSON generado: {SALIDA}")
    print(f"Total estaciones: {len(features)}")


if __name__ == "__main__":
    main()