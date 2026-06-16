# Dashboard de Lesiones no Fatales de Causa Externa

Visualización interactiva de ~243.000 registros de la API abierta [Lesiones no Fatales](https://www.datos.gov.co/Justicia-y-Derecho/Lesiones-no-fatales-de-causa-externa-Informaci-n-p/79dd-d24f/about_data) de la **República de Colombia** (datos.gob.co) — dataset `79dd-d24f`.

## Requisitos

- Docker + Docker Compose

## Inicio rápido

```bash
docker compose up -d --build
```

Abrir [http://localhost:8015](http://localhost:8015)

## Funcionalidades

### Filtros
- **Departamento** — dropdown poblado desde nombres canónicos del GeoJSON
- **Municipio** — se filtra al seleccionar un departamento
- **Año** — extraído del campo `a_o_del_hecho`

### Tarjetas de resumen
- Total de registros
- Identidad de Género (normalizado: "Femenino", "Masculino", "No aplica", "No sabe / No informa")
- Orientación Sexual
- Días de Incapacidad (top 4)

### Mapa
- Burbujas por municipio usando centroides reales del GeoJSON colombiano
- Código DANE municipio → `MPIO_CCNCT` (join como entero)
- Nombres de departamentos como fuente canónica desde el GeoJSON (tildes, ñ, etc.)

### Gráficas (Chart.js)
| Gráfica | Tipo |
|---|---|
| Tendencia por Año | Barra |
| Grupo de Edad | Barra |
| Contexto de Violencia | Barra horizontal |
| Tendencia Mensual | Línea |
| Escenario del Hecho | Dona |
| Mecanismo Causal | Barra horizontal |
| Días de Incapacidad | Polar Area |
| Identidad de Género | Pastel |

### Informe Word
- Descarga un documento `.docx` con portada, tablas, resumen ejecutivo, análisis por contexto, distribución geográfica, mecanismos, escenarios, conclusiones y recomendaciones.
- Los resúmenes y análisis son generados por **OpenRouter AI** (modelo `nvidia/nemotron-3-ultra-550b-a55b:free`).
- Respeta los filtros activos (departamento, municipio, año).

## Arquitectura

```
.
├── Dockerfile                    # Python 3.11-slim
├── docker-compose.yml            # Puerto 8015, settings module
├── requirements.txt              # Django 4.2, requests, python-docx, python-dotenv
├── manage.py                     # Django management
├── .env                          # OPENROUTER_API_KEY, OPENROUTER_MODEL
│
├── data_dashboard_project/       # Configuración Django
│   ├── settings.py
│   ├── urls.py                   # → dashboard.urls
│   └── wsgi.py
│
├── dashboard/                    # App principal
│   ├── views.py                  # API endpoints: /api/filters/, /api/data/, /api/report/
│   ├── urls.py
│   └── templates/dashboard.html  # Frontend (Leaflet + Chart.js desde CDN)
│
├── data_fetching_service.py      # SODA API paginación + GeoJSON centroides
├── report_service.py             # Generación de informe Word con OpenRouter AI
└── README.md
```

## API Endpoints

| Endpoint | Parámetros | Descripción |
|---|---|---|
| `/` | — | Dashboard HTML |
| `/api/filters/` | — | Departamentos, municipios, años disponibles |
| `/api/data/` | `departamento`, `municipio`, `year` | Datos filtrados para gráficas + mapa |
| `/api/report/` | `departamento`, `municipio`, `year` | Descarga informe Word |

## Join GeoJSON ↔ SODA

El join se realiza mediante el código DANE de municipio convertido a entero:

- **GeoJSON**: `MPIO_CCNCT` → `int()` — ej: `"08001"` → `8001`
- **SODA**: `codigo_dane_municipio` → `int()` — ej: `"08001"` → `8001`

Si el código no existe en el GeoJSON, se usa el nombre original del registro SODA como fallback.

Los nombres de departamento (`DPTO_CNMBR`) y municipio (`MPIO_CNMBR`) del GeoJSON se usan como fuente canónica, garantizando tildes y caracteres especiales correctos.

## Caché

- **Registros SODA**: `/tmp/records_cache.json` (se descarga una vez)
- **Centroides GeoJSON**: `/tmp/municipios_geojson_cache.json` (se descarga una vez, ~30 MB, con reintentos)

Para forzar actualización: eliminar los archivos y reiniciar el contenedor.

## Personalización

Editar `.env` para cambiar:
- `OPENROUTER_API_KEY` — clave de API de OpenRouter
- `OPENROUTER_MODEL` — modelo de IA para los informes

## Puerto

El dashboard corre en el puerto **8015** (`localhost:8015`). Cambiar en `docker-compose.yml` si es necesario.
