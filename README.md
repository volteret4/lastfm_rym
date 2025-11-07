# 🎵 Last.fm Statistics Generator

Script Python que genera estadísticas HTML sobre coincidencias musicales entre varios usuarios de Last.fm. Perfecto para grupos de amigos que quieren ver qué música tienen en común.

## 📋 Características

- **Estadísticas periódicas automáticas:**
  - Semanales (generadas diariamente)
  - Mensuales (generadas el día 1 de cada mes)
  - Anuales (generadas el 1 de enero)

- **Tipos de coincidencias:**
  - Artistas
  - Canciones
  - Álbumes
  - Géneros (obtenidos de tags de Last.fm)
  - Sellos discográficos (opcional, usando Discogs)

- **Interfaz HTML interactiva:**
  - Destacar scrobbles de un usuario específico
  - Filtrar por período (semanal, mensual, anual)

## 🚀 Instalación

### 1. Requisitos previos

- Python 3.7 o superior
- Una cuenta en Last.fm
- API Key de Last.fm (gratuita)
- (Opcional) Token de Discogs para información de sellos

### 2. Clonar o descargar los archivos

```bash
# Crear directorio del proyecto
mkdir lastfm-stats
cd lastfm-stats

# Copiar los archivos
# - lastfm_stats.py
# - requirements.txt
# - .env.example
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configuración

#### Opción A: Variables de entorno del sistema

```bash
export LASTFM_API_KEY="tu_api_key"
export LASTFM_USERS="usuario1,usuario2,usuario3"
export DISCOGS_TOKEN="tu_token_discogs"  # Opcional
```

#### Opción B: Archivo .env (recomendado)

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar con tus datos
nano .env  # o tu editor preferido
```

Contenido del archivo `.env`:

```env
LASTFM_API_KEY=tu_api_key_aqui
LASTFM_USERS=usuario1,usuario2,usuario3
DISCOGS_TOKEN=tu_token_discogs  # Opcional, dejar vacío si no lo usas
```

### 5. Obtener API Keys

#### Last.fm API Key (OBLIGATORIO)

1. Ve a: https://www.last.fm/api/account/create
2. Rellena el formulario (puedes poner información básica)
3. Copia la "API Key" (no necesitas el "Shared secret")

#### Discogs Token (OPCIONAL)

Solo si quieres información de sellos discográficos:

1. Ve a: https://www.discogs.com/settings/developers
2. Genera un nuevo token personal
3. Copia el token

## 🔧 Uso

### Ejecución manual

```bash
python3 lastfm_stats.py
```

Esto generará un archivo `weekly.html` en el directorio `docs`.

## 🌐 Publicar en GitHub Pages

### 1. Crear repositorio en GitHub

```bash
git init
git add index.html
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/tu-usuario/lastfm-stats.git
git push -u origin main
```

### 2. Activar GitHub Pages

1. Ve a tu repositorio en GitHub
2. Ir a **Settings** > **Pages**
3. En "Source", selecciona la rama `main` y carpeta `/ (docs)`
4. Guarda los cambios

Tu sitio estará disponible en: `https://tu-usuario.github.io/lastfm-stats/`

### 3. Automatizar actualizaciones con GitHub Actions

Crea el archivo `.github/workflows/update-stats.yml`:

```yaml
name: Update Last.fm Stats

on:
  schedule:
    - cron: "0 3 * * *" # Diariamente a las 3 AM UTC
  workflow_dispatch: # Permitir ejecución manual

jobs:
  update-stats:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.10"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt

      - name: Generate statistics
        env:
          LASTFM_API_KEY: ${{ secrets.LASTFM_API_KEY }}
          LASTFM_USERS: ${{ secrets.LASTFM_USERS }}
          DISCOGS_TOKEN: ${{ secrets.DISCOGS_TOKEN }}
        run: |
          python3 lastfm_stats.py

      - name: Commit and push if changed
        run: |
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git config --global user.name "github-actions[bot]"
          git add index.html stats_data.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "Update statistics" && git push)
```

**Configurar secrets en GitHub:**

1. Ve a tu repositorio > **Settings** > **Secrets and variables** > **Actions**
2. Agrega los siguientes secrets:
   - `LASTFM_API_KEY`: Tu API key de Last.fm
   - `LASTFM_USERS`: Lista de usuarios separados por comas
   - `DISCOGS_TOKEN`: Tu token de Discogs (opcional)

## 📊 Funcionamiento

### Lógica de generación de estadísticas

