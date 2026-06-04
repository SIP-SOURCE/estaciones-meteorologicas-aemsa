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

    if nombre == "Hola_Mojada":
        nombre = "Hoja_Mojada"

    return nombre


def obtener_valor(celda):
    if celda is None:
        return None

    if "f" in celda:
        return celda["f"]

    return celda.get("v")


def convertir_numero(valor):
    if valor is None:
        return None

    texto = str(valor).strip()

    if texto == "":
        return None

    texto = texto.lower()
    texto = texto.replace("°c", "")
    texto = texto.replace("°", "")
    texto = texto.replace("c", "")
    texto = texto.replace("km/h", "")
    texto = texto.replace("mm", "")
    texto = texto.replace("%", "")
    texto = texto.strip()
    texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return None


def tiene_dato(valor):
    if valor is None:
        return False

    if isinstance(valor, str) and valor.strip() == "":
        return False

    return True


def eliminar_campos_vacios(features):
    campos_con_datos = set()

    for feature in features:
        props = feature.get("properties", {})
        for campo, valor in props.items():
            if tiene_dato(valor):
                campos_con_datos.add(campo)

    for feature in features:
        props = feature.get("properties", {})
        feature["properties"] = {
            campo: valor
            for campo, valor in props.items()
            if campo in campos_con_datos
        }

    return features


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

        temperatura_num = convertir_numero(atributos.get("Temperatura"))
        humedad_num = convertir_numero(atributos.get("Humedad"))
        punto_rocio_num = convertir_numero(atributos.get("Punto_de_Rocio"))
        precipitacion_num = convertir_numero(atributos.get("Precipitacion"))
        direccion_viento_num = convertir_numero(atributos.get("Direccion_del_Viento"))
        velocidad_viento_num = convertir_numero(atributos.get("Velocidad_del_Viento"))
        hoja_mojada_num = convertir_numero(atributos.get("Hoja_Mojada"))
        radiacion_num = convertir_numero(atributos.get("Radiacion"))

        atributos["Temperatura_num"] = temperatura_num
        atributos["Humedad_num"] = humedad_num
        atributos["Punto_de_Rocio_num"] = punto_rocio_num
        atributos["Precipitacion_mm_num"] = precipitacion_num
        atributos["Direccion_del_Viento_num"] = direccion_viento_num
        atributos["Velocidad_del_Viento_kmh_num"] = velocidad_viento_num
        atributos["Hoja_Mojada_num"] = hoja_mojada_num
        atributos["Radiacion_num"] = radiacion_num

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

    features = eliminar_campos_vacios(features)

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
    print("Campos numéricos agregados:")
    print([
        "Temperatura_num",
        "Humedad_num",
        "Punto_de_Rocio_num",
        "Precipitacion_mm_num",
        "Direccion_del_Viento_num",
        "Velocidad_del_Viento_kmh_num",
        "Hoja_Mojada_num",
        "Radiacion_num"
    ])


if __name__ == "__main__":
    main()
