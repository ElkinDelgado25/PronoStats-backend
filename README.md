# PronoStats-backend

API REST de **PronoStats**: pronosticos deportivos basados en estadisticas historicas.
Construida con **FastAPI + SQLAlchemy**. Los datos de negocio (ligas, equipos y
partidos) provienen de **datasets CSV** que se leen en memoria en cada arranque;
la base de datos se usa para autenticacion, boletos, combinadas y cartera.

Repositorio: https://github.com/ElkinDelgado25/PronoStats-backend.git

Frontend companion: https://github.com/ElkinDelgado25/PronoStats-Frontend.git

---

## Requisitos

| Herramienta | Version | Para que sirve | Como comprobarlo |
| --- | --- | --- | --- |
| **Python** | 3.10+ (probado con 3.13) | Ejecutar la API | `python --version` o `python3 --version` |
| **pip** | viene con Python | Instalar paquetes | `pip --version` |
| **Git** | cualquiera | Clonar el repo | `git --version` |
| **Docker** | opcional | Solo si usas Postgres local | `docker --version` |

En Windows, al instalar Python marca **Add python.exe to PATH**.

---

## Instalacion paso a paso

Sigue los pasos **en orden**. Cada comando incluye **para que sirve**.

### Paso 0 — Clonar el repositorio

```powershell
git clone https://github.com/ElkinDelgado25/PronoStats-backend.git
cd PronoStats-backend
```

| Comando | Por que se usa |
| --- | --- |
| `git clone ...` | Descarga el codigo fuente del backend a tu PC |
| `cd PronoStats-backend` | Entra a la carpeta del proyecto; los siguientes comandos deben ejecutarse ahi |

Si ya tienes el monorepo local, solo haz `cd PronoStats-backend` (omite el clone).

---

### Paso 1 — Crear un entorno virtual

Un entorno virtual (`.venv`) aisla las librerias de este proyecto para no mezclarlas con otros Python del sistema.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

| Comando | Por que se usa |
| --- | --- |
| `python -m venv .venv` | Crea la carpeta `.venv` con un Python aislado para PronoStats |
| `.venv\Scripts\activate` (Windows) | Activa ese entorno en la terminal actual (veras `(.venv)` al inicio) |
| `source .venv/bin/activate` (Linux/macOS) | Igual que arriba, en shells Unix |

