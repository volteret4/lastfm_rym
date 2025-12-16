# 🎵 Last.fm Statistics Generator

Script Python que genera estadísticas HTML sobre coincidencias musicales entre varios usuarios de Last.fm.

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
LASTFM_USERS_ICONS='user1:🎹,user2:🎧,user3:🎸'
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
