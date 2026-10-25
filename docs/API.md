# Contrato de integración local

Versión de esquema: `1.1.0`.

La API es de solo lectura y devuelve JSON. No incluye endpoints de publicación, alertas, broker ni ejecución. El contrato puede colocarse detrás de un backend autenticado en una etapa posterior; no deben exponerse archivos SQLite directamente desde el frontend.

## Observación normalizada

```json
{
  "sensor_id": "us10y_yield",
  "value": 5.0,
  "unit": "percent",
  "source": "U.S. Department of the Treasury",
  "source_identifier": "treasury:BC_10YEAR",
  "source_url": "https://home.treasury.gov/...",
  "as_of": "2026-10-23",
  "publication_date": "2026-10-23",
  "retrieved_at": "2026-10-25T07:00:00+00:00",
  "instrument": "U.S. Treasury 10-Year Constant Maturity",
  "frequency": "daily",
  "quality": "official_primary",
  "data_kind": "observed",
  "latency": "publication",
  "access": "public",
  "status": "ok",
  "methodology": "Official Treasury daily par yield curve field BC_10YEAR.",
  "metadata": {}
}
```

El ejemplo describe la forma del dato. Los archivos generados por la ingesta contienen los valores efectivamente recuperados y deben usarse para validar cualquier integración.

## Estados de cobertura

`GET /api/market/coverage` informa los 12 sensores configurados, cantidad de observaciones, último `as_of`, consulta, salud normalizada de las cinco familias de fuentes y validación completa. Un sensor sin datos no recibe valor cero: queda sin observaciones y aparece como `missing_sensor`.

## Históricos

`GET /api/market/series/{sensor_id}` devuelve las revisiones e históricos almacenados, ordenados por fecha efectiva descendente. SQLite conserva revisiones de trabajo de forma privada. El bundle público conserva una observación vigente por fecha y todo el historial necesario para reconstruir la base privada del siguiente runner.

## Análisis

`GET /api/market/analyses` expone análisis reproducibles basados en observaciones almacenadas. La primera implementación incluye la reconciliación COT NQ/MNQ con evidencia, códigos, fórmula y redondeo.

