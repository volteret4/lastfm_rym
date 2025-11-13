#!/usr/bin/env python3
"""
UserStatsHTMLGenerator - Clase para generar HTML con gráficos interactivos de estadísticas de usuarios
"""

import json
from typing import Dict, List


class UserStatsHTMLGenerator:
    """Clase para generar HTML con gráficos interactivos de estadísticas de usuarios"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera el HTML completo para estadísticas de usuarios"""
        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(all_user_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - Estadísticas Individuales</title>
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
            color: #cdd6f4;
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
            flex-shrink: 0;
        }}

        .user-button:hover {{
            background: #b4a3e8;
            transform: scale(1.1);
        }}

        .user-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            backdrop-filter: blur(5px);
        }}

        .user-modal-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border-radius: 12px;
            padding: 30px;
            width: 90%;
            max-width: 400px;
            border: 2px solid #cba6f7;
        }}

        .user-modal-header {{
            color: #cba6f7;
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 20px;
            text-align: center;
        }}

        .user-modal-close {{
            position: absolute;
            top: 15px;
            right: 20px;
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0;
        }}

        .user-modal-close:hover {{
            color: #cba6f7;
        }}

        .user-options {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .user-option {{
            padding: 12px 20px;
            background: #313244;
            border: 2px solid #45475a;
            border-radius: 8px;
            color: #cdd6f4;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
        }}

        .user-option:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .user-option.selected {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
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

        select {{
            padding: 8px 15px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            font-size: 0.95em;
            cursor: pointer;
            transition: all 0.3s;
        }}

        select:hover {{
            border-color: #cba6f7;
        }}

        select:focus {{
            outline: none;
            border-color: #cba6f7;
            box-shadow: 0 0 0 3px rgba(203, 166, 247, 0.2);
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

        .data-type-buttons {{
            display: flex;
            gap: 10px;
            margin: 15px 0;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .data-type-btn {{
            padding: 6px 12px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.8em;
            font-weight: 600;
        }}

        .data-type-btn:hover {{
            border-color: #f38ba8;
            background: #45475a;
        }}

        .data-type-btn.active {{
            background: #f38ba8;
            color: #1e1e2e;
            border-color: #f38ba8;
        }}

        .provider-buttons {{
            display: flex;
            gap: 10px;
            margin: 15px 0;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .provider-btn {{
            padding: 6px 12px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.8em;
            font-weight: 600;
        }}

        .provider-btn:hover {{
            border-color: #a6e3a1;
            background: #45475a;
        }}

        .provider-btn.active {{
            background: #a6e3a1;
            color: #1e1e2e;
            border-color: #a6e3a1;
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
            grid-template-columns: 1fr;
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

        /* Estilos para la nueva sección de géneros */
        .genres-section {{
            margin-bottom: 40px;
        }}

        .genres-pie-container {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }}

        .scatter-chart-wrapper {{
            position: relative;
            height: 350px;
            margin-bottom: 10px;
        }}

        .scatter-charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .coincidences-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 25px;
            margin-bottom: 30px;
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
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .popup-item .name {{
            color: #cdd6f4;
            font-weight: 600;
        }}

        .popup-item .count {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            .coincidences-grid {{
                grid-template-columns: 1fr;
            }}

            .evolution-charts {{
                grid-template-columns: 1fr;
            }}

            .scatter-charts-grid {{
                grid-template-columns: 1fr;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .view-buttons {{
                justify-content: center;
            }}

            header {{
                flex-direction: column;
                gap: 15px;
            }}

            .nav-buttons {{
                order: -1;
            }}

            .user-button {{
                order: 1;
                align-self: flex-end;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>🎵 RYM Hispano Estadísticas</h1>
                <div class="nav-buttons">
                    <a href="esta-semana.html" class="nav-button">TEMPORALES</a>
                    <a href="index.html#grupo" class="nav-button">GRUPO</a>
                    <a href="index.html#about" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">👤</button>
        </header>

        <!-- Modal de selección de usuario -->
        <div class="user-modal" id="userModal">
            <div class="user-modal-content">
                <button class="user-modal-close" id="userModalClose">×</button>
                <div class="user-modal-header">Seleccionar Usuario</div>
                <div class="user-options" id="userOptions">
                    <!-- Se llenarán dinámicamente -->
                </div>
            </div>
        </div>

        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Usuario:</label>
                <select id="userSelect">
                    <!-- Se llenará dinámicamente -->
                </select>
            </div>

            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="individual">YoMiMeConMigo</button>
                    <button class="view-btn" data-view="genres">Géneros</button>
                    <button class="view-btn" data-view="coincidences">Coincidencias</button>
                    <button class="view-btn" data-view="evolution">Evolución</button>
                </div>
            </div>
        </div>

        <div class="stats-container">
            <!-- Vista Individual -->
            <div id="individualView" class="view active">
                <div class="data-type-buttons">
                    <button class="data-type-btn active" data-type="annual">Por Año</button>
                    <button class="data-type-btn" data-type="cumulative">Acumulativo</button>
                </div>

                <div class="evolution-section">
                    <h3>🎭 Evolución Individual</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualGenresChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Vista de Géneros -->
            <div id="genresView" class="view">
                <div class="provider-buttons">
                    <button class="provider-btn active" data-provider="lastfm">Last.fm</button>
                    <button class="provider-btn" data-provider="musicbrainz">MusicBrainz</button>
                    <button class="provider-btn" data-provider="discogs">Discogs</button>
                </div>

                <div class="genres-section">
                    <h3>🎶 Distribución de Géneros</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Géneros del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="genresPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>📈 Evolución de Artistas por Género</h3>
                    <div class="scatter-charts-grid" id="genresScatterGrid">
                        <!-- Se llenarán dinámicamente los 5 gráficos de scatter -->
                    </div>
                </div>
            </div>

            <!-- Vista de Coincidencias -->
            <div id="coincidencesView" class="view">
                <div class="coincidences-grid">
                    <div class="chart-container">
                        <h3>Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="artistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="artistsInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de Evolución -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>Evolución de Géneros</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="genresEvolutionChart"></canvas>
                            </div>
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
                <button id="popupClose" class="popup-close">X</button>
            </div>
            <div id="popupContent" class="popup-content"></div>
        </div>
    </div>

    <script>
        const users = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};

        let currentUser = null;
        let currentView = 'individual';
        let currentDataType = 'annual';
        let currentProvider = 'lastfm';
        let charts = {{}};

        // Funcionalidad del botón de usuario (similar al temporal)
        function initializeUserSelector() {{
            const userButton = document.getElementById('userButton');
            const userModal = document.getElementById('userModal');
            const userModalClose = document.getElementById('userModalClose');
            const userOptions = document.getElementById('userOptions');

            let selectedUser = localStorage.getItem('lastfm_selected_user') || '';

            users.forEach(user => {{
                const option = document.createElement('div');
                option.className = 'user-option';
                option.dataset.user = user;
                option.textContent = user;
                userOptions.appendChild(option);
            }});

            updateSelectedUserOption(selectedUser);

            userButton.addEventListener('click', () => {{
                userModal.style.display = 'block';
            }});

            userModalClose.addEventListener('click', () => {{
                userModal.style.display = 'none';
            }});

            userModal.addEventListener('click', (e) => {{
                if (e.target === userModal) {{
                    userModal.style.display = 'none';
                }}
            }});

            userOptions.addEventListener('click', (e) => {{
                if (e.target.classList.contains('user-option')) {{
                    const user = e.target.dataset.user;
                    selectedUser = user;

                    if (user) {{
                        localStorage.setItem('lastfm_selected_user', user);
                    }} else {{
                        localStorage.removeItem('lastfm_selected_user');
                    }}

                    updateSelectedUserOption(user);
                    userModal.style.display = 'none';

                    const userSelect = document.getElementById('userSelect');
                    userSelect.value = user;

                    selectUser(user);
                }}
            }});

            return selectedUser;
        }}

        function updateSelectedUserOption(selectedUser) {{
            const userOptions = document.getElementById('userOptions');
            userOptions.querySelectorAll('.user-option').forEach(option => {{
                option.classList.remove('selected');
                if (option.dataset.user === selectedUser) {{
                    option.classList.add('selected');
                }}
            }});
        }}

        const userSelect = document.getElementById('userSelect');

        users.forEach(user => {{
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        }});

        const viewButtons = document.querySelectorAll('.view-btn');
        viewButtons.forEach(btn => {{
            btn.addEventListener('click', function() {{
                const view = this.dataset.view;
                switchView(view);
            }});
        }});

        const dataTypeButtons = document.querySelectorAll('.data-type-btn');
        dataTypeButtons.forEach(btn => {{
            btn.addEventListener('click', function() {{
                const dataType = this.dataset.type;
                switchDataType(dataType);
            }});
        }});

        const providerButtons = document.querySelectorAll('.provider-btn');
        providerButtons.forEach(btn => {{
            btn.addEventListener('click', function() {{
                const provider = this.dataset.provider;
                switchProvider(provider);
            }});
        }});

        function switchProvider(provider) {{
            currentProvider = provider;

            document.querySelectorAll('.provider-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-provider="${{provider}}"]`).classList.add('active');

            if (currentView === 'genres' && currentUser && allStats[currentUser]) {{
                renderGenresCharts(allStats[currentUser]);
            }}
        }}

        function switchDataType(dataType) {{
            currentDataType = dataType;

            document.querySelectorAll('.data-type-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-type="${{dataType}}"]`).classList.add('active');

            if (currentView === 'individual' && currentUser && allStats[currentUser]) {{
                renderIndividualCharts(allStats[currentUser]);
            }}
        }}

        function switchView(view) {{
            currentView = view;

            document.querySelectorAll('.view-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            document.querySelector(`[data-view="${{view}}"]`).classList.add('active');

            document.querySelectorAll('.view').forEach(v => {{
                v.classList.remove('active');
            }});
            document.getElementById(view + 'View').classList.add('active');

            if (currentUser && allStats[currentUser]) {{
                const userStats = allStats[currentUser];
                if (view === 'individual') {{
                    renderIndividualCharts(userStats);
                }} else if (view === 'genres') {{
                    renderGenresCharts(userStats);
                }} else if (view === 'coincidences') {{
                    renderCoincidenceCharts(userStats);
                }} else if (view === 'evolution') {{
                    renderEvolutionCharts(userStats);
                }}
            }}
        }}

        function selectUser(username) {{
            currentUser = username;
            const userStats = allStats[username];

            if (!userStats) {{
                console.error('No stats found for user:', username);
                return;
            }}

            if (currentView === 'individual') {{
                renderIndividualCharts(userStats);
            }} else if (currentView === 'genres') {{
                renderGenresCharts(userStats);
            }} else if (currentView === 'coincidences') {{
                renderCoincidenceCharts(userStats);
            }} else if (currentView === 'evolution') {{
                renderEvolutionCharts(userStats);
            }}
        }}

        function renderGenresCharts(userStats) {{
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            const genresData = userStats.genres;
            if (!genresData || !genresData[currentProvider]) {{
                return;
            }}

            const providerData = genresData[currentProvider];
            renderGenresPieChart(providerData.pie_chart);
            renderGenresScatterCharts(providerData.scatter_charts, providerData.years);
        }}

        function renderGenresPieChart(pieData) {{
            const canvas = document.getElementById('genresPieChart');
            const info = document.getElementById('genresPieInfo');

            if (!pieData || !pieData.data || Object.keys(pieData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';
            info.innerHTML = `Total: ${{pieData.total.toLocaleString()}} scrobbles | Proveedor: ${{currentProvider}}`;

            const data = {{
                labels: Object.keys(pieData.data),
                datasets: [{{
                    data: Object.values(pieData.data),
                    backgroundColor: colors.slice(0, Object.keys(pieData.data).length),
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
                    }}
                }}
            }};

            charts['genresPieChart'] = new Chart(canvas, config);
        }}

        function renderGenresScatterCharts(scatterData, years) {{
            const container = document.getElementById('genresScatterGrid');
            container.innerHTML = '';

            Object.keys(scatterData).forEach((genre, index) => {{
                const artists = scatterData[genre];

                if (!artists || artists.length === 0) return;

                const genreContainer = document.createElement('div');
                genreContainer.className = 'genres-pie-container';

                const title = document.createElement('h4');
                title.textContent = `${{genre}} - Top ${{artists.length}} Artistas`;
                title.style.color = '#cba6f7';
                title.style.textAlign = 'center';
                title.style.marginBottom = '15px';
                genreContainer.appendChild(title);

                const canvasWrapper = document.createElement('div');
                canvasWrapper.className = 'scatter-chart-wrapper';

                const canvas = document.createElement('canvas');
                const canvasId = `scatterChart_${{genre.replace(/[^a-zA-Z0-9]/g, '_')}}_${{index}}`;
                canvas.id = canvasId;
                canvasWrapper.appendChild(canvas);

                genreContainer.appendChild(canvasWrapper);
                container.appendChild(genreContainer);

                const datasets = [];

                artists.forEach((artistData, artistIndex) => {{
                    const points = [];

                    years.forEach(year => {{
                        const plays = artistData.yearly_data[year] || 0;
                        if (plays > 0) {{
                            points.push({{
                                x: year,
                                y: plays,
                                artistName: artistData.artist
                            }});
                        }}
                    }});

                    if (points.length > 0) {{
                        datasets.push({{
                            label: artistData.artist,
                            data: points,
                            backgroundColor: colors[artistIndex % colors.length],
                            borderColor: colors[artistIndex % colors.length],
                            pointRadius: 8,
                            pointHoverRadius: 12,
                            showLine: false
                        }});
                    }}
                }});

                const config = {{
                    type: 'scatter',
                    data: {{ datasets }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{
                                type: 'linear',
                                position: 'bottom',
                                title: {{
                                    display: true,
                                    text: 'Año',
                                    color: '#a6adc8'
                                }},
                                ticks: {{
                                    color: '#a6adc8',
                                    stepSize: 1
                                }},
                                grid: {{
                                    color: '#313244'
                                }},
                                min: Math.min(...years),
                                max: Math.max(...years)
                            }},
                            y: {{
                                title: {{
                                    display: true,
                                    text: 'Scrobbles',
                                    color: '#a6adc8'
                                }},
                                ticks: {{
                                    color: '#a6adc8'
                                }},
                                grid: {{
                                    color: '#313244'
                                }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                display: false
                            }},
                            tooltip: {{
                                backgroundColor: '#1e1e2e',
                                titleColor: '#cba6f7',
                                bodyColor: '#cdd6f4',
                                borderColor: '#cba6f7',
                                borderWidth: 1,
                                callbacks: {{
                                    title: function(context) {{
                                        const point = context[0].raw;
                                        return point.artistName;
                                    }},
                                    label: function(context) {{
                                        const point = context.raw;
                                        return `${{point.x}}: ${{point.y}} scrobbles`;
                                    }}
                                }}
                            }}
                        }},
                        interaction: {{
                            mode: 'point'
                        }},
                        onClick: function(event, elements) {{
                            if (elements.length > 0) {{
                                const element = elements[0];
                                const point = this.data.datasets[element.datasetIndex].data[element.index];
                                showArtistPopup(point.artistName, genre, currentProvider, point.x, point.y);
                            }}
                        }}
                    }}
                }};

                charts[canvasId] = new Chart(canvas, config);
            }});
        }}

        function showArtistPopup(artistName, genre, provider, year, scrobbles) {{
            const title = `${{artistName}} - ${{genre}} (${{year}})`;
            const content = `
                <div class="popup-item">
                    <span class="name">Artista: ${{artistName}}</span>
                </div>
                <div class="popup-item">
                    <span class="name">Género: ${{genre}}</span>
                </div>
                <div class="popup-item">
                    <span class="name">Año: ${{year}}</span>
                    <span class="count">${{scrobbles}} scrobbles</span>
                </div>
                <div class="popup-item">
                    <span class="name">Proveedor: ${{provider}}</span>
                </div>
            `;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function renderIndividualCharts(userStats) {{
            // Placeholder para gráficos individuales
        }}

        function renderCoincidenceCharts(userStats) {{
            // Placeholder para gráficos de coincidencias
        }}

        function renderEvolutionCharts(userStats) {{
            // Placeholder para gráficos de evolución
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

        userSelect.addEventListener('change', function() {{
            selectUser(this.value);
        }});

        // Inicializar
        const initialUser = initializeUserSelector();
        if (initialUser && users.includes(initialUser)) {{
            userSelect.value = initialUser;
            selectUser(initialUser);
        }} else if (users.length > 0) {{
            selectUser(users[0]);
        }}
    </script>
</body>
</html>"""

    def _format_number(self, number: int) -> str:
        """Formatea números con separadores de miles"""
        return f"{number:,}".replace(",", ".")
