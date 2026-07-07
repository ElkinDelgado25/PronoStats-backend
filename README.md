# PronoStats-backend

API REST de **PronoStats**: pronosticos deportivos basados en estadisticas historicas.
Construida con **FastAPI + SQLAlchemy**. Los datos de negocio (ligas, equipos y
partidos) provienen de **datasets CSV** que se leen en memoria en cada arranque;
la base de datos solo se usa para autenticacion de usuarios.

## Requisitos

- Python 3.10+ (probado con 3.13)

## Instalacion

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # (Windows: copy .env.example .env)
```

## Origen de los datos: datasets CSV (data/dataset_futbol/)

Los datos deportivos NO se guardan en la base de datos. Viven en dos archivos CSV
dentro de `data/dataset_futbol/` y la aplicacion los **relee desde disco en cada arranque** del
backend (en el `lifespan` de FastAPI), cargandolos en memoria mediante el
proveedor `app/csv_store.py`. Asi, para cambiar los datos basta con editar o
regenerar los CSV y reiniciar el servidor; no hay que tocar ninguna BD.

### `data/dataset_futbol/equipos.csv`

Equipos de la liga principal de varios paises de America.

| Columna | Descripcion |
| --- | --- |
| `equipo_id` | Identificador unico del equipo (entero) |
| `nombre` | Nombre del equipo |
| `liga` | Nombre de la liga a la que pertenece |
| `pais` | Pais de la liga |
| `fuerza` | Rating base (0..1) usado por el modelo de goles al generar el dataset |

Ligas incluidas: **Liga Profesional** (Argentina), **Brasileirao Serie A** (Brasil),
**Liga MX** (Mexico), **LigaPro Serie A** (Ecuador), **Categoria Primera A**
(Colombia) y **MLS** (Estados Unidos), con 8 equipos cada una.

### `data/dataset_futbol/goles.csv`

Dataset de goles por partido. Contiene partidos **finalizados** (con marcador,
para calcular estadisticas y el porcentaje de acierto) y **programados**
(sin marcador, para pronosticar).

| Columna | Descripcion |
| --- | --- |
| `partido_id` | Identificador unico del partido |
| `liga` | Nombre de la liga |
| `equipo_local_id` | `equipo_id` del equipo local |
| `equipo_visitante_id` | `equipo_id` del equipo visitante |
| `fecha` | Fecha/hora ISO 8601 |
| `estado` | `finalizado` o `programado` |
| `goles_local` | Goles del local (vacio si `programado`) |
| `goles_visitante` | Goles del visitante (vacio si `programado`) |

### Regenerar los CSV

Los datasets se generan de forma **determinista** (semilla fija) con un modelo de
goles de Poisson basado en la `fuerza` de cada equipo:

```bash
python -m app.generate_dataset
```

Esto sobreescribe `data/dataset_futbol/equipos.csv` y `data/dataset_futbol/goles.csv`. Reinicia el backend para
que vuelva a leerlos. (El script solo escribe archivos; no toca la base de datos.)

### Agregar nuevos datasets

Cada conjunto de datos vive en su propia carpeta bajo `data/` (por ejemplo
`data/dataset_futbol/`). Para un nuevo deporte o competicion:

1. Crea una carpeta como `data/dataset_basquet/` con sus CSV (`equipos.csv`,
   `goles.csv` u otros archivos segun el caso).
2. Ajusta `DATASET_DIR` en `app/csv_store.py` (y en `app/generate_dataset.py`
   si tienes un generador) para apuntar a la nueva carpeta.
3. Reinicia el backend para que recargue los archivos.

### Como se calcula el porcentaje de acierto

Al cargar los CSV, el proveedor pronostica cada partido **finalizado** usando el
motor de reglas (`app/services/prediction_engine.py`) con la forma reciente y el
promedio de goles calculados **unicamente con los partidos anteriores a la fecha
de ese partido** (sin fuga de informacion). Luego compara el resultado predicho
(1/X/2) con el resultado real:

```
porcentaje_de_acierto (precision) = aciertos / total_de_partidos_finalizados
```

El endpoint `GET /stats/model-performance` devuelve `aciertos`, `fallos`,
`precision` (0..1) y una `tendencia` acumulada agregada por dia.

## Base de datos (solo autenticacion)

La BD (SQLAlchemy) se usa solo para usuarios/auth. Configura `DATABASE_URL` en
`.env`; si conserva el valor `BDD_CLOUD` (o vacio), se usa SQLite local
(`pronostats_dev.db`). Las tablas se crean automaticamente al iniciar.

## Ejecutar

```bash
# (Opcional) regenerar los datasets CSV
python -m app.generate_dataset

# Levantar el servidor (relee los CSV en cada arranque)
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentacion interactiva (Swagger): http://localhost:8000/docs

## Contrato de la API (resumen)

Datos deportivos servidos desde el proveedor CSV:

| Metodo | Ruta | Descripcion | HU |
| --- | --- | --- | --- |
| GET | `/leagues` | Listar ligas | HU-04 |
| GET | `/matches` | Catalogo de partidos (filtros liga/fecha/estado) | HU-04, HU-05 |
| GET | `/matches/{id}` | Detalle de partido | HU-04 |
| GET | `/matches/{id}/h2h` | Historial entre equipos | HU-06 |
| GET | `/matches/{id}/prediction` | Pronostico 1X2 + factores + confianza | HU-07, HU-08, HU-09 |
| GET | `/teams` | Listar equipos | - |
| GET | `/teams/{id}/stats` | Estadisticas historicas de un equipo | HU-12 |
| GET | `/stats/model-performance` | Aciertos vs fallos (porcentaje de acierto) | Panel metricas |

Autenticacion y administracion (base de datos):

| Metodo | Ruta | Descripcion | HU |
| --- | --- | --- | --- |
| POST | `/auth/register` | Registro | HU-01 |
| POST | `/auth/login` | Inicio de sesion | HU-02 |
| POST | `/auth/forgot-password` | Recuperar contrasena | HU-03 |
| GET | `/favorites` `POST` `DELETE` | Favoritos del usuario | HU-13 |
| POST/PUT/DELETE | `/admin/...` | CRUD administrativo (BD) | HU-15, HU-16, HU-17 |

> Nota: los endpoints de datos deportivos leen del CSV; los de `/admin` operan
> sobre la BD y son independientes del dataset CSV.

## Estructura

```
app/
  main.py              # App FastAPI + routers + CORS + carga CSV en lifespan
  csv_store.py         # Proveedor de datos CSV en memoria (ligas/equipos/partidos/predicciones/metricas)
  generate_dataset.py  # Generador determinista de los CSV
  core/                # config (settings) y seguridad (JWT)
  db/                  # engine, session, Base (solo auth)
  models/              # SQLAlchemy: usuario, liga, equipo, partido, resultado, prediccion, favorito
  schemas/             # Pydantic (contrato de la API)
  api/                 # routers: auth, leagues, teams, matches, predictions, favorites, stats, admin
  services/            # prediction_engine (compute_prediction), evaluation, team_stats
data/
  dataset_futbol/
    equipos.csv        # equipos de las ligas principales de America
    goles.csv          # partidos finalizados + programados
alembic/               # migraciones (auth)
```
