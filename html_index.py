#!/usr/bin/env python3
"""
Generate Index
Genera el index.html dinámicamente basándose en los archivos HTML en docs/
"""

import os
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict


import unicodedata

def scan_html_files(docs_dir='docs'):
    """Escanea la carpeta docs/ en busca de archivos HTML de estadísticas.
    Normaliza nombres (unicode, espacios, mayúsculas) y hace debug explícito.
    """
    files = {
        'weekly': [],
        'monthly': [],
        'yearly': [],
        'users': [],
        'grupo': []
    }

    if not os.path.exists(docs_dir):
        print(f"⚠️  La carpeta '{docs_dir}' no existe")
        return files

    # Mapa de los nombres exactos esperados (normalizados a lower + NFC)
    weekly_map = {
        "esta-semana.html": "Esta semana",
        "semana-pasada.html": "Semana pasada",
        "hace-dos-semanas.html": "Hace dos semanas",
    "hace-tres-semanas.html": "Hace tres semanas"
    }
    # normalizar las claves por si acaso
    weekly_map_norm = {unicodedata.normalize('NFC', k).strip().lower(): v for k, v in weekly_map.items()}

    found_files = os.listdir(docs_dir)
    print(f"DEBUG: archivos en {docs_dir} -> {len(found_files)} entradas")
    for fn in found_files:
        print(f"  - '{fn}'")

    for filename in found_files:
        # ignorar index y no-html
        if not filename.lower().endswith('.html') or filename.lower() == 'index.html':
            continue

        # ignorar si es directorio (por si hay subcarpetas)
        path = os.path.join(docs_dir, filename)
        if os.path.isdir(path):
            print(f"DEBUG: saltando directorio {filename}")
            continue

        # normalizar nombre de archivo para comparación
        fn_norm = unicodedata.normalize('NFC', filename).strip().lower()

        # Semanales con nombres fijos
        if fn_norm in weekly_map_norm:
            label = weekly_map_norm[fn_norm]
            files['weekly'].append({
                'filename': filename,
                'label': label,
                'date': datetime.now()
            })
            print(f"DEBUG: detectado semanal -> {filename} como '{label}'")
            continue

        # Mensuales: monthly_name_YYYY.html
        if fn_norm.startswith('monthly'):
            match = re.match(r'monthly_([a-z]+)_(\d{4})\.html', fn_norm)
            if match:
                month_name = match.group(1).capitalize()
                year = match.group(2)
                label = f"{month_name} {year}"
                months = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month_num = months.get(match.group(1).lower(), 1)
                date_obj = datetime(int(year), month_num, 1)
                files['monthly'].append({
                    'filename': filename,
                    'label': label,
                    'date': date_obj,
                    'year': year,
                    'month': month_name
                })
                print(f"DEBUG: detectado mensual -> {filename} como '{label}'")
            continue

        # Anuales
        if fn_norm.startswith('yearly'):
            match = re.match(r'yearly_(\d{4})\.html', fn_norm)
            if match:
                year = match.group(1)
                label = f"Año {year}"
                date_obj = datetime(int(year), 1, 1)
                files['yearly'].append({
                    'filename': filename,
                    'label': label,
                    'date': date_obj
                })
                print(f"DEBUG: detectado anual -> {filename} como '{label}'")
            continue

        # Usuarios
        if fn_norm.startswith('usuarios'):
            match = re.match(r'usuarios(?:_(\d{4})-(\d{4}))?\.html', fn_norm)
            if match:
                if match.group(1) and match.group(2):
                    from_year = match.group(1)
                    to_year = match.group(2)
                    label = f"Usuarios {from_year}-{to_year}"
                    date_obj = datetime(int(to_year), 12, 31)
                else:
                    label = "Estadísticas de Usuarios"
                    date_obj = datetime.now()
                files['users'].append({
                    'filename': filename,
                    'label': label,
                    'date': date_obj
                })
                print(f"DEBUG: detectado usuarios -> {filename} como '{label}'")
            continue

        # Grupo
        if fn_norm.startswith('grupo'):
            match = re.match(r'grupo(?:_(\d{4})-(\d{4}))?\.html', fn_norm)
            if match:
                if match.group(1) and match.group(2):
                    from_year = match.group(1)
                    to_year = match.group(2)
                    label = f"Grupo {from_year}-{to_year}"
                    date_obj = datetime(int(to_year), 12, 31)
                else:
                    label = "Estadísticas Grupales"
                    date_obj = datetime.now()
                files['grupo'].append({
                    'filename': filename,
                    'label': label,
                    'date': date_obj
                })
                print(f"DEBUG: detectado grupo -> {filename} como '{label}'")
            continue

        # Si llega aquí es un html que no encaja en patrones conocidos
        print(f"DEBUG: archivo HTML no categorizado -> {filename}")

    # Asegurar orden fijo si existen los cuatro semanales
    order = ["esta-semana.html", "semana-pasada.html", "hace-dos-semanas.html", "hace-tres-semanas.html"]
    files['weekly'].sort(key=lambda x: order.index(unicodedata.normalize('NFC', x['filename']).strip().lower()) if unicodedata.normalize('NFC', x['filename']).strip().lower() in order else 99)

    # Ordenar otras categorías por fecha (más reciente primero)
    for category in ['monthly', 'yearly', 'users', 'grupo']:
        files[category].sort(key=lambda x: x['date'], reverse=True)

    print(f"DEBUG: semanales detectadas -> {[f['filename'] for f in files['weekly']]}")
    return files




