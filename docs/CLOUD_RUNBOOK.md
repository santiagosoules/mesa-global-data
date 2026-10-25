# Operación cloud de Mesa Global Data

## Componentes

- GitHub Actions ejecuta Python 3.12 sin dependencias externas.
- SQLite conserva observaciones, revisiones, ejecuciones y chequeos por fuente sólo durante la ejecución privada del runner.
- El historial JSON público reconstruye la SQLite transitoria al comienzo de cada run.
- GitHub Pages entrega JSON estático de solo lectura.
- Mesa Global consulta únicamente `site_bundle.json` mediante su ruta servidor `/api/intel`.

## Cadencia

| Perfil | Fuentes | Programación UTC | Semántica |
|---|---|---|---|
| `daily` | Treasury, NY Fed, OFR | 23:20 lunes a viernes | Actualiza tasas, ON RRP y componentes públicos de estrés financiero. |
| `h41` | Federal Reserve H.4.1 | 23:35 jueves | Actualiza balance, TGA y reservas después de la publicación semanal. |
| `weekly` | CFTC TFF | 23:50 viernes | Posiciones del martes publicadas normalmente el viernes. |

También existe `workflow_dispatch` con perfiles `daily`, `h41`, `weekly` y `all` para una prueba
controlada o recuperación.

## Fallos

1. Cada descarga usa HTTPS, tres intentos y límites de conexión/tiempo.
2. Una fuente fallida no reemplaza observaciones válidas ni escribe ceros.
3. El bundle conserva el último dato válido con `source_error` y fecha efectiva, sin publicar el error interno.
4. Validación bloquea valores inválidos, unidades, rangos y reconciliaciones CFTC fuera de tolerancia.
5. Los diagnósticos detallados permanecen en la SQLite privada y en los logs de Actions.
6. INTEL rechaza un bundle sin los 12 sensores y usa su snapshot de respaldo.

## Seguridad y coste

- No hay claves para Treasury, Federal Reserve, NY Fed, OFR o CFTC.
- Las series ICE BofA/FRED con redistribución restringida no se publican.
- El repositorio y Pages sólo contienen código y datos públicos; no se suben secretos.
- La base SQLite y sus archivos WAL/SHM están excluidos explícitamente del repositorio.
- `MESA_INTEL_DATA_URL` es una variable no secreta configurada en el backend de Sites.
- No existe endpoint de escritura público ni ejecución de órdenes.
- La solución usa los niveles gratuitos de GitHub Actions/Pages para un repositorio
  público, sujetos a los límites vigentes de la cuenta.

## Activación

1. Crear un repositorio público dedicado, por ejemplo `mesa-global-data`.
2. Subir la rama `main` y habilitar Pages con origen **GitHub Actions**.
3. Ejecutar manualmente el perfil `all` y verificar que Pages entregue HTTP 200.
4. Configurar `MESA_INTEL_DATA_URL` en Sites.
5. Construir y probar INTEL; guardar una versión sin desplegar hasta aprobación.
