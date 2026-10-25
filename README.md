# Mesa Global Data

Implementación independiente y de solo lectura para recopilar, normalizar, validar y almacenar sensores institucionales públicos de NQ/MNQ. No modifica la skill instalada, no publica en Mesa Global y no contiene ejecución de órdenes.

## Sensores conectados

| Sensor | Identificador oficial principal | Fuente |
|---|---|---|
| `us2y_yield` | `BC_2YEAR` | U.S. Treasury XML |
| `us10y_yield` | `BC_10YEAR` | U.S. Treasury XML |
| `us10y_real_yield` | `TC_10YEAR` | U.S. Treasury XML |
| `fed_balance_assets` | `RESPPMA_N.WW` | Federal Reserve H.4.1 DDP |
| `tga_balance` | `RESPPLLDT_N.WW` | Federal Reserve H.4.1 DDP |
| `on_rrp_usage` | fixed-rate overnight reverse repo results | New York Fed Markets API |
| `bank_reserves` | `RESH4R_N.WW` | Federal Reserve H.4.1 DDP |
| `ofr_fsi_credit` | `Credit` | OFR Financial Stress Index |
| `ofr_fsi_us` | `United States` | OFR Financial Stress Index |
| `nq_cot_leveraged_funds_net` | `209742`, `209747`, `20974+` | CFTC TFF Futures Only |
| `nq_cot_asset_manager_net` | `209742`, `209747`, `20974+` | CFTC TFF Futures Only |
| `nq_cot_open_interest` | `209742`, `209747`, `20974+` | CFTC TFF Futures Only |

No se requieren credenciales. Las dos series ICE BofA OAS se excluyeron porque su
redistribución requiere autorización previa. En su lugar se publican dos componentes
agregados del OFR Financial Stress Index, con identificadores y unidades propios para no
presentarlos como OAS.

## Ejecutar

Desde esta carpeta:

```bash
PYTHONPATH=src python3 -m mesa_global_data collect
PYTHONPATH=src python3 -m mesa_global_data collect --profile daily
PYTHONPATH=src python3 -m mesa_global_data collect --profile weekly
PYTHONPATH=src python3 -m unittest discover -s tests -v
RUN_NETWORK_TESTS=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m mesa_global_data validate
```

La ingesta crea una SQLite privada y transitoria en el runner y exporta JSON en
`data/exports/`. `*.sqlite` está excluido por `.gitignore` y nunca se agrega al
repositorio ni al artefacto de Pages. El archivo
`site_bundle.json` contiene los 12 sensores, sus históricos primarios sin revisiones
duplicadas, último valor, observación anterior y delta reproducible para INTEL.

## Actualización independiente

`.github/workflows/update-institutional-data.yml` ejecuta recopilación, pruebas,
validación y persistencia en un runner de GitHub Actions. Antes de cada ingesta, el
runner reconstruye la SQLite privada desde el historial JSON público. El perfil `daily`
consulta Treasury, NY Fed y OFR de lunes a viernes a las 23:20 UTC; `h41` consulta la
Reserva Federal los jueves a las 23:35 UTC; `weekly` consulta CFTC los viernes a las
23:50 UTC. GitHub Pages expone `public/site_bundle.json` como endpoint
estático y versionado. No requiere una Mac encendida, Codex ni credenciales para las
fuentes oficiales.

Si una fuente falla, el pipeline conserva el último dato válido, publica el estado
`source_error` con la fecha efectiva real. Los otros estados son `updated`, `delayed` y
`unavailable`. Los errores y diagnósticos detallados quedan sólo en la SQLite privada y
en los logs de Actions; el JSON público expone únicamente un estado normalizado.

La activación requiere un repositorio GitHub dedicado con Pages configurado para GitHub
Actions. Luego se define en Sites:

```text
MESA_INTEL_DATA_URL=https://<usuario>.github.io/<repositorio>/site_bundle.json
```

INTEL valida esquema y cobertura antes de aceptar el bundle remoto; si falla, conserva
el snapshot local de respaldo e identifica el error del endpoint.

## API de integración

```bash
PYTHONPATH=src python3 -m mesa_global_data serve --host 127.0.0.1 --port 8787
```

Endpoints de solo lectura:

- `GET /health`
- `GET /api/market/coverage`
- `GET /api/market/observations?ids=us10y_yield,tga_balance&limit=100`
- `GET /api/market/series/{sensor_id}?limit=500`
- `GET /api/market/analyses`

El servidor local permite CORS únicamente para `https://mesa-global.santiago-soules.chatgpt.site`. Esto prepara el contrato, pero no significa que el sitio tenga conectividad de red hacia este proceso local. No se realizó publicación ni edición del sitio.

## Metodología COT

NQ tiene un multiplicador de USD 20 por punto y MNQ de USD 2 por punto. La normalización correcta es:

```text
NQ equivalente = contratos NQ + contratos MNQ × (2 / 20)
               = contratos NQ + contratos MNQ × 0,1
```

Para cada semana, el pipeline calcula el neto y el cambio de NQ y MNQ por separado, convierte MNQ a equivalentes NQ y exige que el resultado coincida, con tolerancia de un contrato por redondeo, con la serie oficial consolidada `20974+`. Una discrepancia mayor aborta ese conector.

Para el 20/10/2026:

```text
NQ Leveraged Funds neto                 =  51.749 - 50.799 =       +950
MNQ Leveraged Funds neto                =   8.979 - 95.360 =    -86.381
MNQ en equivalentes NQ                  = -86.381 × 0,1    =   -8.638,1
Consolidado derivado                    = 950 - 8.638,1    =   -7.688,1
Consolidado CFTC 20974+                 =  48.053 - 55.741 =     -7.688
Cambio semanal derivado equivalente NQ  = 12.543 + 16.597×0,1 = +14.202,7
Cambio semanal CFTC 20974+              = 4.275 - (-9.928) =    +14.203
```

La diferencia de 0,1/0,3 contrato responde al redondeo a contratos enteros de la serie consolidada.

## Calidad y trazabilidad

Cada observación conserva sensor, valor, unidad, fuente, URL, identificador original, fecha efectiva, fecha de publicación, consulta UTC, instrumento, frecuencia, calidad, latencia, acceso, metodología y metadatos originales/reconciliados.

Las pruebas y validaciones cubren:

- campos obligatorios, unidad y rango;
- sensor ausente y dato obsoleto;
- fecha de publicación anterior a la fecha efectiva;
- integridad, fechas, unidades y rangos de las series oficiales;
- reconciliación CFTC NQ + MNQ/10 vs `20974+`;
- fallos de fuente y estado de cobertura.

Las fechas de publicación históricas se conservan con su método: `Last-Modified` oficial para la última entrega cuando está disponible, o la cadencia documentada de la fuente para filas históricas. No se presenta una fecha derivada como timestamp observado.

