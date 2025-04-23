# KronzBet NBA Dashboard

Una aplicación web full-stack que muestra información de partidos de la NBA, incluyendo resultados diarios, box scores detallados, marcadores en vivo y predicciones de partidos utilizando un modelo de Machine Learning. Diseñada como un proyecto de portafolio para demostrar habilidades en desarrollo web moderno.

# Link Frontend

- GitHub: [Frontend](https://github.com/SamuelCam14/kronz_bet_client)

## Tabla de Contenidos

- [Descripción](#descripción)
- [Características Principales](#características-principales)
- [Screenshots](#screenshots)
- [Stack Tecnológico](#stack-tecnológico)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Instalación y Ejecución Local](#instalación-y-ejecución-local)
  - [Prerrequisitos](#prerrequisitos)
  - [Backend (FastAPI)](#backend-fastapi)
  - [Frontend (React)](#frontend-react)
- [Endpoints de la API](#endpoints-de-la-api)
- [Despliegue](#despliegue)
- [Posibles Mejoras](#posibles-mejoras)
- [Autor](#autor)

## Descripción

KronzBet NBA Dashboard es una aplicación web interactiva que permite a los aficionados de la NBA consultar información actualizada sobre los partidos. Los usuarios pueden navegar por fechas para ver resultados pasados, acceder a estadísticas detalladas (box scores) de cada partido y consultar las probabilidades de victoria para futuros encuentros, calculadas mediante un modelo de Regresión Logística entrenado con datos históricos.

Este proyecto integra una API externa (`nba_api`) para obtener datos en tiempo real (o casi real), aplica transformaciones a esos datos, utiliza un modelo de Machine Learning pre-entrenado para las predicciones y presenta la información en una interfaz de usuario limpia y responsiva construida con React y Tailwind CSS.

## Características Principales

- 🏀 **Resultados Diarios:** Visualiza los marcadores y horarios de todos los partidos para una fecha seleccionada, obtenidos mediante `scoreboardv2`.
- 📊 **Box Scores Detallados:** Accede a las estadísticas completas por jugador y equipo para un partido específico, usando el endpoint `boxscoretraditionalv3` y transformando los datos para una fácil visualización.
- 🤖 **Predicciones de Partidos:** Muestra la probabilidad de victoria estimada para cada equipo en los partidos programados, utilizando un modelo de Regresión Logística (`sklearn`/`joblib`) alimentado con estadísticas actuales del equipo (`leaguestandingsv3`, `leaguedashteamstats`).
- 🔴 **Marcadores en Vivo:** Muestra el estado actual (periodo, reloj, marcador) de los partidos en curso usando el endpoint de scoreboard en vivo de `nba_api`. `<!-- Confirma si esta característica está visible/funcional en el frontend -->`
- 📅 **Selector de Fecha:** Permite al usuario seleccionar fácilmente una fecha para consultar los partidos correspondientes.
- 🎨 **Diseño MobileFirst:** Interfaz construida con React y Tailwind CSS, diseñada para funcionar en pantallas móviles.
- ⚙️ **Backend Eficiente:** API construida con FastAPI, aprovechando la programación asíncrona para manejar las llamadas a la API externa.

## Stack Tecnológico

**Backend:**

- **Lenguaje:** Python 3.x
- **Framework:** FastAPI
- **Servidor ASGI:** Uvicorn
- **Gestor de Procesos (Prod):** Gunicorn
- **API Externa:** `nba_api` (usando `scoreboardv2`, `boxscoretraditionalv3`, `scoreboard` (live), `leaguestandingsv3`, `leaguedashteamstats`)
- **Machine Learning:** Scikit-learn (`sklearn`), Joblib (para cargar modelo/scaler), Pandas (para manipulación de datos de ML)
- **Manejo de Fechas/Horas:** Pytz
- **Variables de Entorno:** `python-dotenv` (para desarrollo local)

**Frontend:**

- **Librería:** React (con Vite) `<!-- Confirma si es Vite -->`
- **Lenguaje:** JavaScript `<!-- O TypeScript? -->`
- **Estilos:** Tailwind CSS
- **Llamadas API:** Fetch API `<!-- O Axios? -->`
- **Gestión de Estado:** `<!-- ¿Context API, useState local, Redux, Zustand? Menciona si usaste algo específico -->`

**Despliegue:**

- **Backend:** Render (Web Service - Python, Free Tier)
- **Frontend:** Netlify (Static Site Hosting, Free Tier)

## Instalación y Ejecución Local

Sigue estos pasos para configurar y ejecutar el proyecto en tu máquina local.

### Prerrequisitos

- [Python](https://www.python.org/downloads/) (Versión 3.8+ recomendada)
- [Node.js](https://nodejs.org/) y [npm](https://www.npmjs.com/) (o [Yarn](https://yarnpkg.com/))
- [Git](https://git-scm.com/)

### Backend (FastAPI)

1.  **Clona el repositorio:**

    ```bash
    git clone https://github.com/SamuelCam14/kronz_bet_server.git
    cd kronz_bet_server/
    ```

2.  **Crea y activa un entorno virtual:**

    ```bash
    python -m venv .venv
    # Linux/macOS:
    source .venv/bin/activate
    # Windows (cmd):
    # .venv\Scripts\activate.bat
    # Windows (PowerShell):
    # .venv\Scripts\Activate.ps1
    ```

3.  **Instala las dependencias:**

    ```bash
    pip install -r requirements.txt
    ```

    _(Nota: Asegúrate de tener las herramientas de compilación necesarias si alguna dependencia como Pandas necesita compilar algo)._

4.  **Modelo y Scaler:** Asegúrate de que los archivos `logistic_regression_model.joblib` y `scaler.joblib` estén presentes en la carpeta `server_py/models/win_probability/`. (Deberían estar incluidos si clonaste el repo correctamente).

5.  **Ejecuta el servidor de desarrollo:**
    ```bash
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    ```
    - El backend estará disponible en `http://localhost:8000`.
    - La documentación interactiva de la API (Swagger UI) estará en `http://localhost:8000/docs`.

### Frontend (React)

1.  **Navega a la carpeta del frontend (desde la raíz del repo):**

    ```bash
    cd ../client
    ```

2.  **Instala las dependencias:**

    ```bash
    npm install
    # o: yarn install
    ```

3.  **Configura las Variables de Entorno:**

    - Crea un archivo `.env` en la raíz de la carpeta `client/`.
    - Añade la URL de tu backend local:
      ```dotenv
      # client/.env
      VITE_API_URL=http://localhost:8000/api
      ```
    - Asegúrate de que `.env` esté en el `.gitignore` del frontend.

4.  **Ejecuta la aplicación de desarrollo:**
    ```bash
    npm run dev
    # o: yarn dev
    ```
    - La aplicación frontend estará disponible en `http://localhost:5173` (o el puerto que Vite/tu configuración indique).

## Endpoints de la API

El backend FastAPI expone los siguientes endpoints principales bajo el prefijo `/api`:

- **`GET /games?date={YYYY-MM-DD}`**:
  - Obtiene la lista de partidos programados/finalizados para una fecha específica.
  - Usa `scoreboardv2`.
- **`GET /games/{game_id}?date={YYYY-MM-DD}`**:
  - Obtiene los detalles de un partido específico (`game_id` de 10 dígitos).
  - _Requiere también el parámetro `date`_ para buscar eficientemente en los datos del scoreboard de ese día.
- **`GET /boxscores/{game_id}`**:
  - Obtiene el box score detallado y transformado para un `game_id` específico.
  - Usa `boxscoretraditionalv3` y la función `transform_boxscore_data`.
- **`GET /live_scores`**:
  - Obtiene datos simplificados del estado actual (marcador, periodo, reloj) de los partidos en curso.
  - Usa `nba_api.live.nba.endpoints.scoreboard`.
- **`GET /predictions/win_probability?home_team_id={id}&visitor_team_id={id}`**:
  - Calcula y devuelve la probabilidad de victoria estimada para el equipo local y visitante.
  - Requiere los IDs numéricos de los equipos (`home_team_id`, `visitor_team_id`).
  - Obtiene estadísticas actuales de los equipos (`leaguestandingsv3`, `leaguedashteamstats`), calcula features y usa el modelo de Regresión Logística cargado.

Consulta la documentación interactiva de Swagger UI (ejecutando el backend localmente) en `http://localhost:8000/docs` para ver los esquemas de respuesta detallados.

## Despliegue

- **Frontend:** Desplegado en **Netlify** desde la rama `main`. Netlify maneja el build (ej: `npm run build`) y el despliegue de los archivos estáticos generados. La variable de entorno `VITE_API_URL` se configura en Netlify apuntando a la URL del backend en Render.
- **Backend:** Desplegado en **Render** como un Web Service Python desde la rama `main`. Render instala las dependencias de `requirements.txt` y ejecuta el servidor usando Gunicorn y Uvicorn con el comando: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT -t 120`.

## Posibles Mejoras

- **Caching:** Implementar caché (ej: con Redis o en memoria con TTL) para las llamadas a `nba_api` (standings, stats, scoreboard) para reducir la carga y mejorar la velocidad, respetando los límites de la API externa.
- **Modelo de Predicción:**
  - Re-entrenar el modelo con más datos o features más complejos.
  - Experimentar con otros algoritmos (Gradient Boosting, Redes Neuronales).
  - Evaluar el rendimiento del modelo de forma más rigurosa.
- **Interfaz de Usuario:**
  - Mejorar la visualización de datos (gráficos para box scores).
  - Añadir animaciones o transiciones suaves.
  - Implementar un tema claro/oscuro.
- **Gestión de Errores:** Mejorar el manejo y la presentación de errores al usuario en el frontend cuando la API falla.
- **Testing:** Añadir tests unitarios (ej: para `data_transformer`, `parse_nba_datetime_to_utc`, `calculate_prediction_features`) y tests de integración para los endpoints de la API.

## Autor

**[Samuel Camargo]**

- GitHub: [@SamuelCam14](https://github.com/SamuelCam14)
- LinkedIn: (https://linkedin.com/in/samuel-camargo-dev)
- Portfolio: (https://personal-portfolio-amber-zeta.vercel.app/)
