#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión Optimizada
Genera un HTML ligero que carga datos desde archivos JSON
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

# Importar las clases necesarias

from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database_extended import UserStatsDatabaseExtended
from tools.users.user_stats_discoveries import DiscoveriesDataGenerator


def generate_all_data_files(users, years_back, output_dir):
    """Genera todos los archivos JSON necesarios"""

    current_year = datetime.now().year
    from_year = current_year - years_back
    to_year = current_year
    period = f"{from_year}-{to_year}"

    print(f"📊 Generando datos para periodo {period}...")

    # Crear directorios necesarios
    data_dir = Path(output_dir) / "data"
    users_data_dir = data_dir / "usuarios" / period
    users_data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generar datos de estadísticas principales para cada usuario
    print(f"\n📈 Paso 1/2: Generando estadísticas principales...")
    database = UserStatsDatabaseExtended()
    analyzer = UserStatsAnalyzer(database, years_back=years_back)

    for user in users:
        print(f"  • Procesando {user}...")
        user_stats = analyzer.analyze_user(user, users)

        # Remover discoveries si existen (se cargarán por separado)
        if 'individual' in user_stats and 'discoveries' in user_stats['individual']:
            del user_stats['individual']['discoveries']

        # Guardar stats en JSON
        stats_file = users_data_dir / f"{user}_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(user_stats, f, indent=2, ensure_ascii=False)

        # Mostrar resumen
        total_scrobbles = sum(user_stats.get('yearly_scrobbles', {}).values())
        unique_counts = user_stats.get('unique_counts', {})
        print(f"    ✅ {total_scrobbles:,} scrobbles")
        if unique_counts:
            print(f"       {unique_counts.get('total_artists', 0)} artistas, "
                  f"{unique_counts.get('total_albums', 0)} álbumes, "
                  f"{unique_counts.get('total_tracks', 0)} tracks")

    database.close()

    # 2. Generar datos de descubrimientos/novedades
    print(f"\n✨ Paso 2/2: Generando datos de novedades...")
    discoveries_generator = DiscoveriesDataGenerator()

    if not discoveries_generator._check_tables():
        print("    ⚠️  Tablas de primeras escuchas no encontradas")
        print("    💡 Ejecuta: python create_first_listen_tables_mbid.py")
        discoveries_available = False
    else:
        discoveries_available = True
        for user in users:
            try:
                output_file = discoveries_generator.generate_user_json(
                    user, from_year, to_year, str(users_data_dir)
                )
            except Exception as e:
                print(f"    ❌ Error generando novedades para {user}: {e}")

        # Generar índice
        discoveries_generator._generate_index_file(str(users_data_dir), users, period)

    discoveries_generator.close()

    # 3. Generar archivo de configuración
    config = {
        'period': period,
        'from_year': from_year,
        'to_year': to_year,
        'users': users,
        'discoveries_available': discoveries_available,
        'generated_at': datetime.now().isoformat()
    }

    config_file = data_dir / f"config_{period}.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Archivos de datos generados en: {users_data_dir}")
    print(f"📋 Configuración guardada en: {config_file}")

    return {
        'data_dir': str(data_dir),
        'users_data_dir': str(users_data_dir),
        'config_file': str(config_file),
        'discoveries_available': discoveries_available,
        'period': period
    }


