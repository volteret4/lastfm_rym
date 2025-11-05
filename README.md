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
