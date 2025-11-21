#!/usr/bin/env python3
"""
UserStatsHTMLGeneratorOptimized - Versión optimizada que carga datos de novedades desde archivos JSON
"""

import json
import os
from typing import Dict, List
from datetime import datetime


class UserStatsHTMLGeneratorOptimized:
    """Generador HTML optimizado que carga datos de novedades dinámicamente"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera el HTML optimizado para estadísticas de usuarios"""

        # Remover datos de novedades del JSON principal para reducir tamaño
        optimized_stats = self._remove_discoveries_from_stats(all_user_stats)

        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(optimized_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        # Configurar iconos de usuario
        icons_env = os.getenv('LASTFM_USERS_ICONS', '')
        user_icons = {}
        if icons_env:
            for pair in icons_env.split(','):
                if ':' in pair:
                    user, icon = pair.split(':', 1)
                    user_icons[user.strip()] = icon.strip()
        user_icons_json = json.dumps(user_icons, ensure_ascii=False)

        # Configurar periodo para carga de datos de novedades
        current_year = datetime.now().year
        from_year = current_year - years_back
        to_year = current_year
        period = f"{from_year}-{to_year}"

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - Estadísticas Individuales (Optimizado)</title>
    <link rel="icon" type="image/png" href="images/music.png">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        /* Mismo CSS que antes pero agregando estilos para loading */
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

        .nav-buttons {{
            display: flex;
            gap: 15px;
            margin-top: 10px;
        }}

        .nav-button {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }}

        .nav-button:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .nav-button.current {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .user-button {{
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #cba6f7;
            color: #1e1e2e;
            border: none;
            cursor: pointer;
            font-size: 1.2em;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
        }}

        .user-button:hover {{
            background: #b4a3e8;
            transform: scale(1.1);
        }}

        .content {{
            padding: 30px;
        }}

        .nav-tabs {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            border-bottom: 2px solid #313244;
            padding-bottom: 15px;
            flex-wrap: wrap;
        }}

        .nav-tab {{
            padding: 12px 20px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
            position: relative;
        }}

        .nav-tab:hover {{
            background: #45475a;
            border-color: #cba6f7;
        }}

        .nav-tab.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
            border-bottom-color: #181825;
        }}

        .tab-content {{
            display: none;
        }}

        .tab-content.active {{
            display: block;
        }}

        .evolution-section {{
            margin-bottom: 40px;
        }}

        .evolution-section h3 {{
            color: #cba6f7;
            font-size: 1.3em;
            margin-bottom: 20px;
            border-bottom: 2px solid #cba6f7;
            padding-bottom: 10px;
        }}

        .evolution-charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 25px;
        }}

        .evolution-chart {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .evolution-chart h4 {{
            color: #cba6f7;
            font-size: 1.1em;
            margin-bottom: 15px;
            text-align: center;
        }}

        .line-chart-wrapper {{
            position: relative;
            height: 400px;
        }}

        .loading-spinner {{
            display: none;
            text-align: center;
            padding: 40px;
            color: #a6adc8;
        }}

        .loading-spinner.active {{
            display: block;
        }}

        .discoveries-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }}

        .no-data {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 200px;
            background: #313244;
            border-radius: 8px;
            color: #a6adc8;
            font-style: italic;
        }}

        @media (max-width: 768px) {{
            .discoveries-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>🎵 RYM Hispano Estadísticas (Optimizado)</h1>
                <div class="nav-buttons">
                    <a href="index.html#temporal" class="nav-button">TEMPORALES</a>
                    <a href="index.html#grupo" class="nav-button">GRUPO</a>
                    <a href="index.html#about" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">👤</button>
        </header>

        <div class="content">
            <div class="nav-tabs">
                <div class="nav-tab active" data-view="individual">📊 Individual</div>
                <div class="nav-tab" data-view="discoveries">✨ Novedades</div>
                <div class="nav-tab" data-view="genres">🎵 Géneros</div>
                <div class="nav-tab" data-view="labels">💿 Sellos</div>
                <div class="nav-tab" data-view="coincidences">🤝 Coincidencias</div>
                <div class="nav-tab" data-view="evolution">📈 Evolución</div>
            </div>

            <div id="individualTab" class="tab-content active">
                <p>Contenido de estadísticas individuales (original)...</p>
            </div>

            <!-- Nueva pestaña de Novedades -->
            <div id="discoveriesTab" class="tab-content">
                <div class="evolution-section">
                    <h3>✨ Descubrimientos Musicales</h3>

                    <div class="loading-spinner" id="discoveriesLoading">
                        <p>🔄 Cargando datos de novedades...</p>
                    </div>

                    <div class="discoveries-grid" id="discoveriesGrid" style="display: none;">
                        <div class="evolution-chart">
                            <h4>Nuevos Artistas por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesArtistsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Nuevos Álbumes por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesAlbumsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Nuevas Canciones por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesTracksChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Nuevos Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesLabelsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Resto de pestañas existentes -->
            <div id="genresTab" class="tab-content">
                <p>Contenido de géneros (original)...</p>
            </div>

            <div id="labelsTab" class="tab-content">
                <p>Contenido de sellos (original)...</p>
            </div>

            <div id="coincidencesTab" class="tab-content">
                <p>Contenido de coincidencias (original)...</p>
            </div>

            <div id="evolutionTab" class="tab-content">
                <p>Contenido de evolución (original)...</p>
            </div>
        </div>
    </div>

    <script>
        // Configuración global
        const allUsers = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};
        const userIcons = {user_icons_json};
        const dataPeriod = '{period}';

        // Variables globales
        let currentUser = null;
        let currentView = 'individual';
        let charts = {{}};
        let discoveriesData = {{}}; // Cache para datos de novedades

        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {{
            initializeApp();
        }});

        function initializeApp() {{
            setupNavigation();

            // Seleccionar primer usuario por defecto
            if (allUsers.length > 0) {{
                selectUser(allUsers[0]);
            }}
        }}

        function setupNavigation() {{
            const navTabs = document.querySelectorAll('.nav-tab');
            const tabContents = document.querySelectorAll('.tab-content');

            navTabs.forEach(tab => {{
                tab.addEventListener('click', () => {{
                    const view = tab.dataset.view;

                    // Actualizar pestañas activas
                    navTabs.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');

                    // Mostrar contenido correspondiente
                    tabContents.forEach(content => {{
                        content.classList.remove('active');
                    }});

                    document.getElementById(view + 'Tab').classList.add('active');
                    currentView = view;

                    // Cargar datos específicos de la vista
                    if (currentUser && view === 'discoveries') {{
                        loadDiscoveriesData(currentUser);
                    }}
                }});
            }});
        }}

        function selectUser(username) {{
            currentUser = username;
            console.log(`Usuario seleccionado: ${{username}}`);

            // Si estamos en la vista de novedades, cargar datos
            if (currentView === 'discoveries') {{
                loadDiscoveriesData(username);
            }}
        }}

        async function loadDiscoveriesData(username) {{
            console.log(`Cargando datos de novedades para ${{username}}...`);

            // Mostrar loading
            document.getElementById('discoveriesLoading').classList.add('active');
            document.getElementById('discoveriesGrid').style.display = 'none';

            try {{
                // Verificar cache
                if (discoveriesData[username]) {{
                    console.log('Usando datos del cache');
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }}

                // Cargar desde archivo JSON
                const dataUrl = `data/usuarios/${{dataPeriod}}/${{username}}.json`;
                console.log(`Cargando desde: ${{dataUrl}}`);

                const response = await fetch(dataUrl);

                if (!response.ok) {{
                    throw new Error(`Error HTTP: ${{response.status}}`);
                }}

                const userData = await response.json();

                // Guardar en cache
                discoveriesData[username] = userData;

                // Renderizar gráficos
                renderDiscoveriesCharts(userData);

            }} catch (error) {{
                console.error('Error cargando datos de novedades:', error);
                showDiscoveriesError(error.message);
            }}
        }}

        function renderDiscoveriesCharts(userData) {{
            console.log('Renderizando gráficos de novedades...', userData);

            // Ocultar loading
            document.getElementById('discoveriesLoading').classList.remove('active');
            document.getElementById('discoveriesGrid').style.display = 'grid';

            // Destruir gráficos existentes
            Object.values(charts).forEach(chart => {{
                if (chart && typeof chart.destroy === 'function') {{
                    chart.destroy();
                }}
            }});

            // Renderizar cada tipo de gráfico
            const discoveryTypes = ['artists', 'albums', 'tracks', 'labels'];

            discoveryTypes.forEach(type => {{
                const canvasId = `discoveries${{type.charAt(0).toUpperCase() + type.slice(1)}}Chart`;
                const typeData = userData.discoveries[type];

                if (typeData) {{
                    renderDiscoveryChart(canvasId, typeData, type);
                }} else {{
                    showNoDataForChart(canvasId);
                }}
            }});
        }}

        function renderDiscoveryChart(canvasId, typeData, typeName) {{
            const canvas = document.getElementById(canvasId);

            if (!canvas) {{
                console.error(`Canvas ${{canvasId}} no encontrado`);
                return;
            }}

            // Preparar datos para el gráfico
            const years = [];
            const counts = [];
            const details = {{}};

            // Ordenar años y extraer conteos
            const sortedYears = Object.keys(typeData).sort((a, b) => parseInt(a) - parseInt(b));

            sortedYears.forEach(year => {{
                if (!isNaN(year)) {{
                    years.push(parseInt(year));
                    counts.push(typeData[year].count || 0);
                    details[year] = typeData[year].items || [];
                }}
            }});

            if (years.length === 0) {{
                showNoDataForChart(canvasId);
                return;
            }}

            const config = {{
                type: 'line',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: `Nuevos ${{typeName}}`,
                        data: counts,
                        borderColor: '#cba6f7',
                        backgroundColor: '#cba6f7' + '30',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#cba6f7',
                        pointBorderColor: '#1e1e2e',
                        pointBorderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 15,
                                font: {{ size: 12 }}
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            title: {{
                                display: true,
                                text: 'Año',
                                color: '#cdd6f4'
                            }},
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: 'Número de Novedades',
                                color: '#cdd6f4'
                            }},
                            ticks: {{
                                color: '#a6adc8',
                                precision: 0
                            }},
                            grid: {{ color: '#313244' }},
                            beginAtZero: true
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const pointIndex = elements[0].index;
                            const year = this.data.labels[pointIndex];
                            const count = this.data.datasets[0].data[pointIndex];

                            if (count > 0 && details[year]) {{
                                showDiscoveryDetails(year, details[year], typeName, count);
                            }}
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showDiscoveryDetails(year, items, typeName, count) {{
            const title = `${{typeName.toUpperCase()}} - ${{year}} (${{count}} nuevos)`;

            let content = '<div style="max-height: 300px; overflow-y: auto;">';
            items.slice(0, 30).forEach(item => {{
                content += `<div style="padding: 8px; margin: 4px 0; background: #313244; border-radius: 6px; display: flex; justify-content: space-between;">
                    <span style="color: #cdd6f4; font-weight: 600;">${{item.name}}</span>
                    <span style="color: #a6adc8; font-size: 0.9em;">${{item.date}}</span>
                </div>`;
            }});

            if (count > 30) {{
                content += `<div style="text-align: center; padding: 10px; color: #a6adc8; font-style: italic;">
                    ... y ${{count - 30}} más
                </div>`;
            }}
            content += '</div>';

            // Mostrar en un alert simple por ahora (se puede mejorar con modal)
            alert(`${{title}}\\n\\nPrimeros elementos mostrados en consola.`);
            console.log(title, items);
        }}

        function showDiscoveriesError(errorMessage) {{
            document.getElementById('discoveriesLoading').classList.remove('active');
            document.getElementById('discoveriesGrid').innerHTML = `
                <div class="no-data">
                    <div>
                        <p>❌ Error cargando datos de novedades</p>
                        <p style="font-size: 0.9em; margin-top: 10px;">${{errorMessage}}</p>
                        <p style="font-size: 0.8em; margin-top: 10px; color: #6c7086;">
                            Ejecuta: python generate_discoveries_data.py
                        </p>
                    </div>
                </div>
            `;
        }}

        function showNoDataForChart(canvasId) {{
            const canvas = document.getElementById(canvasId);
            if (canvas) {{
                canvas.style.display = 'none';
                canvas.parentElement.innerHTML = '<div class="no-data">Sin datos de novedades</div>';
            }}
        }}

        // Función simple para seleccionar usuario (para pruebas)
        function selectUserFromList() {{
            const user = prompt(`Selecciona usuario (${{allUsers.join(', ')}}):`, allUsers[0]);
            if (user && allUsers.includes(user)) {{
                selectUser(user);
            }}
        }}

        // Event listener para botón de usuario
        document.getElementById('userButton').addEventListener('click', selectUserFromList);

    </script>
</body>
</html>"""

    def _remove_discoveries_from_stats(self, all_user_stats: Dict) -> Dict:
        """Remueve datos de novedades del JSON principal para optimizar"""
        optimized_stats = {}

        for user, stats in all_user_stats.items():
            user_copy = dict(stats)

            # Remover datos de novedades si existen
            if 'individual' in user_copy and 'discoveries' in user_copy['individual']:
                del user_copy['individual']['discoveries']

            optimized_stats[user] = user_copy

        return optimized_stats

    def _format_number(self, number: int) -> str:
        """Formatea números con separadores de miles"""
        return f"{number:,}".replace(",", ".")
