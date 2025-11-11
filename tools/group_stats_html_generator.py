#!/usr/bin/env python3
"""
GroupStatsHTMLGenerator - Clase para generar HTML con grÃ¡ficos interactivos de estadÃ­sticas grupales
"""

import json
from typing import Dict, List


class GroupStatsHTMLGenerator:
    """Clase para generar HTML con grÃ¡ficos interactivos de estadÃ­sticas grupales"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, group_stats: Dict, years_back: int) -> str:
        """Genera el HTML completo para estadÃ­sticas grupales"""
        stats_json = json.dumps(group_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Grupo - EstadÃ­sticas Grupales</title>
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

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
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

        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 999;
        }}

        .popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border: 2px solid #cba6f7;
            border-radius: 12px;
            padding: 20px;
            max-width: 500px;
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }}

        .popup-header {{
            color: #cba6f7;
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 1px solid #313244;
            padding-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .popup-close {{
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.2em;
            cursor: pointer;
            padding: 0;
        }}

        .popup-close:hover {{
            color: #cba6f7;
        }}

        .popup-content {{
            max-height: 300px;
            overflow-y: auto;
        }}

        .popup-item {{
            padding: 8px 12px;
            background: #181825;
            margin-bottom: 5px;
            border-radius: 6px;
            border-left: 3px solid #45475a;
        }}

        .popup-item .name {{
            color: #cdd6f4;
            font-weight: 600;
            margin-bottom: 5px;
        }}

        .popup-item .details {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .popup-item .users {{
            color: #6c7086;
            font-size: 0.85em;
            margin-top: 5px;
        }}

        @media (max-width: 768px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            .evolution-charts {{
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
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>ðŸ‘¥ EstadÃ­sticas Grupales</h1>
            <p class="subtitle">AnÃ¡lisis global del grupo</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="shared">Por Usuarios Compartidos</button>
                    <button class="view-btn" data-view="scrobbles">Por Scrobbles Totales</button>
                    <button class="view-btn" data-view="evolution">EvoluciÃ³n Temporal</button>
                </div>
            </div>
        </div>

        <div id="groupHeader" class="group-header">
            <h2 id="groupTitle">AnÃ¡lisis Grupal</h2>
            <p class="group-info" id="groupInfo">PerÃ­odo de anÃ¡lisis: {years_back + 1} aÃ±os</p>
        </div>

        <div class="stats-container">
            <!-- Resumen de estadÃ­sticas -->
            <div id="summaryStats" class="summary-stats">
                <!-- Se llenarÃ¡ dinÃ¡micamente -->
            </div>

            <!-- Vista Por Usuarios Compartidos -->
            <div id="sharedView" class="view active">
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>ðŸŽ¤ Top 15 Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedArtistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedArtistsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸ’¿ Top 15 Ãlbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedAlbumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedAlbumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸŽµ Top 15 Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedTracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedTracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸŽ­ Top 15 GÃ©neros</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedGenresChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedGenresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸ·ï¸ Top 15 Sellos</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedLabelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedLabelsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸ“… Top 15 AÃ±os de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedReleaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedReleaseYearsInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista Por Scrobbles Totales -->
            <div id="scribblesView" class="view">
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>ðŸŽ¤ Top 15 Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesArtistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesArtistsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸ’¿ Top 15 Ãlbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesAlbumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesAlbumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸŽµ Top 15 Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesTracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesTracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸŽ­ Top 15 GÃ©neros</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesGenresChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesGenresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸ·ï¸ Top 15 Sellos</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesLabelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesLabelsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸ“… Top 15 AÃ±os de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesReleaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesReleaseYearsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>ðŸŒŸ Top 15 Global</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesAllCombinedChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesAllCombinedInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de EvoluciÃ³n -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>ðŸ“ˆ EvoluciÃ³n Temporal por Scrobbles</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>ðŸŽ¤ Top 15 Artistas por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionArtistsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>ðŸ’¿ Top 15 Ãlbumes por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionAlbumsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>ðŸŽµ Top 15 Canciones por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionTracksChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>ðŸŽ­ Top 15 GÃ©neros por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionGenresChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>ðŸ·ï¸ Top 15 Sellos por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionLabelsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>ðŸ“… Top 15 AÃ±os de Lanzamiento por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionReleaseYearsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Popup para mostrar detalles -->
            <div id="popupOverlay" class="popup-overlay" style="display: none;"></div>
            <div id="popup" class="popup" style="display: none;">
                <div class="popup-header">
                    <span id="popupTitle">Detalles</span>
                    <button id="popupClose" class="popup-close">âœ•</button>
                </div>
                <div id="popupContent" class="popup-content"></div>
            </div>
        </div>
    </div>

    <script>
        const groupStats = {stats_json};
        const colors = {colors_json};

        let currentView = 'shared';
        let charts = {{}};

        // InicializaciÃ³n
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

            // Cargar vista inicial
            switchView('shared');
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
            if (view === 'shared') {{
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
                `PerÃ­odo: ${{groupStats.period}} | ${{groupStats.user_count}} usuarios | Generado: ${{groupStats.generated_at}}`;
        }}

        function updateSummaryStats() {{
            // Usar los totales reales de elementos compartidos por TODOS los usuarios
            const totalCounts = groupStats.total_counts || {{}};
            const scrobblesCharts = groupStats.scrobbles_charts;

            const totalSharedArtists = totalCounts.shared_artists || 0;
            const totalSharedAlbums = totalCounts.shared_albums || 0;
            const totalSharedTracks = totalCounts.shared_tracks || 0;
            const totalSharedGenres = totalCounts.shared_genres || 0;
            const totalSharedLabels = totalCounts.shared_labels || 0;
            const totalSharedReleaseYears = totalCounts.shared_release_years || 0;

            const totalScrobblesArtists = scrobblesCharts.artists.total || 0;
            const totalScrobblesAll = scrobblesCharts.all_combined.total || 0;

            const summaryHTML = `
                <div class="summary-card">
                    <div class="number">${{groupStats.user_count}}</div>
                    <div class="label">Usuarios</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedArtists}}</div>
                    <div class="label">Artistas Compartidos (Todos)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedAlbums}}</div>
                    <div class="label">Ãlbumes Compartidos</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedTracks}}</div>
                    <div class="label">Canciones Compartidas (Todos)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedGenres}}</div>
                    <div class="label">Géneros Compartidos (Todos)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedLabels}}</div>
                    <div class="label">Sellos Compartidos (Todos)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalScrobblesArtists.toLocaleString()}}</div>
                    <div class="label">Scrobbles (Artistas)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalScrobblesAll.toLocaleString()}}</div>
                    <div class="label">Scrobbles (Total)</div>
                </div>
            `;

            document.getElementById('summaryStats').innerHTML = summaryHTML;
        }}

        function renderSharedCharts() {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar grÃ¡ficos por usuarios compartidos
            renderPieChart('sharedArtistsChart', groupStats.shared_charts.artists, 'sharedArtistsInfo');
            renderPieChart('sharedAlbumsChart', groupStats.shared_charts.albums, 'sharedAlbumsInfo');
            renderPieChart('sharedTracksChart', groupStats.shared_charts.tracks, 'sharedTracksInfo');
            renderPieChart('sharedGenresChart', groupStats.shared_charts.genres, 'sharedGenresInfo');
            renderPieChart('sharedLabelsChart', groupStats.shared_charts.labels, 'sharedLabelsInfo');
            renderPieChart('sharedReleaseYearsChart', groupStats.shared_charts.release_years, 'sharedReleaseYearsInfo');
        }}

        function renderScrobblesCharts() {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar grÃ¡ficos por scrobbles totales
            renderPieChart('scrobblesArtistsChart', groupStats.scrobbles_charts.artists, 'scrobblesArtistsInfo');
            renderPieChart('scrobblesAlbumsChart', groupStats.scrobbles_charts.albums, 'scrobblesAlbumsInfo');
            renderPieChart('scrobblesTracksChart', groupStats.scrobbles_charts.tracks, 'scrobblesTracksInfo');
            renderPieChart('scrobblesGenresChart', groupStats.scrobbles_charts.genres, 'scrobblesGenresInfo');
            renderPieChart('scrobblesLabelsChart', groupStats.scrobbles_charts.labels, 'scrobblesLabelsInfo');
            renderPieChart('scrobblesReleaseYearsChart', groupStats.scrobbles_charts.release_years, 'scrobblesReleaseYearsInfo');
            renderPieChart('scrobblesAllCombinedChart', groupStats.scrobbles_charts.all_combined, 'scrobblesAllCombinedInfo');
        }}

        function renderEvolutionCharts() {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar grÃ¡ficos de evoluciÃ³n
            renderLineChart('evolutionArtistsChart', groupStats.evolution.artists);
            renderLineChart('evolutionAlbumsChart', groupStats.evolution.albums);
            renderLineChart('evolutionTracksChart', groupStats.evolution.tracks);
            renderLineChart('evolutionGenresChart', groupStats.evolution.genres);
            renderLineChart('evolutionLabelsChart', groupStats.evolution.labels);
            renderLineChart('evolutionReleaseYearsChart', groupStats.evolution.release_years);
        }}

        function renderPieChart(canvasId, chartData, infoId) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';
            const unit = chartData.type === 'shared' ? 'usuarios' : 'scrobbles';
            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}} ${{unit}} | Click para detalles`;

            const data = {{
                labels: Object.keys(chartData.data),
                datasets: [{{
                    data: Object.values(chartData.data),
                    backgroundColor: colors.slice(0, Object.keys(chartData.data).length),
                    borderColor: '#181825',
                    borderWidth: 2
                }}]
            }};

            const config = {{
                type: 'pie',
                data: data,
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 15,
                                usePointStyle: true
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
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const index = elements[0].index;
                            const label = data.labels[index];
                            showGroupPopup(chartData, label);
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function renderLineChart(canvasId, chartData) {{
            const canvas = document.getElementById(canvasId);

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            Object.keys(chartData.data).forEach(item => {{
                datasets.push({{
                    label: item,
                    data: chartData.years.map(year => {{
                        const yearData = chartData.data[item][year];
                        if (yearData !== undefined && yearData !== null) {{
                            // Si es la nueva estructura con objetos total: X, users:
                            if (typeof yearData === 'object' && 'total' in yearData) {{
                                return yearData.total;
                            }}
                            // Si es la estructura antigua con números directos
                            if (typeof yearData === 'number') {{
                                return yearData;
                            }}
                        }}
                        return 0;
                    }}),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false,
                    userData: chartData.data[item] // Guardar datos de usuario para tooltips
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: chartData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1,
                            callbacks: {{
                                afterBody: function(context) {{
                                    const datasetIndex = context[0].datasetIndex;
                                    const dataset = datasets[datasetIndex];
                                    const year = chartData.years[context[0].dataIndex];
                                    const userData = dataset.userData[year];

                                    // Solo mostrar desglose si es la nueva estructura con datos de usuario
                                    if (userData && typeof userData === 'object' && userData.users && Object.keys(userData.users).length > 0) {{
                                        const userList = Object.entries(userData.users)
                                            .sort((a, b) => b[1] - a[1])
                                            .map(([user, plays]) => `${{user}}: ${{plays}}`)
                                            .join('\\n');
                                        return '\\nDesglose por usuario:\\n' + userList;
                                    }}
                                    return '';
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const dataset = datasets[datasetIndex];
                            const year = chartData.years[pointIndex];
                            const userData = dataset.userData[year];

                            // Solo mostrar popup si es la nueva estructura con datos de usuario
                            if (userData && typeof userData === 'object' && userData.users && Object.keys(userData.users).length > 0) {{
                                showEvolutionPopup(dataset.label, year, userData);
                            }}
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showGroupPopup(chartData, selectedLabel) {{
            const details = chartData.details[selectedLabel];
            if (!details) return;

            let title = `${{selectedLabel}}`;
            let content = '';

            content += `<div class="popup-item">
                <div class="name">${{selectedLabel}}</div>
                <div class="details">
                    Usuarios: ${{details.user_count}} |
                    Scrobbles: ${{details.total_scrobbles.toLocaleString()}}
                </div>`;

            if (details.shared_users && details.shared_users.length > 0) {{
                content += `<div class="users">Compartido por: ${{details.shared_users.join(', ')}}</div>`;
            }}

            if (details.artist && details.album) {{
                content += `<div class="details">Artista: ${{details.artist}} | Ãlbum: ${{details.album}}</div>`;
            }} else if (details.artist && details.track) {{
                content += `<div class="details">Artista: ${{details.artist}} | CanciÃ³n: ${{details.track}}</div>`;
            }}

            if (chartData.type === 'combined') {{
                content += `<div class="details">CategorÃ­a: ${{details.category}}</div>`;
            }}

            // Agregar desglose por usuario si está disponible
            if (details.user_plays && Object.keys(details.user_plays).length > 0) {{
                content += `<div class="details" style="margin-top: 10px; font-weight: bold;">Desglose por usuario:</div>`;
                const userPlays = Object.entries(details.user_plays)
                    .sort((a, b) => b[1] - a[1]) // Ordenar por scrobbles desc
                    .map(([user, plays]) => `${{user}} (${{plays.toLocaleString()}})`)
                    .join(', ');
                content += `<div class="users">${{userPlays}}</div>`;
            }}

            content += `</div>`;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function showEvolutionPopup(itemName, year, userData) {{
            let title = `${{itemName}} en ${{year}}`;
            let content = '';

            content += `<div class="popup-item">
                <div class="name">${{itemName}}</div>
                <div class="details">
                    Año: ${{year}} |
                    Scrobbles: ${{userData.total.toLocaleString()}}
                </div>`;

            if (userData.users && Object.keys(userData.users).length > 0) {{
                content += `<div class="details" style="margin-top: 10px; font-weight: bold;">Desglose por usuario:</div>`;
                const userPlays = Object.entries(userData.users)
                    .sort((a, b) => b[1] - a[1]) // Ordenar por scrobbles desc
                    .map(([user, plays]) => `${{user}} (${{plays.toLocaleString()}})`)
                    .join(', ');
                content += `<div class="users">${{userPlays}}</div>`;
            }}

            content += `</div>`;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        // Configurar cierre de popup
        document.getElementById('popupClose').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        document.getElementById('popupOverlay').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});
    </script>
</body>
</html>"""

    def _format_number(self, number: int) -> str:
        """Formatea nÃºmeros con separadores de miles"""
        return f"{number:,}".replace(",", ".")