Si en Windows `python` no existe, prueba:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
```

Si PowerShell bloquea `Activate.ps1`:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Luego vuelve a ejecutar `.venv\Scripts\activate`.

> **Importante:** cada vez que abras una terminal nueva para trabajar en el backend, vuelve a activar el entorno con `activate`.

---

### Paso 2 — Instalar dependencias de Python

```powershell
pip install -r requirements.txt
```

| Comando | Por que se usa |
| --- | --- |
| `pip install -r requirements.txt` | Lee la lista de paquetes (FastAPI, Uvicorn, SQLAlchemy, PyJWT, Stripe, etc.) e instala versiones fijadas dentro de `.venv` |

Sin este paso, `uvicorn` y los imports de `app/` fallaran.

---

### Paso 3 — Crear el archivo `.env`

```powershell
copy .env.example .env
```

**Linux / macOS:**

```bash
cp .env.example .env
```

| Comando | Por que se usa |
| --- | --- |
| `copy` / `cp .env.example .env` | Copia la plantilla de variables. `.env` no se sube a Git (secretos locales) |

Abre `.env` con un editor y **define al menos** `JWT_SECRET` (minimo 32 caracteres).

Generar un secreto aleatorio:

**PowerShell:**

```powershell
[guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
```

**Linux / macOS:**

```bash
openssl rand -hex 32
```

Pega el resultado en `.env`:

```env
JWT_SECRET=pega_aqui_tu_clave_generada
DATABASE_URL=BDD_CLOUD
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ENVIRONMENT=development
```

| Variable | Por que importa |
| --- | --- |
| `JWT_SECRET` | Firma las cookies de sesion. **Obligatorio**; sin el la API no arranca |
| `DATABASE_URL=BDD_CLOUD` | Valor centinela: la app usa SQLite local (`pronostats_dev.db`). Ideal para empezar sin Postgres |
| `CORS_ORIGINS` | Permite que el frontend (Vite en `:5173`) llame a la API con cookies |
| `ENVIRONMENT` | `development` desactiva reglas estrictas de produccion (cookies secure, etc.) |

Stripe (`STRIPE_SECRET_KEY`, etc.) es **opcional**: solo hace falta si pruebas depositos con tarjeta. El resto de la app funciona sin Stripe.

Las tablas de la BD se crean **automaticamente** al iniciar el servidor.

---

### Paso 4 — Crear usuarios de prueba

```powershell
python -m app.seed
```

| Comando | Por que se usa |
| --- | --- |
| `python -m app.seed` | Ejecuta el modulo `app/seed.py` como script: crea (o actualiza) usuarios demo en la BD |

| Rol | Email | Contrasena |
| --- | --- | --- |
| Admin | `admin@pronostats.com` | `admin123` |
| Usuario | `usuario@pronostats.com` | `usuario123` |

Debes tener el entorno virtual **activado** y el `.env` ya configurado antes de este paso.

---

### Paso 5 — (Opcional) Regenerar datasets CSV

Los CSV de futbol ya vienen en `data/dataset_futbol/`. Solo regenera si quieres datos nuevos:

```powershell
python -m app.generate_dataset
```

| Comando | Por que se usa |
| --- | --- |
| `python -m app.generate_dataset` | Sobrescribe `equipos.csv` y `goles.csv` con un generador determinista (Poisson). No toca la BD |

Tras regenerar, **reinicia** el backend para que vuelva a leer los CSV.

---

### Paso 6 — Arrancar el servidor

```powershell
uvicorn app.main:app --reload
```

| Parte del comando | Por que se usa |
| --- | --- |
| `uvicorn` | Servidor ASGI que ejecuta aplicaciones FastAPI |
| `app.main:app` | Modulo `app/main.py`, objeto `app` (la aplicacion FastAPI) |
| `--reload` | Reinicia solo al detectar cambios en el codigo (desarrollo) |

Deja esta terminal abierta. Deberias ver algo como `Uvicorn running on http://127.0.0.1:8000`.

- API: http://localhost:8000
- Documentacion interactiva (Swagger): http://localhost:8000/docs

Luego clona/instala el [frontend](https://github.com/ElkinDelgado25/PronoStats-Frontend) y arrancalo en otra terminal.

Para detener el servidor: `Ctrl + C`.

---

## Resumen rapido (copiar y pegar)

### Windows (PowerShell)

```powershell
git clone https://github.com/ElkinDelgado25/PronoStats-backend.git
cd PronoStats-backend

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
# Edita .env y pega JWT_SECRET (min. 32 caracteres)

python -m app.seed
uvicorn app.main:app --reload
```

### Linux / macOS

```bash
git clone https://github.com/ElkinDelgado25/PronoStats-backend.git
cd PronoStats-backend

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edita .env y pega JWT_SECRET (openssl rand -hex 32)

python -m app.seed
uvicorn app.main:app --reload
```

---

## PostgreSQL opcional (Docker)

Por defecto usas SQLite. Si prefieres Postgres local:

1. En `.env` define una contraseña, por ejemplo:

```env
POSTGRES_PASSWORD=pronostats123
```

2. Levanta el contenedor:

```powershell
docker compose up -d
```

| Comando | Por que se usa |
| --- | --- |
| `docker compose up -d` | Crea y arranca Postgres 16 en segundo plano (`-d`). Puerto host: **15432** |

3. Apunta la app a ese Postgres en `.env`:

```env
DATABASE_URL=postgresql+psycopg://pronostats:pronostats123@127.0.0.1:15432/backend_pronoticos
```

(Usa la misma contraseña que `POSTGRES_PASSWORD`.)

4. Reinicia Uvicorn y vuelve a sembrar usuarios:

```powershell
python -m app.seed
```

Para parar Postgres: `docker compose down` (los datos del volumen se conservan salvo que uses `-v`).

---

## Solucion de problemas

| Problema | Solucion |
| --- | --- |
| Error al arrancar por JWT | Define `JWT_SECRET` en `.env` (min. 32 caracteres, no vacio ni placeholder) |
| `ModuleNotFoundError` | Activa `.venv` y vuelve a `pip install -r requirements.txt` |
| Frontend no conecta / CORS | Revisa que `CORS_ORIGINS` incluye `http://localhost:5173` |
| Sin partidos en la API | Verifica `data/dataset_futbol/*.csv` o ejecuta `python -m app.generate_dataset` y reinicia |
| Login falla | Ejecuta `python -m app.seed` con el mismo `DATABASE_URL` que usa el servidor |
| Puerto 8000 ocupado | `uvicorn app.main:app --reload --port 8001` y actualiza `VITE_API_URL` en el frontend |
| Docker: falta `POSTGRES_PASSWORD` | Definelo en `.env` antes de `docker compose up -d` |

---

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

## Base de datos (solo autenticacion y cartera)

La BD (SQLAlchemy) se usa para usuarios/auth, boletos, combinadas y cartera.
Configura `DATABASE_URL` en `.env`; si conserva el valor `BDD_CLOUD` (o vacio),
se usa SQLite local (`pronostats_dev.db`). Las tablas se crean automaticamente al iniciar.

## Seguridad de despliegue

- `JWT_SECRET` es obligatorio y no debe reutilizarse entre ambientes.
- En produccion usa `ENVIRONMENT=production`, `JWT_COOKIE_SECURE=true` y origenes
  explicitos en `CORS_ORIGINS`.
- `CORS_ORIGINS` no acepta `*` porque la app usa cookies HttpOnly.
- `POSTGRES_PASSWORD` debe definirse en `.env` antes de levantar
  `docker-compose.yml`.
- El endpoint `/auth/forgot-password` responde de forma generica y no devuelve
  tokens de recuperacion en el cuerpo HTTP.

## Contrato de la API (resumen)

Datos deportivos servidos desde el proveedor CSV:

| Metodo | Ruta | Descripcion | HU |
| --- | --- | --- | --- |
| GET | `/leagues` | Listar ligas | HU-04 |
| GET | `/countries` | Listar paises disponibles | HU-04 |
| GET | `/matches` | Catalogo de partidos (filtros liga/fecha/estado) | HU-04, HU-05 |
| GET | `/predictions` | Catalogo publico de pronosticos 1X2 | HU-07 |
| GET | `/matches/{id}` | Detalle de partido | HU-04 |
| GET | `/matches/{id}/h2h` | Historial entre equipos | HU-06 |
| GET | `/matches/{id}/prediction` | Pronostico 1X2 + factores + confianza | HU-07, HU-08, HU-09 |
| GET | `/teams` | Listar equipos | - |
| GET | `/teams/{id}/stats` | Estadisticas historicas de un equipo | HU-12 |
| GET | `/teams/compare` | Comparar dos equipos por estadisticas e historial directo | HU-11 |
| GET | `/stats/model-performance` | Aciertos vs fallos (porcentaje de acierto) | Panel metricas |
| GET | `/statistics` | Metricas publicas del modelo para el dashboard | Panel metricas |

Autenticacion y administracion (base de datos):

| Metodo | Ruta | Descripcion | HU |
| --- | --- | --- | --- |
| POST | `/auth/register` | Registro | HU-01 |
| POST | `/auth/login` | Inicio de sesion | HU-02 |
| POST | `/auth/forgot-password` | Recuperar contrasena | HU-03 |
| GET | `/favorites` `POST` `DELETE` | Favoritos del usuario | HU-13 |
| GET/POST/DELETE | `/analysis-history` | Historial de analisis consultados | HU-14 |
| POST/PUT/DELETE | `/admin/...` | CRUD administrativo (BD) | HU-15, HU-16, HU-17 |
| POST | `/wallet/recharge` | Recarga validada ($5-$500): `stripe`, `transfer` o `mock` en desarrollo | Cartera |
| GET | `/wallet/balance` | Saldo actual de la cartera autenticada | Cartera |
| GET | `/wallet/transactions` | Movimientos recientes de la cartera autenticada | Cartera |

> Nota: los endpoints de datos deportivos leen del CSV; los de `/admin` operan
> sobre la BD y son independientes del dataset CSV.

## Estructura

```
app/
  main.py              # App FastAPI + routers + CORS + carga CSV en lifespan
  csv_store.py         # Proveedor de datos CSV en memoria (ligas/equipos/partidos/predicciones/metricas)
  generate_dataset.py  # Generador determinista de los CSV
  seed.py              # Usuarios y datos de ejemplo en BD
  core/                # config (settings) y seguridad (JWT)
  db/                  # engine, session, Base
  models/              # SQLAlchemy: usuario, liga, equipo, partido, resultado, prediccion, favorito, boleto, cartera
  schemas/             # Pydantic (contrato de la API)
  api/                 # routers: auth, leagues, teams, matches, predictions, favorites, stats, admin, boletos, ...
  services/            # prediction_engine, evaluation, team_stats, combinadas, wallet, stripe
data/
  dataset_futbol/
    equipos.csv        # equipos de las ligas principales de America
    goles.csv          # partidos finalizados + programados
alembic/               # migraciones
docker-compose.yml     # Postgres opcional
.env.example           # Plantilla de variables de entorno
requirements.txt       # Dependencias Python
```
