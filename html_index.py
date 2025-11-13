#!/usr/bin/env python3
"""
Generate Index
Genera el index.html dinámicamente basándose en los archivos HTML en docs/
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import unicodedata

# Cargar variables de entorno
try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

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

    # Leer usuarios reales del entorno
    users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
    if not users:
        print("⚠️  No se encontraron usuarios en LASTFM_USERS, usando usuarios de ejemplo")
        users = ['usuario1', 'usuario2', 'usuario3']  # Fallback

    # Leer iconos de usuarios del entorno
    icons_env = os.getenv('LASTFM_USERS_ICONS', '')
    user_icons = {}
    if icons_env:
        for pair in icons_env.split(','):
            if ':' in pair:
                user, icon = pair.split(':', 1)
                user_icons[user.strip()] = icon.strip()

    print(f"📋 Usuarios detectados para el selector: {', '.join(users)}")

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
                padding: 0 20px;
            }

            header {
                background: #181825;
                padding: 2rem 0;
                border-bottom: 2px solid #cba6f7;
            }

            h1 {
                font-size: 2.5em;
                color: #cba6f7;
                margin-bottom: 0.5rem;
                text-align: center;
            }

            .subtitle {
                text-align: center;
                color: #a6adc8;
                font-size: 1.1em;
            }

            /* Botón de usuario circular */
            .user-button {
                position: fixed;
                top: 20px;
                right: 20px;
                width: 50px;
                height: 50px;
                background: #cba6f7;
                color: #1e1e2e;
                border: none;
                border-radius: 50%;
                font-size: 24px;
                cursor: pointer;
                z-index: 1000;
                transition: all 0.3s;
                box-shadow: 0 4px 16px rgba(203, 166, 247, 0.3);
            }

            .user-button:hover {
                background: #ddb6f2;
                transform: scale(1.1);
            }

            /* Modal de selección de usuario */
            .user-modal {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0,0,0,0.7);
                z-index: 999;
                display: none;
            }

            .user-modal-content {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: #1e1e2e;
                border: 2px solid #cba6f7;
                border-radius: 12px;
                padding: 20px;
                max-width: 400px;
                width: 90%;
            }

            .user-modal-header {
                color: #cba6f7;
                font-size: 1.2em;
                font-weight: 600;
                margin-bottom: 15px;
                text-align: center;
            }

            .user-options {
                display: flex;
                flex-direction: column;
                gap: 10px;
            }

            .user-option {
                padding: 12px 16px;
                background: #313244;
                color: #cdd6f4;
                border: 2px solid #45475a;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s;
                text-align: center;
            }

            .user-option:hover {
                border-color: #cba6f7;
                background: #45475a;
            }

            .user-option.selected {
                background: #cba6f7;
                color: #1e1e2e;
                border-color: #cba6f7;
            }

            .user-modal-close {
                display: block;
                margin: 15px auto 0;
                padding: 8px 16px;
                background: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                cursor: pointer;
            }

            .user-modal-close:hover {
                background: #6c7086;
            }

            nav {
                background: #1e1e2e;
                padding: 1rem 0;
                border-bottom: 1px solid #313244;
            }

            .nav-tabs {
                display: flex;
                justify-content: center;
                list-style: none;
                gap: 1rem;
            }

            .tab-link {
                padding: 12px 24px;
                background: #313244;
                color: #cdd6f4;
                text-decoration: none;
                border-radius: 8px;
                transition: all 0.3s;
                font-weight: 600;
            }

            .tab-link:hover {
                background: #45475a;
                color: #cba6f7;
            }

            .tab-link.active {
                background: #cba6f7;
                color: #1e1e2e;
            }

            .content {
                padding: 2rem 0;
            }

            .tab-content {
                display: none;
            }

            .tab-content.active {
                display: block;
                animation: fadeIn 0.3s;
            }

            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(10px); }
                to { opacity: 1; transform: translateY(0); }
            }

            /* Secciones colapsables */
            .period-selector {
                margin-bottom: 3rem;
                background: #181825;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            }

            .section-header {
                padding: 20px 24px;
                background: #1e1e2e;
                border-bottom: 1px solid #313244;
                cursor: pointer;
                transition: all 0.3s;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .section-header:hover {
                background: #2a2a3e;
            }

            .section-header h2 {
                color: #cba6f7;
                font-size: 1.3em;
                margin: 0;
                display: flex;
                align-items: center;
                gap: 10px;
            }

            .stats-badge {
                background: #cba6f7;
                color: #1e1e2e;
                font-size: 0.7em;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 600;
            }

            .collapse-icon {
                font-size: 1.2em;
                color: #a6adc8;
                transition: transform 0.3s;
            }

            .section-header[aria-expanded="true"] .collapse-icon {
                transform: rotate(180deg);
            }

            .section-content {
                display: none;
                padding: 24px;
                border-top: 1px solid #313244;
            }

            .section-content.active {
                display: block;
                animation: fadeIn 0.3s;
            }

            .period-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
            }

            .period-link {
                display: block;
                padding: 1rem;
                background: #313244;
                border-radius: 8px;
                text-decoration: none;
                color: #cdd6f4;
                transition: all 0.3s;
                border: 2px solid transparent;
            }

            .period-link:hover {
                background: #45475a;
                border-color: #cba6f7;
                transform: translateY(-2px);
            }

            .period-name {
                font-size: 1.1em;
                font-weight: 600;
                margin-bottom: 0.5rem;
            }

            .period-date {
                color: #a6adc8;
                font-size: 0.9em;
            }

            .empty-state {
                grid-column: 1 / -1;
                text-align: center;
                padding: 3rem 1rem;
                color: #6c7086;
            }

            .empty-state-icon {
                font-size: 3em;
                margin-bottom: 1rem;
            }

            .empty-state p {
                margin-bottom: 0.5rem;
            }

            code {
                background: #313244;
                color: #cba6f7;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: "Monaco", "Menlo", monospace;
            }

            .year-selector {
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
                flex-wrap: wrap;
            }

            .year-selector label {
                color: #cba6f7;
                font-weight: 600;
            }

            .year-selector select {
                background: #313244;
                color: #cdd6f4;
                border: 2px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 1em;
            }

            .year-selector select:focus {
                outline: none;
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

            .info-box {
                background: #181825;
                padding: 2rem;
                border-radius: 12px;
                margin-bottom: 2rem;
                border: 1px solid #313244;
            }

            .info-box h3 {
                color: #cba6f7;
                margin-bottom: 1rem;
                font-size: 1.3em;
            }

            .info-box p {
                margin-bottom: 1rem;
                color: #a6adc8;
            }

            .info-box ul {
                list-style: none;
                margin-left: 1rem;
            }

            .info-box li {
                margin-bottom: 0.5rem;
                position: relative;
            }

            .info-box li:before {
                content: "▶";
                color: #cba6f7;
                position: absolute;
                left: -1rem;
            }

            footer {
                background: #181825;
                padding: 2rem 0;
                border-top: 1px solid #313244;
                text-align: center;
                color: #6c7086;
                margin-top: 3rem;
            }

            /* Estilos responsive para móviles */
            @media (max-width: 768px) {
                .container {
                    padding: 0 15px; /* MARGEN REDUCIDO - puedes cambiarlo aquí */
                }

                h1 {
                    font-size: 2em;
                }

                .nav-tabs {
                    flex-wrap: wrap;
                }

                .nav-tabs li {
                    flex: 1 1 50%;
                }

                /* Temporal en 2 columnas en móvil */
                .period-grid {
                    grid-template-columns: repeat(2, 1fr); /* 2 COLUMNAS EN MÓVIL - puedes cambiar a 1fr para 1 columna */
                    gap: 0.8rem; /* Gap más pequeño en móvil */
                }

                .period-link {
                    padding: 0.8rem; /* Padding más pequeño */
                    font-size: 0.9em;
                }

                .period-name {
                    font-size: 1em;
                    margin-bottom: 0.3rem;
                }

                .year-selector {
                    margin-bottom: 15px;
                }

                .year-selector label {
                    display: block;
                    margin-bottom: 5px;
                    margin-right: 0;
                }

                .section-header {
                    padding: 15px 18px; /* Padding más pequeño en header */
                }

                .section-content {
                    padding: 18px; /* Padding más pequeño en content */
                }

                .user-button {
                    top: 15px;
                    right: 15px;
                    width: 45px;
                    height: 45px;
                    font-size: 20px;
                }

                .info-box {
                    padding: 1.5rem; /* Padding más pequeño en info boxes */
                    margin-bottom: 1.5rem;
                }
            }

            /* Para pantallas muy pequeñas */
            @media (max-width: 480px) {
                .container {
                    padding: 0 10px; /* MARGEN AÚN MÁS REDUCIDO - ajústalo aquí si quieres menos margen */
                }

                .period-grid {
                    gap: 0.6rem;
                }

                .section-header {
                    padding: 12px 15px;
                }

                .section-content {
                    padding: 15px;
                }
            }
        </style>
    </head>
    <body>
        <!-- Botón de usuario circular -->
        <button class="user-button" id="userButton" title="Seleccionar usuario destacado"></button>

        <!-- Modal de selección de usuario -->
        <div class="user-modal" id="userModal">
            <div class="user-modal-content">
                <div class="user-modal-header">Seleccionar Usuario Destacado</div>
                <div class="user-options" id="userOptions">
                    <div class="user-option selected" data-user="">Ninguno</div>
                    <!-- Se llenarán dinámicamente con JavaScript -->
                </div>
                <button class="user-modal-close" id="userModalClose">Cerrar</button>
            </div>
        </div>

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
                        <div class="section-header" onclick="toggleSection('weekly')" aria-expanded="false">
                            <h2>📀 Estadísticas Semanales<span class="stats-badge">""" + str(len(files['weekly'])) + """</span></h2>
                            <span class="collapse-icon">▼</span>
                        </div>
                        <div class="section-content" id="weekly-content">
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
                    </div>

                    <!-- Estadísticas Mensuales -->
                    <div class="period-selector">
                        <div class="section-header" onclick="toggleSection('monthly')" aria-expanded="false">
                            <h2>📅 Estadísticas Mensuales<span class="stats-badge">""" + str(len(files['monthly'])) + """</span></h2>
                            <span class="collapse-icon">▼</span>
                        </div>
                        <div class="section-content" id="monthly-content">"""

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
                    </div>

                    <!-- Estadísticas Anuales -->
                    <div class="period-selector">
                        <div class="section-header" onclick="toggleSection('yearly')" aria-expanded="false">
                            <h2>📆 Estadísticas Anuales<span class="stats-badge">""" + str(len(files['yearly'])) + """</span></h2>
                            <span class="collapse-icon">▼</span>
                        </div>
                        <div class="section-content" id="yearly-content">
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
                </div>

                <!-- Tab Grupo -->
                <div id="grupo" class="tab-content">
                    <!-- Estadísticas de Usuarios -->
                    <div class="period-selector">
                        <h2>👤 Estadísticas de Usuarios <span class="stats-badge">""" + str(len(files['users'])) + """</span></h2>
                        <div class="period-grid">"""

    # Agregar enlaces de usuarios
    if files['users']:
        for file_info in files['users']:
            html += f"""
                            <a href="{file_info['filename']}" class="period-link">
                                <div class="period-name">{file_info['label']}</div>
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
                        <h2>👥 Estadísticas Grupales <span class="stats-badge">""" + str(len(files['grupo'])) + """</span></h2>
                        <div class="period-grid">"""

    # Agregar enlaces de grupo
    if files['grupo']:
        for file_info in files['grupo']:
            html += f"""
                            <a href="{file_info['filename']}" class="period-link">
                                <div class="period-name">{file_info['label']}</div>
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
                        <ul>
                            <li>
                                <strong>Temporales:</strong> Análisis semanales,
                                mensuales y anuales
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
            // Usuarios reales del entorno LASTFM_USERS e iconos de LASTFM_USERS_ICONS
            const userIcons = """ + json.dumps(user_icons, ensure_ascii=False) + """;
            const availableUsers = """ + json.dumps(users, ensure_ascii=False) + """;

            // Funcionalidad del botón de usuario
            function initializeUserSelector() {
                const userButton = document.getElementById('userButton');
                const userModal = document.getElementById('userModal');
                const userModalClose = document.getElementById('userModalClose');
                const userOptions = document.getElementById('userOptions');

                // Cargar usuario guardado desde localStorage
                let selectedUser = localStorage.getItem('lastfm_selected_user') || '';

                // Llenar opciones de usuarios
                availableUsers.forEach(user => {
                    const option = document.createElement('div');
                    option.className = 'user-option';
                    option.dataset.user = user;

                    const icon = userIcons[user];
                    if (icon) {
                        if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {
                            option.innerHTML = `<img src="${icon}" alt="${user}" style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;"> ${user}`;
                        } else {
                            option.innerHTML = `<span style="font-size:1.2em;margin-right:8px;">${icon}</span> ${user}`;
                        }
                    } else {
                        option.textContent = user;
                    }

                    userOptions.appendChild(option);
                    function updateUserButtonIcon(user) {
                        const userButton = document.getElementById('userButton');
                        const icon = userIcons[user];
                        if (icon) {
                            if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {
                                userButton.innerHTML = `<img src="${icon}" alt="${user}" style="width:100%;height:100%;border-radius:50%;">`;
                            } else {
                                userButton.textContent = icon;
                            }
                        } else {
                            userButton.textContent = '👤';
                        }
                    }

                });


                // Marcar opción seleccionada
                updateSelectedUserOption(selectedUser);
                updateUserButtonIcon(selectedUser);

                // Event listeners
                userButton.addEventListener('click', () => {
                    userModal.style.display = 'block';
                });

                userModalClose.addEventListener('click', () => {
                    userModal.style.display = 'none';
                });

                userModal.addEventListener('click', (e) => {
                    if (e.target === userModal) {
                        userModal.style.display = 'none';
                    }
                });

                userOptions.addEventListener('click', (e) => {
                    if (e.target.classList.contains('user-option')) {
                        const user = e.target.dataset.user;
                        selectedUser = user;

                        // Guardar en localStorage
                        if (user) {
                            localStorage.setItem('lastfm_selected_user', user);
                        } else {
                            localStorage.removeItem('lastfm_selected_user');
                        }

                        updateSelectedUserOption(user);
                        userModal.style.display = 'none';
                    }
                });
            }

            function updateSelectedUserOption(selectedUser) {
                const userOptions = document.getElementById('userOptions');
                userOptions.querySelectorAll('.user-option').forEach(option => {
                    option.classList.remove('selected');
                    if (option.dataset.user === selectedUser) {
                        option.classList.add('selected');
                    }
                });
            }

            // Sistema de secciones colapsables
            function toggleSection(sectionName) {
                const content = document.getElementById(sectionName + '-content');
                const header = content.previousElementSibling;
                const isExpanded = header.getAttribute('aria-expanded') === 'true';

                if (isExpanded) {
                    // Cerrar sección
                    content.classList.remove('active');
                    header.setAttribute('aria-expanded', 'false');
                } else {
                    // Abrir sección
                    content.classList.add('active');
                    header.setAttribute('aria-expanded', 'true');

                    // Si es la sección mensual y hay años disponibles, mostrar el primer año
                    if (sectionName === 'monthly') {
                        const yearSelect = document.getElementById('year-select');
                        if (yearSelect && yearSelect.options.length > 1 && !yearSelect.value) {
                            const firstYear = yearSelect.options[1].value;
                            yearSelect.value = firstYear;
                            changeMonthlyYear(firstYear);
                        }
                    }
                }
            }

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

            // Inicialización
            document.addEventListener('DOMContentLoaded', function() {
                initializeUserSelector();
            });
        </script>
    </body>
</html>"""

    return html


def main():
    print("=" * 60)
    print("GENERADOR DE INDEX.HTML")
    print("=" * 60)

    # Verificar variable de entorno
    users_env = os.getenv('LASTFM_USERS', '')
    if users_env:
        users_list = [u.strip() for u in users_env.split(',') if u.strip()]
        print(f"✅ Variable LASTFM_USERS encontrada: {len(users_list)} usuarios")
        print(f"👥 Usuarios: {', '.join(users_list)}")
    else:
        print("⚠️  Variable LASTFM_USERS no encontrada. El selector de usuarios usará valores por defecto.")
        print("💡 Asegúrate de tener un archivo .env con: LASTFM_USERS=usuario1,usuario2,usuario3")

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
    print(f"🔗 El selector de usuarios está integrado con localStorage (clave: 'lastfm_selected_user')")
    print("\n" + "=" * 60)
    print("😃 PROCESO COMPLETADO")
    print("=" * 60)


if __name__ == '__main__':
    main()
