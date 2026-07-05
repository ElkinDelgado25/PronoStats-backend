# PronoStats-backend

API REST de **PronoStats**: pronosticos deportivos basados en estadisticas historicas.
Construida con **FastAPI + SQLAlchemy + PostgreSQL** (en la nube via Supabase, abstraida por `DATABASE_URL`).

## Requisitos

- Python 3.10+

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

## Base de datos (BDD_CLOUD)

En `.env`, define `DATABASE_URL` con la cadena de conexion de Supabase u otro Postgres:

```
DATABASE_URL=postgresql+psycopg2://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

Si dejas el valor `BDD_CLOUD` (o vacio), la app usa automaticamente una BD **SQLite local**
(`pronostats_dev.db`) para desarrollo, sin cambiar el contrato de la API.

## Ejecutar

```bash
# Cargar datos de ejemplo (opcional, recomendado para probar)
python -m app.seed

# Levantar el servidor
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentacion interactiva (Swagger): http://localhost:8000/docs

Usuarios de ejemplo (tras `python -m app.seed`):

- Admin: `admin@pronostats.com` / `admin123`
- Usuario: `usuario@pronostats.com` / `usuario123`

## Migraciones (produccion)

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

En desarrollo, las tablas se crean automaticamente al iniciar la app.

## Contrato de la API (resumen)

| Metodo | Ruta | Descripcion | HU |
| --- | --- | --- | --- |
| POST | `/auth/register` | Registro | HU-01 |
| POST | `/auth/login` | Inicio de sesion | HU-02 |
| POST | `/auth/forgot-password` | Recuperar contrasena | HU-03 |
| GET | `/leagues` | Listar ligas | HU-04 |
| GET | `/matches` | Catalogo de partidos (filtros liga/fecha/estado) | HU-04, HU-05 |
| GET | `/matches/{id}` | Detalle de partido | HU-04 |
| GET | `/matches/{id}/h2h` | Historial entre equipos | HU-06 |
| GET | `/matches/{id}/prediction` | Pronostico 1X2 + factores + confianza | HU-07, HU-08, HU-09 |
| GET | `/teams` | Listar equipos | - |
| GET | `/teams/{id}/stats` | Estadisticas historicas de un equipo | HU-12 |
| GET | `/favorites` | Listar favoritos | HU-13 |
| POST | `/favorites` | Agregar favorito | HU-13 |
| DELETE | `/favorites/{equipo_id}` | Eliminar favorito | HU-13 |
| GET | `/stats/model-performance` | Aciertos vs fallos del modelo | Panel metricas |
| POST/PUT/DELETE | `/admin/leagues` | CRUD ligas (admin) | HU-15 |
| POST/PUT/DELETE | `/admin/teams` | CRUD equipos (admin) | HU-16 |
| POST/PUT/DELETE | `/admin/matches` | CRUD partidos (admin) | HU-16 |
| PUT | `/admin/matches/{id}/result` | Cargar resultado y evaluar prediccion | HU-16 |
| GET | `/admin/usage-stats` | Estadisticas de uso (admin) | HU-17 |

## Estructura

```
app/
  main.py              # App FastAPI + routers + CORS
  core/                # config (settings, DATABASE_URL) y seguridad (JWT)
  db/                  # engine, session, Base
  models/              # SQLAlchemy: usuario, liga, equipo, partido, resultado, prediccion, favorito
  schemas/             # Pydantic (contrato de la API)
  api/                 # routers: auth, leagues, teams, matches, predictions, favorites, stats, admin
  services/            # prediction_engine, evaluation, team_stats
  seed.py              # datos de ejemplo
alembic/               # migraciones
```