def generate_optimized_html(data_info, output_file):
    """Genera HTML optimizado que carga datos desde JSON"""

    users = data_info.get('users', [])
    period = data_info.get('period', '')
    discoveries_available = data_info.get('discoveries_available', False)

    # Obtener iconos de usuarios
    icons_env = os.getenv('LASTFM_USERS_ICONS', '')
    user_icons = {}
    if icons_env:
        for pair in icons_env.split(','):
            if ':' in pair:
                user, icon = pair.split(':', 1)
                user_icons[user.strip()] = icon.strip()

    users_json = json.dumps(users, ensure_ascii=False)
    user_icons_json = json.dumps(user_icons, ensure_ascii=False)

    # Colores para gráficos
    colors = [
        '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
        '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
        '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
    ]
    colors_json = json.dumps(colors, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - Estadísticas {period}</title>
    <link rel="icon" type="image/png" href="images/music.png">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: #181825;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: #1e1e2e;
            padding: 20px 30px;
            border-bottom: 2px solid #cba6f7;
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 80px;
        }}

        .header-content {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex-grow: 1;
        }}

        h1 {{
            font-size: 2em;
            color: #cba6f7;
            margin-bottom: 10px;
        }}

        .period-badge {{
            background: #313244;
            color: #cba6f7;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 500;
        }}

        .nav-buttons {{
            display: flex;
            gap: 15px;
            margin-top: 10px;
        }}

        .nav-button {{
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            text-decoration: none;
            font-weight: 500;
        }}

        .nav-button:hover {{
            background: #45475a;
            border-color: #cba6f7;
            transform: translateY(-2px);
        }}

        .user-section {{
            padding: 30px;
        }}

        .user-selector {{
            display: flex;
            justify-content: center;
            gap: 15px;
            flex-wrap: wrap;
            margin-bottom: 30px;
        }}

        .user-button {{
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            padding: 12px 24px;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 1.1em;
            font-weight: 500;
        }}

        .user-button:hover {{
            background: #45475a;
            border-color: #cba6f7;
            transform: translateY(-2px);
        }}

        .user-button.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .user-content {{
            display: none;
        }}

        .user-content.active {{
            display: block;
        }}

        .tabs {{
            display: flex;
            gap: 10px;
            border-bottom: 2px solid #313244;
            margin-bottom: 30px;
            overflow-x: auto;
            padding-bottom: 10px;
        }}

        .nav-tab {{
            background: transparent;
            color: #a6adc8;
            border: none;
            padding: 12px 24px;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 1em;
            white-space: nowrap;
        }}

        .nav-tab:hover {{
            background: #313244;
            color: #cdd6f4;
        }}

        .nav-tab.active {{
            background: #313244;
            color: #cba6f7;
            border-bottom: 3px solid #cba6f7;
        }}

        .tab-content {{
            display: none;
            animation: fadeIn 0.3s;
        }}

        .tab-content.active {{
            display: block;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: #1e1e2e;
            padding: 20px;
            border-radius: 12px;
            border: 2px solid #313244;
            transition: all 0.3s;
        }}

        .stat-card:hover {{
            border-color: #cba6f7;
            transform: translateY(-2px);
        }}

        .stat-card h3 {{
            color: #a6adc8;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .stat-card .value {{
            color: #cba6f7;
            font-size: 2em;
            font-weight: bold;
        }}

        .chart-container {{
            background: #1e1e2e;
            padding: 20px;
            border-radius: 12px;
            border: 2px solid #313244;
            margin-bottom: 20px;
        }}

        .chart-container h3 {{
            color: #cba6f7;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}

        .loading-spinner {{
            text-align: center;
            padding: 40px;
            color: #a6adc8;
        }}

        .error-message {{
            background: #f38ba8;
            color: #1e1e2e;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: center;
        }}

        .top-list {{
            background: #1e1e2e;
            border-radius: 12px;
            overflow: hidden;
            border: 2px solid #313244;
        }}

        .top-item {{
            padding: 15px 20px;
            border-bottom: 1px solid #313244;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: background 0.2s;
        }}

        .top-item:hover {{
            background: #313244;
        }}

        .top-item:last-child {{
            border-bottom: none;
        }}

        .rank {{
            color: #cba6f7;
            font-weight: bold;
            font-size: 1.2em;
            min-width: 40px;
        }}

        .item-name {{
            flex-grow: 1;
            margin: 0 20px;
        }}

        .item-count {{
            color: #a6adc8;
            font-weight: 500;
        }}

        .popup-overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}

        .popup-overlay.active {{
            display: flex;
        }}

        .popup-content {{
            background: #181825;
            padding: 30px;
            border-radius: 16px;
            max-width: 600px;
            max-height: 80vh;
            overflow-y: auto;
            border: 2px solid #cba6f7;
        }}

        .popup-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}

        .popup-close {{
            background: #313244;
            border: none;
            color: #cdd6f4;
            font-size: 1.5em;
            cursor: pointer;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            transition: all 0.3s;
        }}

        .popup-close:hover {{
            background: #45475a;
        }}

        .discoveries-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>🎵 Last.fm Estadísticas de Usuarios</h1>
                <span class="period-badge">📅 Periodo: {period}</span>
                <div class="nav-buttons">
                    <a href="index.html" class="nav-button">🏠 Inicio</a>
                    <a href="index.html#temporal" class="nav-button">⏰ Temporales</a>
                </div>
            </div>
        </header>

        <div class="user-section">
            <div class="user-selector" id="userSelector">
                <!-- Los botones de usuario se generarán dinámicamente -->
            </div>

            <div id="userContentContainer">
                <!-- El contenido de cada usuario se cargará dinámicamente -->
            </div>
        </div>
    </div>

    <!-- Popup para mostrar detalles -->
    <div class="popup-overlay" id="popupOverlay">
        <div class="popup-content" id="popupContent">
            <!-- Contenido del popup se generará dinámicamente -->
        </div>
    </div>

    <script>
        // Configuración global
        const CONFIG = {{
            users: {users_json},
            userIcons: {user_icons_json},
            colors: {colors_json},
            period: '{period}',
            dataPath: 'data/usuarios/{period}/',
            discoveriesAvailable: {str(discoveries_available).lower()}
        }};

        // Cache para datos cargados
        const dataCache = {{}};

        // Estado de la aplicación
        let currentUser = null;
        let currentTab = 'overview';
        let charts = {{}};

        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {{
            initializeUserButtons();

            // Seleccionar primer usuario por defecto
            if (CONFIG.users.length > 0) {{
                selectUser(CONFIG.users[0]);
            }}
        }});

        function initializeUserButtons() {{
            const container = document.getElementById('userSelector');
            container.innerHTML = '';

            CONFIG.users.forEach(user => {{
                const button = document.createElement('button');
                button.className = 'user-button';

                const icon = CONFIG.userIcons[user] || '👤';
                button.innerHTML = `${{icon}} ${{user}}`;

                button.onclick = () => selectUser(user);
                container.appendChild(button);
            }});
        }}

        async function selectUser(user) {{
            currentUser = user;

            // Actualizar botones
            document.querySelectorAll('.user-button').forEach(btn => {{
                btn.classList.remove('active');
                if (btn.textContent.includes(user)) {{
                    btn.classList.add('active');
                }}
            }});

            // Cargar datos del usuario
            await loadUserData(user);
        }}

        async function loadUserData(user) {{
            const container = document.getElementById('userContentContainer');

            // Mostrar spinner de carga
            container.innerHTML = `
                <div class="loading-spinner">
                    <p>🔄 Cargando datos de ${{user}}...</p>
                </div>
            `;

            try {{
                // Cargar stats principales
                const statsData = await loadJSON(`${{CONFIG.dataPath}}${{user}}_stats.json`);
                dataCache[user] = {{ stats: statsData }};

                // Cargar discoveries si está disponible
                if (CONFIG.discoveriesAvailable) {{
                    try {{
                        const discoveriesData = await loadJSON(`${{CONFIG.dataPath}}${{user}}.json`);
                        dataCache[user].discoveries = discoveriesData;
                    }} catch (e) {{
                        console.warn('No se pudieron cargar discoveries para', user);
                    }}
                }}

                // Renderizar contenido
                renderUserContent(user, statsData);

            }} catch (error) {{
                console.error('Error cargando datos:', error);
                container.innerHTML = `
                    <div class="error-message">
                        ❌ Error cargando datos de ${{user}}: ${{error.message}}
                    </div>
                `;
            }}
        }}

        async function loadJSON(path) {{
            const response = await fetch(path);
            if (!response.ok) {{
                throw new Error(`HTTP error! status: ${{response.status}}`);
            }}
            return await response.json();
        }}

        function renderUserContent(user, data) {{
            const container = document.getElementById('userContentContainer');

            // Crear tabs
            const tabs = ['overview', 'charts', 'genres', 'labels', 'evolution'];
            if (CONFIG.discoveriesAvailable && dataCache[user].discoveries) {{
                tabs.push('discoveries');
            }}

            const tabNames = {{
                'overview': '📊 Resumen',
                'charts': '🎯 Rankings',
                'genres': '🎭 Géneros',
                'labels': '🏢 Sellos',
                'evolution': '📈 Evolución',
                'discoveries': '✨ Novedades'
            }};

            let tabsHTML = '<div class="tabs">';
            tabs.forEach(tab => {{
                const active = tab === 'overview' ? 'active' : '';
                tabsHTML += `<div class="nav-tab ${{active}}" onclick="switchTab('${{tab}}')">${{tabNames[tab]}}</div>`;
            }});
            tabsHTML += '</div>';

            container.innerHTML = tabsHTML + '<div id="tabContentContainer"></div>';

            // Mostrar primera tab
            switchTab('overview');
        }}

        function switchTab(tabName) {{
            currentTab = tabName;

            // Actualizar tabs
            document.querySelectorAll('.nav-tab').forEach(tab => {{
                tab.classList.remove('active');
            }});
            event.target.classList.add('active');

            // Renderizar contenido de la tab
            const container = document.getElementById('tabContentContainer');

            switch(tabName) {{
                case 'overview':
                    renderOverview(container);
                    break;
                case 'charts':
                    renderCharts(container);
                    break;
                case 'genres':
                    renderGenres(container);
                    break;
                case 'labels':
                    renderLabels(container);
                    break;
                case 'evolution':
                    renderEvolution(container);
                    break;
                case 'discoveries':
                    renderDiscoveries(container);
                    break;
            }}
        }}

        function renderOverview(container) {{
            const data = dataCache[currentUser].stats;

            const totalScrobbles = Object.values(data.yearly_scrobbles || {{}}).reduce((a, b) => a + b, 0);
            const uniqueCounts = data.unique_counts || {{}};

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="stats-grid">
                        <div class="stat-card">
                            <h3>Total Scrobbles</h3>
                            <div class="value">${{totalScrobbles.toLocaleString()}}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Artistas Únicos</h3>
                            <div class="value">${{(uniqueCounts.total_artists || 0).toLocaleString()}}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Álbumes Únicos</h3>
                            <div class="value">${{(uniqueCounts.total_albums || 0).toLocaleString()}}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Canciones Únicas</h3>
                            <div class="value">${{(uniqueCounts.total_tracks || 0).toLocaleString()}}</div>
                        </div>
                    </div>

                    <div class="chart-container">
                        <h3>Scrobbles por Año</h3>
                        <canvas id="yearlyChart"></canvas>
                    </div>
                </div>
            `;

            // Renderizar gráfico de scrobbles por año
            renderYearlyChart(data.yearly_scrobbles);
        }}

        function renderYearlyChart(yearlyData) {{
            const ctx = document.getElementById('yearlyChart');
            if (!ctx) return;

            const years = Object.keys(yearlyData).sort();
            const values = years.map(year => yearlyData[year]);

            if (charts.yearly) charts.yearly.destroy();

            charts.yearly = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: 'Scrobbles',
                        data: values,
                        backgroundColor: CONFIG.colors[0],
                        borderColor: CONFIG.colors[0],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        x: {{
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }}
                    }}
                }}
            }});
        }}

        function renderCharts(container) {{
            const data = dataCache[currentUser].stats;

            // Renderizar rankings de artistas, álbumes y tracks
            container.innerHTML = `
                <div class="tab-content active">
                    <div class="chart-container">
                        <h3>🎤 Top Artistas</h3>
                        <div id="topArtists" class="top-list"></div>
                    </div>
                    <div class="chart-container">
                        <h3>💿 Top Álbumes</h3>
                        <div id="topAlbums" class="top-list"></div>
                    </div>
                    <div class="chart-container">
                        <h3>🎵 Top Canciones</h3>
                        <div id="topTracks" class="top-list"></div>
                    </div>
                </div>
            `;

            // Renderizar listas
            renderTopList('topArtists', data.artists?.rankings?.all_time?.slice(0, 20) || []);
            renderTopList('topAlbums', data.albums?.rankings?.all_time?.slice(0, 20) || []);
            renderTopList('topTracks', data.tracks?.rankings?.all_time?.slice(0, 20) || []);
        }}

        function renderTopList(elementId, items) {{
            const container = document.getElementById(elementId);
            if (!container) return;

            container.innerHTML = items.map((item, index) => `
                <div class="top-item">
                    <span class="rank">${{index + 1}}</span>
                    <span class="item-name">${{item.name}}</span>
                    <span class="item-count">${{item.count.toLocaleString()}} plays</span>
                </div>
            `).join('');
        }}

        function renderGenres(container) {{
            const data = dataCache[currentUser].stats;
            const genresData = data.genres || {{}};

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="chart-container">
                        <h3>Distribución de Géneros</h3>
                        <canvas id="genresChart"></canvas>
                    </div>
                </div>
            `;

            // Renderizar gráfico de géneros (usar datos de lastfm, musicbrainz o discogs)
            const providers = ['lastfm', 'musicbrainz', 'discogs'];
            let genresPieData = null;

            for (const provider of providers) {{
                if (genresData[provider]?.pie_chart) {{
                    genresPieData = genresData[provider].pie_chart;
                    break;
                }}
            }}

            if (genresPieData && genresPieData.data) {{
                renderPieChart('genresChart', genresPieData.data);
            }}
        }}

        function renderLabels(container) {{
            const data = dataCache[currentUser].stats;
            const labelsData = data.labels?.pie_chart || {{}};

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="chart-container">
                        <h3>Sellos Discográficos</h3>
                        <canvas id="labelsChart"></canvas>
                    </div>
                </div>
            `;

            if (labelsData.data) {{
                renderPieChart('labelsChart', labelsData.data);
            }}
        }}

        function renderPieChart(canvasId, data) {{
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;

            const labels = data.map(item => item.label);
            const values = data.map(item => item.count);

            if (charts[canvasId]) charts[canvasId].destroy();

            charts[canvasId] = new Chart(ctx, {{
                type: 'pie',
                data: {{
                    labels: labels,
                    datasets: [{{
                        data: values,
                        backgroundColor: CONFIG.colors,
                        borderColor: '#181825',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            position: 'right',
                            labels: {{ color: '#cdd6f4' }}
                        }}
                    }}
                }}
            }});
        }}

        function renderEvolution(container) {{
            const data = dataCache[currentUser].stats;
            const evolution = data.evolution || {{}};

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="discoveries-grid">
                        <div class="chart-container">
                            <h3>Evolución Artistas</h3>
                            <canvas id="evolutionArtistsChart"></canvas>
                        </div>
                        <div class="chart-container">
                            <h3>Evolución Álbumes</h3>
                            <canvas id="evolutionAlbumsChart"></canvas>
                        </div>
                        <div class="chart-container">
                            <h3>Evolución Canciones</h3>
                            <canvas id="evolutionTracksChart"></canvas>
                        </div>
                    </div>
                </div>
            `;

            // Renderizar gráficos de evolución
            if (evolution.artists_timeline) {{
                renderLineChart('evolutionArtistsChart', evolution.artists_timeline, 'Artistas');
            }}
            if (evolution.albums_timeline) {{
                renderLineChart('evolutionAlbumsChart', evolution.albums_timeline, 'Álbumes');
            }}
            if (evolution.tracks_timeline) {{
                renderLineChart('evolutionTracksChart', evolution.tracks_timeline, 'Canciones');
            }}
        }}

        function renderLineChart(canvasId, timelineData, label) {{
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;

            const years = Object.keys(timelineData).sort();
            const cumulative = [];
            const yearly = [];

            let total = 0;
            years.forEach(year => {{
                const yearData = timelineData[year];
                const count = yearData.unique || yearData.count || 0;
                total += count;
                cumulative.push(total);
                yearly.push(count);
            }});

            if (charts[canvasId]) charts[canvasId].destroy();

            charts[canvasId] = new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: years,
                    datasets: [
                        {{
                            label: `${{label}} Acumulados`,
                            data: cumulative,
                            borderColor: CONFIG.colors[0],
                            backgroundColor: CONFIG.colors[0] + '20',
                            fill: true,
                            tension: 0.4
                        }},
                        {{
                            label: `${{label}} por Año`,
                            data: yearly,
                            borderColor: CONFIG.colors[1],
                            backgroundColor: CONFIG.colors[1] + '20',
                            fill: true,
                            tension: 0.4
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            display: true,
                            labels: {{ color: '#cdd6f4' }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        x: {{
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }}
                    }}
                }}
            }});
        }}

        function renderDiscoveries(container) {{
            const discoveries = dataCache[currentUser].discoveries;

            if (!discoveries) {{
                container.innerHTML = `
                    <div class="tab-content active">
                        <div class="error-message">
                            ℹ️ Datos de novedades no disponibles
                        </div>
                    </div>
                `;
                return;
            }}

            container.innerHTML = `
                <div class="tab-content active">
                    <div class="discoveries-grid">
                        <div class="chart-container">
                            <h3>✨ Nuevos Artistas</h3>
                            <canvas id="discoveriesArtistsChart"></canvas>
                        </div>
                        <div class="chart-container">
                            <h3>💿 Nuevos Álbumes</h3>
                            <canvas id="discoveriesAlbumsChart"></canvas>
                        </div>
                        <div class="chart-container">
                            <h3>🎵 Nuevas Canciones</h3>
                            <canvas id="discoveriesTracksChart"></canvas>
                        </div>
                        <div class="chart-container">
                            <h3>🏢 Nuevos Sellos</h3>
                            <canvas id="discoveriesLabelsChart"></canvas>
                        </div>
                    </div>
                </div>
            `;

            // Renderizar gráficos de discoveries
            const types = ['artists', 'albums', 'tracks', 'labels'];
            types.forEach(type => {{
                if (discoveries.discoveries && discoveries.discoveries[type]) {{
                    renderDiscoveriesChart(`discoveries${{type.charAt(0).toUpperCase() + type.slice(1)}}Chart`,
                                         discoveries.discoveries[type]);
                }}
            }});
        }}

        function renderDiscoveriesChart(canvasId, discoveriesData) {{
            const ctx = document.getElementById(canvasId);
            if (!ctx) return;

            const years = Object.keys(discoveriesData).filter(y => !isNaN(y)).sort();
            const counts = years.map(year => {{
                const yearData = discoveriesData[year];
                return typeof yearData === 'object' ? yearData.count : 0;
            }});

            if (charts[canvasId]) charts[canvasId].destroy();

            charts[canvasId] = new Chart(ctx, {{
                type: 'bar',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: 'Descubrimientos',
                        data: counts,
                        backgroundColor: CONFIG.colors[2],
                        borderColor: CONFIG.colors[2],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        x: {{
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }}
                    }},
                    onClick: (event, elements) => {{
                        if (elements.length > 0) {{
                            const index = elements[0].index;
                            const year = years[index];
                            showDiscoveryPopup(year, discoveriesData[year]);
                        }}
                    }}
                }}
            }});
        }}

        function showDiscoveryPopup(year, yearData) {{
            const overlay = document.getElementById('popupOverlay');
            const content = document.getElementById('popupContent');

            const items = yearData.items || [];
            const hasMore = yearData.has_more || false;

            let itemsHTML = items.map(item => `
                <div class="top-item">
                    <span class="item-name">${{item.name}}</span>
                    <span class="item-count">${{item.date}}</span>
                </div>
            `).join('');

            if (hasMore) {{
                itemsHTML += `<div class="top-item" style="text-align: center; color: #a6adc8;">
                    <span>... y ${{yearData.count - 10}} más</span>
                </div>`;
            }}

            content.innerHTML = `
                <div class="popup-header">
                    <h3>Descubrimientos de ${{year}}</h3>
                    <button class="popup-close" onclick="closePopup()">✕</button>
                </div>
                <div class="top-list">
                    ${{itemsHTML}}
                </div>
            `;

            overlay.classList.add('active');
        }}

        function closePopup() {{
            document.getElementById('popupOverlay').classList.remove('active');
        }}

        // Cerrar popup al hacer click fuera
        document.getElementById('popupOverlay').addEventListener('click', function(e) {{
            if (e.target === this) {{
                closePopup();
            }}
        }});
    </script>
