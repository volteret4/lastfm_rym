#!/usr/bin/env python3
"""
GroupStatsHTMLGenerator - Clase para generar HTML con gráficos interactivos de estadísticas grupales
VERSIÓN CORREGIDA - Fix para cambio de niveles de usuarios
"""

import json
from typing import Dict, List


class GroupStatsHTMLGenerator:
    """Clase para generar HTML con gráficos interactivos de estadísticas grupales"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, group_stats: Dict, years_back: int) -> str:
        """Genera el HTML completo para estadísticas grupales"""
        stats_json = json.dumps(group_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Grupo - Estadísticas Grupales</title>
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
            padding: 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        h1 {{
            font-size: 2em;
            color: #cba6f7;
            margin-bottom: 10px;
        }}

        .subtitle {{
            color: #a6adc8;
            font-size: 1em;
        }}

        .controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .control-group {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}

        label {{
            color: #cba6f7;
            font-weight: 600;
        }}

        .view-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .view-btn {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }}

        .view-btn:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .view-btn.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .group-header {{
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        .group-header h2 {{
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }}

        .group-info {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .stats-container {{
            padding: 30px;
        }}

        .view {{
            display: none;
        }}

        .view.active {{
            display: block;
        }}

        /* Estilos para la sección de datos */
        .data-section {{
            margin-bottom: 40px;
        }}

        .data-controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .data-control-group {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}

        .data-select {{
            padding: 8px 15px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
        }}

        .data-select:hover {{
            border-color: #cba6f7;
        }}

        .data-select:focus {{
            outline: none;
            border-color: #cba6f7;
            box-shadow: 0 0 0 3px rgba(203, 166, 247, 0.2);
        }}

        .data-categories {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .data-category-filter {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }}

        .data-category-filter:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .data-category-filter.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .data-display {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
            padding: 30px;
        }}

        .data-category {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
            display: none;
        }}

        .data-category.visible {{
            display: block;
        }}

        .data-category h4 {{
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #cba6f7;
        }}

        .data-item {{
            padding: 12px;
            margin-bottom: 10px;
            background: #181825;
            border-radius: 8px;
            border-left: 3px solid #45475a;
            transition: all 0.3s;
        }}

        .data-item:hover {{
            transform: translateX(5px);
            border-left-color: #cba6f7;
        }}

        .data-item.highlighted {{
            border-left-color: #cba6f7;
            background: #1e1e2e;
        }}

        .data-item-name {{
            color: #cdd6f4;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .data-item-meta {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            font-size: 0.9em;
        }}

        .data-badge {{
            padding: 4px 10px;
            background: #313244;
            color: #a6adc8;
            border-radius: 6px;
            font-size: 0.85em;
        }}

        .data-user-badge {{
            padding: 4px 10px;
            background: #45475a;
            color: #cdd6f4;
            border-radius: 6px;
            font-size: 0.85em;
        }}

        .data-user-badge.highlighted-user {{
            background: #cba6f7;
            color: #1e1e2e;
            font-weight: 600;
        }}

        .data-no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
            grid-column: 1 / -1;
        }}

        /* Resto de estilos... (charts, etc.) */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .chart-container h3 {{
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            text-align: center;
        }}

        .chart-wrapper {{
            position: relative;
            height: 300px;
            margin-bottom: 10px;
        }}

        .chart-info {{
            text-align: center;
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: #1e1e2e;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #313244;
            text-align: center;
        }}

        .summary-card .number {{
            font-size: 1.8em;
            font-weight: 600;
            color: #cba6f7;
            margin-bottom: 5px;
        }}

        .summary-card .label {{
            font-size: 0.9em;
            color: #a6adc8;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
        }}

        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .view-buttons {{
                justify-content: center;
            }}

            .summary-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .data-display {{
                grid-template-columns: 1fr;
                padding: 20px;
            }}

            .data-controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .data-categories {{
                justify-content: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 Estadísticas Grupales</h1>
            <p class="subtitle">Análisis global del grupo</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="data">Datos</button>
                    <button class="view-btn" data-view="shared">Por Usuarios Compartidos</button>
                    <button class="view-btn" data-view="scrobbles">Por Scrobbles Totales</button>
                    <button class="view-btn" data-view="evolution">Evolución Temporal</button>
                </div>
            </div>
        </div>

        <div id="groupHeader" class="group-header">
            <h2 id="groupTitle">Análisis Grupal</h2>
            <p class="group-info" id="groupInfo">Período de análisis: {years_back + 1} años</p>
        </div>

        <div class="stats-container">
            <!-- Resumen de estadísticas -->
            <div id="summaryStats" class="summary-stats">
                <!-- Se llenará dinámicamente -->
            </div>

            <!-- Vista de Datos -->
            <div id="dataView" class="view active">
                <div class="data-section">
                    <div class="data-controls">
                        <div class="data-control-group">
                            <label for="userLevelSelect">Nivel de coincidencia:</label>
                            <select id="userLevelSelect" class="data-select">
                                <!-- Se llenará dinámicamente -->
                            </select>
                        </div>

                        <div class="data-control-group">
                            <label for="highlightUserSelect">Destacar usuario:</label>
                            <select id="highlightUserSelect" class="data-select">
                                <option value="">Ninguno</option>
                                <!-- Se llenará dinámicamente -->
                            </select>
                        </div>

                        <div class="data-control-group">
                            <label>Mostrar categorías:</label>
                            <div class="data-categories">
                                <button class="data-category-filter active" data-category="artists">Artistas</button>
                                <button class="data-category-filter" data-category="albums">Álbumes</button>
                                <button class="data-category-filter" data-category="tracks">Canciones</button>
                                <button class="data-category-filter" data-category="genres">Géneros</button>
                                <button class="data-category-filter" data-category="labels">Sellos</button>
                                <button class="data-category-filter" data-category="decades">Décadas</button>
                            </div>
                        </div>
                    </div>

                    <div class="data-display" id="dataDisplay">
                        <!-- Se llenará dinámicamente -->
                    </div>
                </div>
            </div>

            <!-- Vista Por Usuarios Compartidos -->
            <div id="sharedView" class="view">
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>🎤 Top 15 Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedArtistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedArtistsInfo"></div>
                    </div>
                    <!-- Más gráficos aquí... -->
                </div>
            </div>

            <!-- Vista Por Scrobbles Totales -->
            <div id="scribblesView" class="view">
                <!-- Contenido similar -->
            </div>

            <!-- Vista de Evolución -->
            <div id="evolutionView" class="view">
                <!-- Contenido similar -->
            </div>
        </div>
    </div>

    <script>
        const groupStats = {stats_json};
        const colors = {colors_json};

        let currentView = 'data';
        let charts = {{}};

        // Variables para la sección de datos
        let activeDataCategories = new Set(['artists']); // Por defecto mostrar artistas
        let currentUserLevel = '';
        let selectedHighlightUser = '';

        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {{
            updateGroupHeader();
            updateSummaryStats();

            // Manejar botones de vista
            const viewButtons = document.querySelectorAll('.view-btn');
            viewButtons.forEach(btn => {{
                btn.addEventListener('click', function() {{
                    const view = this.dataset.view;
                    switchView(view);
                }});
            }});

            // Inicializar controles de datos
            initializeDataControls();

            // Cargar vista inicial
            switchView('data');
        }});

        function switchView(view) {{
            currentView = view;

            // Update buttons
            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-view="${{view}}"]`).classList.add('active');

            // Update views
            document.querySelectorAll('.view').forEach(v => {{
                v.classList.remove('active');
            }});

            if (view === 'scrobbles') {{
                document.getElementById('scribblesView').classList.add('active');
            }} else {{
                document.getElementById(view + 'View').classList.add('active');
            }}

            // Render appropriate charts
            if (view === 'data') {{
                renderDataView();
            }} else if (view === 'shared') {{
                renderSharedCharts();
            }} else if (view === 'scrobbles') {{
                renderScrobblesCharts();
            }} else if (view === 'evolution') {{
                renderEvolutionCharts();
            }}
        }}

        function updateGroupHeader() {{
            const users = groupStats.users.join(', ');
            document.getElementById('groupTitle').textContent = `Grupo: ${{users}}`;
            document.getElementById('groupInfo').innerHTML =
                `Período: ${{groupStats.period}} | ${{groupStats.user_count}} usuarios | Generado: ${{groupStats.generated_at}}`;
        }}

        function updateSummaryStats() {{
            // Usar los totales reales de elementos compartidos por TODOS los usuarios
            const totalCounts = groupStats.total_counts || {{}};

            const summaryHTML = `
                <div class="summary-card">
                    <div class="number">${{groupStats.user_count}}</div>
                    <div class="label">Usuarios</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalCounts.shared_artists || 0}}</div>
                    <div class="label">Artistas Compartidos (Todos)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalCounts.shared_albums || 0}}</div>
                    <div class="label">Álbumes Compartidos</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalCounts.shared_tracks || 0}}</div>
                    <div class="label">Canciones Compartidas (Todos)</div>
                </div>
            `;

            document.getElementById('summaryStats').innerHTML = summaryHTML;
        }}

        // Funciones para la sección de datos
        function initializeDataControls() {{
            console.log('Inicializando controles de datos...'); // Debug
            console.log('Datos disponibles:', groupStats.data_by_levels); // Debug

            const userLevelSelect = document.getElementById('userLevelSelect');
            const highlightUserSelect = document.getElementById('highlightUserSelect');

            // Llenar select de niveles de usuarios
            if (groupStats.data_by_levels) {{
                const levels = Object.keys(groupStats.data_by_levels);
                console.log('Niveles encontrados:', levels); // Debug

                levels.forEach((levelKey, index) => {{
                    const option = document.createElement('option');
                    option.value = levelKey;
                    option.textContent = getLevelLabel(levelKey);
                    userLevelSelect.appendChild(option);

                    if (index === 0) {{
                        currentUserLevel = levelKey;
                        option.selected = true;
                        console.log('Nivel inicial establecido:', currentUserLevel); // Debug
                    }}
                }});
            }} else {{
                console.error('No se encontraron data_by_levels en groupStats'); // Debug
            }}

            // Llenar select de usuarios para destacar
            groupStats.users.forEach(user => {{
                const option = document.createElement('option');
                option.value = user;
                option.textContent = user;
                highlightUserSelect.appendChild(option);
            }});

            // Event listeners
            userLevelSelect.addEventListener('change', function() {{
                currentUserLevel = this.value;
                console.log('Cambiando a nivel:', currentUserLevel); // Debug
                renderDataView();
            }});

            highlightUserSelect.addEventListener('change', function() {{
                selectedHighlightUser = this.value;
                console.log('Destacando usuario:', selectedHighlightUser); // Debug
                renderDataView();
            }});

            // Manejar filtros de categorías
            const dataCategoryFilters = document.querySelectorAll('.data-category-filter');
            dataCategoryFilters.forEach(filter => {{
                filter.addEventListener('click', () => {{
                    const category = filter.dataset.category;

                    if (activeDataCategories.has(category)) {{
                        activeDataCategories.delete(category);
                        filter.classList.remove('active');
                    }} else {{
                        activeDataCategories.add(category);
                        filter.classList.add('active');
                    }}

                    renderDataView();
                }});
            }});

            // Renderizar vista inicial después de configurar todo
            setTimeout(() => {{
                console.log('Renderizando vista inicial...'); // Debug
                renderDataView();
            }}, 100);
        }}

        function getLevelLabel(levelKey) {{
            const totalUsers = groupStats.user_count;
            if (levelKey === 'total_usuarios') {{
                return `Total de usuarios (${{totalUsers}})`;
            }} else {{
                const missing = parseInt(levelKey.replace('total_menos_', ''));
                const remaining = totalUsers - missing;
                return `Total menos ${{missing}} (${{remaining}} usuarios)`;
            }}
        }}

        function renderDataView() {{
            console.log('Renderizando vista con nivel:', currentUserLevel); // Debug
            const dataDisplay = document.getElementById('dataDisplay');
            dataDisplay.innerHTML = '';

            if (!currentUserLevel || !groupStats.data_by_levels || !groupStats.data_by_levels[currentUserLevel]) {{
                console.log('No hay datos para el nivel:', currentUserLevel); // Debug
                console.log('Niveles disponibles:', Object.keys(groupStats.data_by_levels || {{}})); // Debug
                dataDisplay.innerHTML = '<div class="data-no-data">No hay datos disponibles</div>';
                return;
            }}

            const levelData = groupStats.data_by_levels[currentUserLevel];
            console.log('Datos del nivel:', levelData); // Debug
            const categoryOrder = ['artists', 'albums', 'tracks', 'genres', 'labels', 'decades'];
            const categoryTitles = {{
                artists: 'Artistas',
                albums: 'Álbumes',
                tracks: 'Canciones',
                genres: 'Géneros',
                labels: 'Sellos',
                decades: 'Décadas'
            }};

            let hasVisibleData = false;

            categoryOrder.forEach(categoryKey => {{
                if (!activeDataCategories.has(categoryKey)) return;
                if (!levelData[categoryKey] || levelData[categoryKey].length === 0) return;

                hasVisibleData = true;

                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'data-category visible';

                const title = document.createElement('h4');
                title.textContent = `${{categoryTitles[categoryKey]}} (${{levelData[categoryKey].length}})`;
                categoryDiv.appendChild(title);

                levelData[categoryKey].forEach(item => {{
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'data-item';

                    // Destacar si el usuario seleccionado está en la lista
                    if (selectedHighlightUser && item.users.includes(selectedHighlightUser)) {{
                        itemDiv.classList.add('highlighted');
                    }}

                    const itemName = document.createElement('div');
                    itemName.className = 'data-item-name';
                    itemName.textContent = item.name;
                    itemDiv.appendChild(itemName);

                    const itemMeta = document.createElement('div');
                    itemMeta.className = 'data-item-meta';

                    // Badge con total de scrobbles
                    const countBadge = document.createElement('span');
                    countBadge.className = 'data-badge';
                    countBadge.textContent = `${{item.count.toLocaleString()}} plays`;
                    itemMeta.appendChild(countBadge);

                    // Badges de usuarios
                    item.users.forEach(user => {{
                        const userBadge = document.createElement('span');
                        userBadge.className = 'data-user-badge';
                        if (user === selectedHighlightUser) {{
                            userBadge.classList.add('highlighted-user');
                        }}

                        const userPlays = item.user_counts[user] || 0;
                        userBadge.textContent = `${{user}} (${{userPlays.toLocaleString()}})`;
                        itemMeta.appendChild(userBadge);
                    }});

                    itemDiv.appendChild(itemMeta);
                    categoryDiv.appendChild(itemDiv);
                }});

                dataDisplay.appendChild(categoryDiv);
            }});

            if (!hasVisibleData) {{
                dataDisplay.innerHTML = activeDataCategories.size === 0
                    ? '<div class="data-no-data">Selecciona al menos una categoría para ver los datos</div>'
                    : '<div class="data-no-data">No hay datos disponibles para este nivel</div>';
            }}
        }}

        // Funciones vacías para las otras vistas (para evitar errores)
        function renderSharedCharts() {{
            console.log('Renderizando gráficos compartidos...');
        }}

        function renderScrobblesCharts() {{
            console.log('Renderizando gráficos por scrobbles...');
        }}

        function renderEvolutionCharts() {{
            console.log('Renderizando gráficos de evolución...');
        }}
    </script>
</body>
</html>"""

    def _format_number(self, number: int) -> str:
        """Formatea números con separadores de miles"""
        return f"{number:,}".replace(",", ".")