def group_monthly_by_year(monthly_files):
    """Agrupa los archivos mensuales por año"""
    years = defaultdict(list)
    for file_info in monthly_files:
        if 'year' in file_info:
            years[file_info['year']].append(file_info)

    # Ordenar meses dentro de cada año
    for year in years:
        years[year].sort(key=lambda x: x['date'], reverse=True)

    return dict(years)


def generate_index_html(files):
    """Genera el contenido del index.html"""

    # Agrupar archivos mensuales por año
    monthly_by_year = group_monthly_by_year(files['monthly'])
    available_years = sorted(monthly_by_year.keys(), reverse=True)

    html = """<!doctype html>
<html lang="es">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>RYM Hispano Estadísticas</title>
        <link rel="icon" type="image/png" href="images/music.png">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family:
                    -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                    sans-serif;
                background: #1e1e2e;
                color: #cdd6f4;
                line-height: 1.6;
            }

            .container {
                max-width: 1200px;
                margin: 0 auto;
            }

            header {
                background: #181825;
                padding: 30px 20px;
                text-align: center;
                border-bottom: 3px solid #cba6f7;
            }

            h1 {
                font-size: 2.5em;
                color: #cba6f7;
                margin-bottom: 10px;
            }

            .subtitle {
                color: #a6adc8;
                font-size: 1.1em;
            }

            nav {
                background: #181825;
                padding: 0;
                border-bottom: 1px solid #313244;
            }

            .nav-tabs {
                display: flex;
                list-style: none;
                max-width: 1200px;
                margin: 0 auto;
            }

            .nav-tabs li {
                flex: 1;
            }

            .nav-tabs a {
                display: block;
                padding: 20px;
                text-align: center;
                color: #a6adc8;
                text-decoration: none;
                border-bottom: 3px solid transparent;
                transition: all 0.3s;
                font-weight: 600;
            }

            .nav-tabs a:hover {
                background: #1e1e2e;
                color: #cba6f7;
            }

            .nav-tabs a.active {
                color: #cba6f7;
                border-bottom-color: #cba6f7;
                background: #1e1e2e;
            }

            .content {
                padding: 40px 20px;
            }

            .tab-content {
                display: none;
            }

            .tab-content.active {
                display: block;
                animation: fadeIn 0.3s;
            }

            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }

            .period-selector {
                background: #181825;
                padding: 25px;
                border-radius: 12px;
                margin-bottom: 30px;
                border: 1px solid #313244;
            }

            .period-selector h2 {
                color: #cba6f7;
                margin-bottom: 20px;
                font-size: 1.5em;
            }

            .period-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 15px;
            }

            .period-link {
                display: block;
                padding: 20px;
                background: #1e1e2e;
                border: 2px solid #313244;
                border-radius: 10px;
                text-decoration: none;
                color: #cdd6f4;
                transition: all 0.3s;
                text-align: center;
            }

            .period-link:hover {
                border-color: #cba6f7;
                background: #313244;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(203, 166, 247, 0.2);
            }

            .period-link .period-name {
                font-size: 1.1em;
                font-weight: 600;
                margin-bottom: 5px;
            }

            .period-link .period-date {
                font-size: 0.9em;
                color: #a6adc8;
            }

            .info-box {
                background: #181825;
                padding: 30px;
                border-radius: 12px;
                border: 1px solid #313244;
                margin-bottom: 20px;
            }

            .info-box h3 {
                color: #cba6f7;
                margin-bottom: 15px;
                font-size: 1.3em;
            }

            .info-box p {
                color: #cdd6f4;
                margin-bottom: 10px;
            }

            .info-box ul {
                margin-left: 20px;
                color: #a6adc8;
            }

            .info-box ul li {
                margin-bottom: 8px;
            }

            .info-box code {
                background: #1e1e2e;
                padding: 2px 6px;
                border-radius: 4px;
                color: #f38ba8;
            }

            footer {
                background: #181825;
                padding: 20px;
                text-align: center;
                color: #6c7086;
                border-top: 1px solid #313244;
                margin-top: 40px;
            }

            .empty-state {
                text-align: center;
                padding: 60px 20px;
                color: #6c7086;
            }

            .empty-state-icon {
                font-size: 4em;
                margin-bottom: 20px;
                opacity: 0.5;
            }

            .empty-state p {
                font-size: 1.1em;
                margin-bottom: 10px;
            }

            .stats-badge {
                display: inline-block;
                background: #cba6f7;
                color: #1e1e2e;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 0.85em;
                font-weight: 600;
                margin-left: 10px;
            }

            /* Estilos para el selector de año */
            .year-selector {
                margin-bottom: 20px;
                text-align: center;
            }

            .year-selector label {
                color: #a6adc8;
                margin-right: 10px;
                font-weight: 600;
            }

            .year-selector select {
                background: #1e1e2e;
                border: 2px solid #313244;
                border-radius: 8px;
                color: #cdd6f4;
                padding: 8px 12px;
                font-size: 1em;
                transition: all 0.3s;
            }

            .year-selector select:focus {
                border-color: #cba6f7;
                outline: none;
            }

            .year-selector select:hover {
                border-color: #cba6f7;
            }

            .monthly-year-section {
                display: none;
                margin-top: 20px;
            }

            .monthly-year-section.active {
                display: block;
                animation: fadeIn 0.3s;
            }

            @media (max-width: 768px) {
                h1 {
                    font-size: 2em;
                }

                .nav-tabs {
                    flex-wrap: wrap;
                }

                .nav-tabs li {
                    flex: 1 1 50%;
                }

                .period-grid {
                    grid-template-columns: 1fr;
                }

                .year-selector {
                    margin-bottom: 15px;
                }

                .year-selector label {
                    display: block;
                    margin-bottom: 5px;
                    margin-right: 0;
                }
            }
        </style>
    </head>
    <body>
        <header>
            <div class="container">
                <h1>🎵 RYM Hispano Estadísticas</h1>
                <p class="subtitle">Coincidencias musicales entre usuarios</p>
            </div>
        </header>

        <nav>
            <ul class="nav-tabs">
                <li>
                    <a href="#temporal" class="tab-link active" data-tab="temporal"
                        >Temporales</a
                    >
                </li>
                <li>
                    <a href="#grupo" class="tab-link" data-tab="grupo"
                        >Grupo</a
                    >
                </li>
                <li>
                    <a href="#about" class="tab-link" data-tab="about">Acerca de</a>
                </li>
            </ul>
        </nav>

        <div class="container">
            <div class="content">
                <!-- Tab Temporal -->
                <div id="temporal" class="tab-content active">
                    <!-- Estadísticas Semanales -->
                    <div class="period-selector">
                        <h2>📀 Estadísticas Semanales<span class="stats-badge">""" + str(len(files['weekly'])) + """</span></h2>
                        <div class="period-grid">"""

    # Agregar enlaces semanales
    if files['weekly']:
        for file_info in files['weekly']:
            html += f"""
                            <a href="{file_info['filename']}" class="period-link">
                                <div class="period-name">{file_info['label']}</div>
                            </a>"""
    else:
        html += """
                            <div class="empty-state">
                                <div class="empty-state-icon">📀</div>
                                <p>No hay estadísticas semanales disponibles</p>
                                <p style="font-size: 0.9em;">Ejecuta <code>python3 html_semanal.py</code></p>
                            </div>"""

    html += """
                        </div>
                    </div>

                    <!-- Estadísticas Mensuales -->
                    <div class="period-selector">
                        <h2>📅 Estadísticas Mensuales<span class="stats-badge">""" + str(len(files['monthly'])) + """</span></h2>"""

    # Agregar selector de año si hay archivos mensuales
    if monthly_by_year:
        html += """
                        <div class="year-selector">
                            <label for="year-select">Seleccionar año:</label>
                            <select id="year-select" onchange="changeMonthlyYear(this.value)">"""

        # Agregar opción por defecto
        html += """
                                <option value="">-- Selecciona un año --</option>"""

        # Agregar opciones de años
        for year in available_years:
            html += f"""
                                <option value="{year}">{year}</option>"""

        html += """
                            </select>
                        </div>"""

        # Agregar secciones por año
        for year in available_years:
            html += f"""
                        <div class="monthly-year-section" id="year-{year}">
                            <div class="period-grid">"""

            for file_info in monthly_by_year[year]:
                html += f"""
                                <a href="{file_info['filename']}" class="period-link">
                                    <div class="period-name">{file_info['label']}</div>
                                </a>"""

            html += """
                            </div>
                        </div>"""
    else:
        html += """
                        <div class="period-grid">
                            <div class="empty-state">
                                <div class="empty-state-icon">📅</div>
                                <p>No hay estadísticas mensuales disponibles</p>
                                <p style="font-size: 0.9em;">Ejecuta <code>python3 html_mensual.py</code></p>
                            </div>
                        </div>"""

    html += """
                    </div>

                    <!-- Estadísticas Anuales -->
                    <div class="period-selector">
                        <h2>📆 Estadísticas Anuales<span class="stats-badge">""" + str(len(files['yearly'])) + """</span></h2>
                        <div class="period-grid">"""

    # Agregar enlaces anuales
    if files['yearly']:
        for file_info in files['yearly']:
            html += f"""
                            <a href="{file_info['filename']}" class="period-link">
                                <div class="period-name">{file_info['label']}</div>
                            </a>"""
    else:
        html += """
                            <div class="empty-state">
                                <div class="empty-state-icon">📆</div>
                                <p>No hay estadísticas anuales disponibles</p>
                                <p style="font-size: 0.9em;">Ejecuta <code>python3 html_anual.py</code></p>
                            </div>"""

    html += """
                        </div>
                    </div>
                </div>

                <!-- Tab Grupo -->
                <div id="grupo" class="tab-content">
                    <!-- Estadísticas de Usuarios -->
                    <div class="period-selector">
                        <h2>👤 Estadísticas de Usuarios<span class="stats-badge">""" + str(len(files['users'])) + """</span></h2>
                        <div class="period-grid">"""

    # Agregar enlaces de usuarios
    if files['users']:
        for file_info in files['users']:
            html += f"""
                            <a href="{file_info['filename']}" class="period-link">
                                <div class="period-name">{file_info['label']}</div>
                                <div class="period-date">Análisis individual</div>
                            </a>"""
    else:
        html += """
                            <div class="empty-state">
                                <div class="empty-state-icon">👤</div>
                                <p>No hay estadísticas de usuarios disponibles</p>
                                <p style="font-size: 0.9em;">Ejecuta <code>python3 html_usuarios.py</code></p>
                            </div>"""

    html += """
                        </div>
                    </div>

                    <!-- Estadísticas Grupales -->
                    <div class="period-selector">
                        <h2>👥 Estadísticas Grupales<span class="stats-badge">""" + str(len(files['grupo'])) + """</span></h2>
                        <div class="period-grid">"""

    # Agregar enlaces de grupo
    if files['grupo']:
        for file_info in files['grupo']:
            html += f"""
                            <a href="{file_info['filename']}" class="period-link">
                                <div class="period-name">{file_info['label']}</div>
                                <div class="period-date">Análisis grupal</div>
                            </a>"""
    else:
        html += """
                            <div class="empty-state">
                                <div class="empty-state-icon">👥</div>
                                <p>No hay estadísticas grupales disponibles</p>
                                <p style="font-size: 0.9em;">Ejecuta <code>python3 html_grupo.py</code></p>
                            </div>"""

    html += """
                        </div>
                    </div>
                </div>

                <!-- Tab About -->
                <div id="about" class="tab-content">
                    <div class="info-box">
                        <h3>🎵 Acerca de RYM Hispano Estadísticas</h3>
                        <p>
                            Esta aplicación genera estadísticas de coincidencias
                            musicales entre múltiples usuarios de Last.fm usando este <a href="https://github.com/volteret4/lastfm_rym">repositorio</a>
                        </p>
                    </div>

                    <div class="info-box">
                        <h3>🎯 Características</h3>
                        <ul>
                            <li>
                                <strong>Estadísticas Semanales:</strong>
                                Análisis de los últimos 7 días
                            </li>
                            <li>
                                <strong>Estadísticas Mensuales:</strong>
                                Análisis de meses completos organizados por año
                            </li>
                            <li>
                                <strong>Estadísticas Anuales:</strong> Análisis
                                de años completos
                            </li>
                            <li>
                                <strong>Estadísticas de Usuarios:</strong> Análisis
                                individual con gráficos de coincidencias y evolución
                            </li>
                            <li>
                                <strong>Estadísticas Grupales:</strong> Análisis
                                global del grupo con coincidencias y tendencias
                            </li>
                            <li>
                                <strong>Coincidencias:</strong> Muestra solo
                                artistas, canciones y álbumes escuchados por 2 o
                                más usuarios
                            </li>
                            <li>
                                <strong>Géneros:</strong> Detección automática
                                de géneros musicales
                            </li>
                            <li>
                                <strong>Sellos:</strong> Información sobre
                                sellos discográficos (si está configurado)
                            </li>
                        </ul>
                    </div>

                    <div class="info-box">
                        <h3>🛠️ Uso</h3>
                        <p><strong>Actualización de datos:</strong></p>
                        <ul>
                            <li>
                                Ejecuta
                                <code>python3 update_database.py</code>
                                diariamente para actualizar la base de datos
                            </li>
                        </ul>
                        <p><strong>Generación de estadísticas:</strong></p>
                        <ul>
                            <li>
                                <code>python3 html_semanal.py</code> - Genera
                                estadísticas semanales
                            </li>
                            <li>
                                <code>python3 html_mensual.py</code> -
                                Genera estadísticas del mes actual
                            </li>
                            <li>
                                <code>python3 html_mensual.py --months-ago 1</code>
                                - Genera estadísticas del mes pasado
                            </li>
                            <li>
                                <code>python3 html_anual.py</code> - Genera
                                estadísticas del año actual
                            </li>
                            <li>
                                <code>python3 html_anual.py --years-ago 1</code>
                                - Genera estadísticas del año pasado
                            </li>
                            <li>
                                <code>python3 html_usuarios.py</code> - Genera
                                estadísticas individuales de usuarios
                            </li>
                            <li>
                                <code>python3 html_usuarios.py --years-back 3</code>
                                - Análisis de los últimos 3 años
                            </li>
                            <li>
                                <code>python3 html_grupo.py</code> - Genera
                                estadísticas grupales globales
                            </li>
                        </ul>
                        <p><strong>Generación del índice:</strong></p>
                        <ul>
                            <li>
                                <code>python3 html_index.py</code> - Genera
                                el index.html basándose en los archivos disponibles
                            </li>
                        </ul>
                    </div>

                    <div class="info-box">
                        <h3>🔧 Configuración</h3>
                        <p>Crea un archivo <code>.env</code> con:</p>
                        <ul>
                            <li><code>LASTFM_API_KEY=tu_api_key</code></li>
                            <li>
                                <code>LASTFM_USERS=usuario1,usuario2,usuario3</code>
                            </li>
                            <li>
                                <code>DISCOGS_TOKEN=tu_token</code> (opcional)
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>

        <footer>
            <p>RYM Hispano Estadísticas | Última actualización: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
        </footer>

        <script>
            // Sistema de tabs
            const tabLinks = document.querySelectorAll(".tab-link");
            const tabContents = document.querySelectorAll(".tab-content");

            tabLinks.forEach((link) => {
                link.addEventListener("click", (e) => {
                    e.preventDefault();

                    // Remover active de todos
                    tabLinks.forEach((l) => l.classList.remove("active"));
                    tabContents.forEach((c) => c.classList.remove("active"));

                    // Activar el seleccionado
                    link.classList.add("active");
                    const tabId = link.getAttribute("data-tab");
                    document.getElementById(tabId).classList.add("active");

                    // Actualizar URL
                    window.location.hash = tabId;
                });
            });

            // Activar tab desde URL
            if (window.location.hash) {
                const hash = window.location.hash.substring(1);
                const targetLink = document.querySelector(
                    `[data-tab="${hash}"]`,
                );
                if (targetLink) {
                    targetLink.click();
                }
            }

            // Sistema de selector de año para estadísticas mensuales
            function changeMonthlyYear(year) {
                // Ocultar todas las secciones de años
                const yearSections = document.querySelectorAll('.monthly-year-section');
                yearSections.forEach(section => {
                    section.classList.remove('active');
                });

                // Mostrar la sección del año seleccionado
                if (year) {
                    const selectedSection = document.getElementById(`year-${year}`);
                    if (selectedSection) {
                        selectedSection.classList.add('active');
                    }
                }
            }

            // Mostrar el primer año por defecto si existe
            document.addEventListener('DOMContentLoaded', function() {
                const yearSelect = document.getElementById('year-select');
                if (yearSelect && yearSelect.options.length > 1) {
                    // Seleccionar el primer año disponible (más reciente)
                    const firstYear = yearSelect.options[1].value;
                    yearSelect.value = firstYear;
                    changeMonthlyYear(firstYear);
                }
            });
        </script>
    </body>
</html>"""

    return html


def main():
    print("=" * 60)
    print("GENERADOR DE INDEX.HTML")
    print("=" * 60)

    docs_dir = 'docs'

    # Crear carpeta docs si no existe
    if not os.path.exists(docs_dir):
        print(f"Creando carpeta '{docs_dir}'...")
        os.makedirs(docs_dir)

    # Escanear archivos
    print(f"Escaneando archivos en '{docs_dir}'...")
    files = scan_html_files(docs_dir)

    print(f"Semanales: {len(files['weekly'])}")
    print(f"Mensuales: {len(files['monthly'])}")
    print(f"Anuales: {len(files['yearly'])}")
    print(f"Usuarios: {len(files['users'])}")
    print(f"Grupo: {len(files['grupo'])}")

    # Generar HTML
    print(f"Generando index.html...")
    html_content = generate_index_html(files)

    # Guardar archivo
    output_path = os.path.join(docs_dir, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Archivo generado: {output_path}")
    print("\n" + "=" * 60)
    print("😃 PROCESO COMPLETADO")
    print("=" * 60)


if __name__ == '__main__':
    main()