</body>
</html>
"""

    return html_content


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='Generador optimizado de estadísticas de usuarios de Last.fm'
    )
    parser.add_argument(
        '--years-back',
        type=int,
        default=5,
        help='Número de años hacia atrás para analizar (por defecto: 5)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Archivo de salida HTML (por defecto: auto-generado con fecha)'
    )
    parser.add_argument(
        '--skip-data-generation',
        action='store_true',
        help='Omitir generación de archivos JSON (usar datos existentes)'
    )

    args = parser.parse_args()

    # Obtener usuarios
    users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
    if not users:
        print("❌ Variable LASTFM_USERS no configurada")
        print("Ejemplo: export LASTFM_USERS='usuario1,usuario2,usuario3'")
        sys.exit(1)

    # Auto-generar nombre de archivo si no se especifica
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/usuarios_{from_year}-{current_year}.html'

    output_dir = os.path.dirname(args.output) or 'docs'

    print("🎵 Generador Optimizado de Estadísticas de Usuarios")
    print("=" * 60)
    print(f"👥 Usuarios: {', '.join(users)}")
    print(f"📅 Años atrás: {args.years_back}")
    print(f"📁 Salida: {args.output}")

    try:
        # Paso 1: Generar archivos de datos JSON (si no se omite)
        if not args.skip_data_generation:
            data_info = generate_all_data_files(users, args.years_back, output_dir)
            data_info['users'] = users
        else:
            print("\n⏭️  Omitiendo generación de datos JSON (usando existentes)")
            current_year = datetime.now().year
            from_year = current_year - args.years_back
            period = f"{from_year}-{to_year}"

            data_info = {
                'users': users,
                'period': period,
                'discoveries_available': True  # Asumir que están disponibles
            }

        # Paso 2: Generar HTML optimizado
        print(f"\n🎨 Generando HTML optimizado...")
        html_content = generate_optimized_html(data_info, args.output)

        # Paso 3: Guardar HTML
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Calcular tamaños
        html_size = os.path.getsize(args.output) / 1024 / 1024  # MB

        # Calcular tamaño de JSONs
        json_dir = Path(output_dir) / "data" / "usuarios" / data_info['period']
        json_size = 0
        if json_dir.exists():
            for json_file in json_dir.glob("*.json"):
                json_size += os.path.getsize(json_file)
        json_size = json_size / 1024 / 1024  # MB

        print(f"\n✅ Generación completada!")
        print(f"📄 HTML: {args.output} ({html_size:.2f} MB)")
        print(f"📊 JSONs: {json_dir} ({json_size:.2f} MB)")
        print(f"💾 Total: {html_size + json_size:.2f} MB")

        print(f"\n✨ Características:")
        print(f"  ✅ HTML ligero (~{html_size:.1f}MB vs ~13MB anterior)")
        print(f"  ✅ Carga dinámica desde archivos JSON separados")
        print(f"  ✅ Navegación entre usuarios sin recargar")
        print(f"  ✅ Tabs interactivas con gráficos")
        print(f"  ✅ Pestaña de novedades con popups")
        print(f"  ✅ Mejor rendimiento y tiempo de carga")

        print(f"\n🚀 Para usar:")
        print(f"  1. Abre {args.output} en tu navegador")
        print(f"  2. Selecciona un usuario con los botones superiores")
        print(f"  3. Navega entre las diferentes pestañas")
        print(f"  4. Los datos se cargan automáticamente bajo demanda")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