- **Semanales:** Se generan cada vez que se ejecuta el script (datos de los últimos 7 días)
- **Mensuales:** Solo se generan el día 1 de cada mes (datos desde el día 1 hasta hoy)
- **Anuales:** Solo se generan el 1 de enero (datos de todo el año en curso)

### Persistencia de datos

El script guarda las estadísticas usando sqlite en `lastfm_stats.db` para:

- Mantener estadísticas mensuales entre ejecuciones diarias
- Mantener estadísticas anuales durante todo el año
- Evitar recalcular datos que no han cambiado

### Filtrado de coincidencias

Solo se muestran items (artistas, canciones, etc.) que han sido escuchados por **2 o más usuarios**.

## 🎨 Características del HTML

- **Selector de usuario:** Destaca las coincidencias de un usuario específico con un fondo dorado
- **Selector de período:** Filtra para ver solo estadísticas semanales, mensuales o anuales
- **Información detallada:** Muestra número de plays y qué usuarios escucharon cada item

## ⚙️ Opciones de configuración

### Variables de entorno

| Variable         | Obligatorio | Descripción                  |
| ---------------- | ----------- | ---------------------------- |
| `LASTFM_API_KEY` | ✅ Sí       | API Key de Last.fm           |
| `LASTFM_USERS`   | ✅ Sí       | Usuarios separados por comas |
| `DISCOGS_TOKEN`  | ❌ No       | Token de Discogs para sellos |

### Límites

- **Last.fm:** ~5 peticiones por segundo (el script usa delays de 0.2s)
- **Discogs:** ~60 peticiones por minuto (el script usa delays de 1s)

## 📝 Notas adicionales

- Los datos se cachean durante la ejecución para evitar llamadas repetidas a las APIs
- El HTML generado es completamente estático y no requiere backend
- Puedes personalizar los estilos editando el CSS en `lastfm_stats.py`

## 📄 Licencia

Este proyecto es de código abierto y está disponible para uso personal.

## 🙏 Agradecimientos

- Last.fm API para los datos de scrobbles
- Discogs API para información de sellos discográficos

# **USUARIOS**

## FAVORITOS

<!--
### 📈 Top 10 artistas por escuchas

- contando solo con los top 10 artistas con mas scrobbles de cada usuario, crear un grafico circular con las coincidencias del usuario seleccionado en el dropdown con el resto. al hacer click mostrará las 10 canciones mas escuchadas para ese artista, con una cuenta de escuchas para cada usuario.

### 🏠 Vuelve a casa

- contando solo con los top 10 artistas que aparezcan mas dias en el periodo seleccionado, crear un grafico circular con las coincidencias del usuario seleccionado en el dropdown con otros usuarios, cada porcion sera otro usuario y el tamaño de la porcion sera la cantidad de dias que aparece en el periodo seleccionado.

### 📚 Discografía completada

- contando solo con los top 10 de cada usuario con mayor numero de temas escuchados suyos, crea un grafico circular con las coincidencias del usuario seleccionado en el dropdown con el resto. al hacer click mostrará las artistas coincidentes y el numero de escuchas para cada artista

### 💫 Streaks

contando con el top 5 artistas con mas streaks (mas dias seguidos escuchando a dicho artista) de cada usurario, crear un grafico circular con las coincidencias del usuario seleccionado en el dropdown con el resto, cada porcion sera un usuario y el tamaño dependera de la suma de dias de los 5 artistas. al hacer click mostrará las artistas coincidentes y el numero de escuchas para cada artista-->

## FECHAS

- grafico barras, cada barra una decada divida por el numero de scrobbles de cada usuario para la misma en el periodo calculado por el script.

## SCROBBLES

grafico lineal de evolucion de usuarios en el tiempo de artistas nuevos (descubrimiento)
grafico lineal de evolucion de usuarios de artistas unicos en un año ( el variadito )
grafico lineal de evolucion en el tiempo de los scrobbles de cada usuario correspondiente a sus artistas mas escuchados, por ejemplo en 2005 una media de 19 scrobbles por artista (media de scrobbles por artista al año)
grafico lineal evolucion en el tiempo de scrobbles por usuario

# **MENSUAL Y ANUAL**

## destacar obsesiones individuales (scripts temporales)

- grafico lineal temporal, en el eje x el periodo que el script analiza, cada linea sera un artista NUEVO (no tiene scrobble antes) con mas scrobbles en el periodo. cada punto con un pop up por ej en abril descubriste artista 1, 2 y 3 y escuchaste 100, 200 y 300 scrobbles respectivamente en ese mes **(solo anual)**

#### obsesiones

- grafico circular cada porcion un usuario y el tamaño dependera del mayor numero de scrobbles de un mismo artista en un dia (mensual y anual)

#### top 10 artistas

- grafico circular para el usuario Selecccionado en el dropdwon, cada porcion uno de sus top 10 artistas mas escuchados en el periodo calculado por el script, y el tamaño dependera del numero de scrobbles para el artista en ese periodo (mensual y anual)

- grafico ciruclar de artistas con tracks nuevos, del top 10 artistas con mas scrobbles, por ej. The Beach Boys has añadido 10 temas nuevos, llevas 130 temas de ellos escuchados

#### ultimos descubrimientos (scripts temporales)

- 10 ultimos artistas nuevos para el periodo calculado por el script

#### one hit wonder (scripts temporales)

- grafico circular 10 artistas mas escuchados con solo un tema escuchado en el periodo calculado por el script

#### golden oldies

- grafico circular de artistas que llevas sin escuchar un porcentaje de tiempo de un tercio el valor del periodo calculado por el script, (si se calculan 9 años, 3 años) que tengan al menos 50 scrobbles. cada porcion sera mayor o menor segun el numero de scrobbles del artista.

#### escaladores

- grafico lineal temporal que muestre los 10 artistas que con al menos 50 scrobbles en un mes han subido mas rapido de rango en el periodo calculado por el script
- grafico lineal temporal que muestre los 10 artistas que con al menos 50 scrobbles en un mes han bajado mas rapido de rango en el periodo calculado por el script

#### streaks

- grafico lineal temporal que muestre la evolucion de top 10 artistas con mas streaks (mas scrobbles seguidos del mismo artista)

- grafico barras, cada barra una decada divida por el numero de scrobbles de cada usuario para la misma en el periodo calculado por el script.

grafico circular cada porcion un usuario y el tamaño depende del numero de scrobbles que tiene el dia de mas scrobbles tenga para el tiempo calculado por el script

#### coincidencias

- grafico circular cada porcion un usuario y el tamaño depende del numero de coincidencias en el top 10 artistas con mas scrobbles para el periodo calculado por el script
- grafico circular cada porcion un usuario y el tamaño depende del numero de coincidencias en el top 10 albumes con mas scrobbles para el periodo calculado por el script
- grafico circular cada porcion un usuario y el tamaño depende del numero de coincidencias en el top 10 canciones con mas scrobbles para el periodo calculado por el script

## SISTEMA DE PUNTOS PARA RECOMENDACIONES

A tener en cuenta:

- Coincidencia con otro usuario en one hit wonder
- Coincidencia con otro usuario en golden oldies
- Coincidencia con otro usuario en escaladores
- Coincidencia con otro usuario en artistas con mas streaks
- Coincidencia con otro usuario en descubrimientos obsesivos
- Coincidencia con otro usuario en artistas que no desaparecen

en la nueva seccion yomimeconmigo:
en top artistas con una cancion el pop up y el tooltip deben mostrar el nombre del artista y la cancion
en top sellos y artistas los pop up y el tooltip deben mostrar los artistas que mas scrobbles aportan a dicho genero o sello en ese periodo de tiempo.
en "Top 10 Artistas con Más Días Consecutivos" el pop up debe mosrar el numero de dias, al igual que el eje Y debe ser el numero de dias, no de scrobbles
en "Top 10 Artistas con Más Canciones Únicas" el pop up debe mostrar el numero de canciones añadidas en ese periodo, y los 10 albums con mas scrobbles para ese periodo. El eje Y debe ser el numero de canciones únicas, no de scrobbles
en "Top 10 Artistas que Más Rápido Subieron" el pop up debe mostrar el top 10 canciones mas escuchadas en ese periodo
"Top 10 Artistas que Más Rápido Bajaron" es identico al anterior, esto debe ser un error de calculo.

en "EVOLUCION"
en todos los graficos deberia mostrar en el pop up las coincidencias con cada usuario (las discos que ayudan a establecer ese valor, no el numero de scrobbles del elemento). Por ejemplo si en "Coincidencias en Géneros por Año" el user1 tiene 10 coincidencias con el user2 no quiero ver los scrobbles para el año para ese genero, sino cuales son esas coincidencias, que canciones, albumes o artistas son esas (si es posible los 3 datos, mejor) en las que coincido con ese usuario, limitado a 10 (eligiendo las mas escuchadas)

Antes de crear los graficos has añadido una info que solo cambia el numero de scrobbles entre usuarios, el resto lo muestra LASTFM_API_KEY
251.390
Scrobbles
7
Usuarios (Artistas)
7
Usuarios (Álbumes)
8
Géneros
7
Décadas
7
