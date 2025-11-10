#!/usr/bin/env python3
"""
UserStatsHTMLGenerator - Clase para generar HTML con grÃƒÂ¡ficos interactivos de estadÃƒÂ­sticas de usuarios
"""

import json
from typing import Dict, List


class UserStatsHTMLGenerator:
    """Clase para generar HTML con grÃƒÂ¡ficos interactivos de estadÃƒÂ­sticas de usuarios"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera el HTML completo para estadÃƒÂ­sticas de usuarios"""
        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(all_user_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - EstadÃƒÂ­sticas Individuales</title>
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

        .user-header {{
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        .user-header h2 {{
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }}

        .user-info {{
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

        .coincidences-grid {{
            display: grid;
            grid-template-columns: 1fr;
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
            <h1>Ã°Å¸â€˜Â¤ EstadÃƒÂ­sticas Individuales</h1>
            <p class="subtitle">AnÃƒÂ¡lisis detallado por usuario</p>
        </header>

        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Usuario:</label>
                <select id="userSelect">
                    <!-- Se llenarÃƒÂ¡ dinÃƒÂ¡micamente -->
                </select>
            </div>

            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="individual">YoMiMeConMigo</button>
                    <button class="view-btn" data-view="coincidences">Coincidencias</button>
                    <button class="view-btn" data-view="evolution">EvoluciÃƒÂ³n</button>
                </div>
            </div>
        </div>

        <div id="userHeader" class="user-header">
            <h2 id="userName">Selecciona un usuario</h2>
            <p class="user-info" id="userInfo">PerÃƒÂ­odo de anÃƒÂ¡lisis: {years_back + 1} aÃƒÂ±os</p>
        </div>

        <div class="stats-container">
            <!-- Resumen de estadÃƒÂ­sticas -->
            <div id="summaryStats" class="summary-stats">
                <!-- Se llenarÃƒÂ¡ dinÃƒÂ¡micamente -->
            </div>

            <!-- Vista Individual (YoMiMeConMigo) -->
            <div id="individualView" class="view active">
                <div class="evolution-section">
                    <h3>Ã°Å¸Å½Âµ EvoluciÃƒÂ³n de GÃƒÂ©neros Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 GÃƒÂ©neros por AÃƒÂ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualGenresChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸ÂÂ·Ã¯Â¸Â EvoluciÃƒÂ³n de Sellos Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Sellos por AÃƒÂ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualLabelsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸Å½Â¤ EvoluciÃƒÂ³n de Artistas Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas por AÃƒÂ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸â€™Â« One Hit Wonders</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con 1 CanciÃƒÂ³n (+25 scrobbles)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualOneHitChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸â€Â¥ Artistas con Mayor Streak</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con MÃƒÂ¡s DÃƒÂ­as Consecutivos</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualStreakChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸â€œÅ¡ Artistas con Mayor DiscografÃƒÂ­a</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con MÃƒÂ¡s Canciones ÃƒÅ¡nicas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualTrackCountChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸Å’Å¸ Artistas Nuevos</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas Nuevos (Sin Escuchas Previas)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualNewArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸â€œË† Artistas en Ascenso</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas que MÃƒÂ¡s RÃƒÂ¡pido Subieron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualRisingChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸â€œâ€° Artistas en Declive</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas que MÃƒÂ¡s RÃƒÂ¡pido Bajaron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualFallingChart"></canvas>
                            </div>
                        </div>
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

                    <div class="chart-container">
                        <h3>ÃƒÂlbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="albumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="tracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="tracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>GÃƒÂ©neros (Individual)</h3>
                        <div class="chart-wrapper">
                            <canvas id="genresChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>GÃƒÂ©neros (Coincidencias)</h3>
                        <div class="chart-wrapper">
                            <canvas id="genreCoincidencesChart"></canvas>
                        </div>
                        <div class="chart-info" id="genreCoincidencesInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Sellos DiscogrÃƒÂ¡ficos</h3>
                        <div class="chart-wrapper">
                            <canvas id="labelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>AÃƒÂ±os de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="releaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="releaseYearsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Ã°Å¸â€œË† Top 10 Artistas por Escuchas</h3>
                        <div class="chart-wrapper">
                            <canvas id="topScrobblesChart"></canvas>
                        </div>
                        <div class="chart-info" id="topScrobblesInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Ã°Å¸ÂÂ  Vuelve a Casa</h3>
                        <div class="chart-wrapper">
                            <canvas id="topDaysChart"></canvas>
                        </div>
                        <div class="chart-info" id="topDaysInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Ã°Å¸â€œÅ¡ DiscografÃƒÂ­a Completada</h3>
                        <div class="chart-wrapper">
                            <canvas id="topDiscographyChart"></canvas>
                        </div>
                        <div class="chart-info" id="topDiscographyInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Ã°Å¸â€™Â« Streaks</h3>
                        <div class="chart-wrapper">
                            <canvas id="topStreaksChart"></canvas>
                        </div>
                        <div class="chart-info" id="topStreaksInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de EvoluciÃƒÂ³n -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>Ã°Å¸Å½Âµ EvoluciÃƒÂ³n de GÃƒÂ©neros (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en GÃƒÂ©neros por AÃƒÂ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="genresEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸ÂÂ·Ã¯Â¸Â EvoluciÃƒÂ³n de Sellos (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Sellos por AÃƒÂ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="labelsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸â€œâ€¦ EvoluciÃƒÂ³n de DÃƒÂ©cadas (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en DÃƒÂ©cadas por AÃƒÂ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="releaseYearsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Ã°Å¸Â¤Â EvoluciÃƒÂ³n de Coincidencias BÃƒÂ¡sicas</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Artistas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="artistsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en ÃƒÂlbumes</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="albumsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en Canciones</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="tracksEvolutionChart"></canvas>
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
                <button id="popupClose" class="popup-close">Ãƒâ€”</button>
            </div>
            <div id="popupContent" class="popup-content"></div>
        </div>
        </div>
    </div>

    <script>
        const users = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};

        let currentUser = null;
        let currentView = 'individual';
        let charts = {{}};

        // InicializaciÃƒÂ³n simple sin DOMContentLoaded - siguiendo el patrÃƒÂ³n de html_anual.py
        const userSelect = document.getElementById('userSelect');

        // Llenar selector de usuarios
        users.forEach(user => {{
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        }});

        // Manejar botones de vista
        const viewButtons = document.querySelectorAll('.view-btn');
        viewButtons.forEach(btn => {{
            btn.addEventListener('click', function() {{
                const view = this.dataset.view;
                switchView(view);
            }});
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
            document.getElementById(view + 'View').classList.add('active');

            // Render appropriate charts
            if (currentUser && allStats[currentUser]) {{
                const userStats = allStats[currentUser];
                if (view === 'individual') {{
                    renderIndividualCharts(userStats);
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

            updateUserHeader(username, userStats);
            updateSummaryStats(userStats);

            if (currentView === 'individual') {{
                renderIndividualCharts(userStats);
            }} else if (currentView === 'coincidences') {{
                renderCoincidenceCharts(userStats);
            }} else if (currentView === 'evolution') {{
                renderEvolutionCharts(userStats);
            }}
        }}

        function updateUserHeader(username, userStats) {{
            document.getElementById('userName').textContent = username;
            document.getElementById('userInfo').innerHTML =
                `PerÃƒÂ­odo: ${{userStats.period}} | Generado: ${{userStats.generated_at}}`;
        }}

        function updateSummaryStats(userStats) {{
            const totalScrobbles = Object.values(userStats.yearly_scrobbles).reduce((a, b) => a + b, 0);

            const artistsChart = userStats.coincidences.charts.artists;
            const albumsChart = userStats.coincidences.charts.albums;
            const tracksChart = userStats.coincidences.charts.tracks;
            const genresChart = userStats.coincidences.charts.genres;
            const releaseYearsChart = userStats.coincidences.charts.release_years;
            const labelsChart = userStats.coincidences.charts.labels;

            const totalArtistCoincidences = Object.keys(artistsChart.data || {{}}).length;
            const totalAlbumCoincidences = Object.keys(albumsChart.data || {{}}).length;
            const totalTrackCoincidences = Object.keys(tracksChart.data || {{}}).length;
            const totalGenres = Object.keys(genresChart.data || {{}}).length;
            const totalReleaseYears = Object.keys(releaseYearsChart.data || {{}}).length;
            const totalLabels = Object.keys(labelsChart.data || {{}}).length;

            const summaryHTML = `
                <div class="summary-card">
                    <div class="number">${{totalScrobbles.toLocaleString()}}</div>
                    <div class="label">Scrobbles</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalArtistCoincidences}}</div>
                    <div class="label">Usuarios (Artistas)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalAlbumCoincidences}}</div>
                    <div class="label">Usuarios (ÃƒÂlbumes)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">GÃƒÂ©neros</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalReleaseYears}}</div>
                    <div class="label">DÃƒÂ©cadas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalLabels}}</div>
                    <div class="label">Sellos</div>
                </div>
            `;

            document.getElementById('summaryStats').innerHTML = summaryHTML;
        }}

        function renderCoincidenceCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // GrÃƒÂ¡ficos bÃƒÂ¡sicos
            renderPieChart('artistsChart', userStats.coincidences.charts.artists, 'artistsInfo');
            renderPieChart('albumsChart', userStats.coincidences.charts.albums, 'albumsInfo');
            renderPieChart('tracksChart', userStats.coincidences.charts.tracks, 'tracksInfo');
            renderPieChart('genresChart', userStats.coincidences.charts.genres, 'genresInfo');

            // Nuevos grÃƒÂ¡ficos de coincidencias
            renderPieChart('genreCoincidencesChart', userStats.coincidences.charts.genre_coincidences, 'genreCoincidencesInfo');
            renderPieChart('labelsChart', userStats.coincidences.charts.labels, 'labelsInfo');
            renderPieChart('releaseYearsChart', userStats.coincidences.charts.release_years, 'releaseYearsInfo');

            // GrÃƒÂ¡ficos especiales
            renderPieChart('topScrobblesChart', userStats.coincidences.charts.top_scrobbles, 'topScrobblesInfo');
            renderPieChart('topDaysChart', userStats.coincidences.charts.top_days, 'topDaysInfo');
            renderPieChart('topDiscographyChart', userStats.coincidences.charts.top_discography, 'topDiscographyInfo');
            renderPieChart('topStreaksChart', userStats.coincidences.charts.top_streaks, 'topStreaksInfo');
        }}

        function renderEvolutionCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Ahora todos son de coincidencias
            renderCoincidencesEvolution('genres', userStats.evolution.genres);
            renderCoincidencesEvolution('labels', userStats.evolution.labels);
            renderCoincidencesEvolution('release_years', userStats.evolution.release_years);
            renderCoincidencesEvolution('artists', userStats.evolution.coincidences);
            renderCoincidencesEvolution('albums', userStats.evolution.coincidences);
            renderCoincidencesEvolution('tracks', userStats.evolution.coincidences);
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
            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}} | Click en una porciÃƒÂ³n para ver detalles`;

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
                            showSmartPopup(chartData, label);
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showSmartPopup(chartData, selectedLabel) {{
            const details = chartData.details[selectedLabel];
            const chartType = chartData.type;

            if (!details) return;

            let title = '';
            let content = '';

            if (chartType === 'artists') {{
                // Mostrar ÃƒÂ¡lbumes top para estos artistas
                title = `Top ÃƒÂlbumes - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(artist => {{
                    if (details[artist] && details[artist].length > 0) {{
                        content += `<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">${{artist}}</h4>`;
                        details[artist].forEach(album => {{
                            content += `<div class="popup-item">
                                <span class="name">${{album.name}}</span>
                                <span class="count">${{album.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }});
            }} else if (chartType === 'albums') {{
                // Mostrar canciones top para estos ÃƒÂ¡lbumes
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(album => {{
                    if (details[album] && details[album].length > 0) {{
                        content += `<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">${{album}}</h4>`;
                        details[album].forEach(track => {{
                            content += `<div class="popup-item">
                                <span class="name">${{track.name}}</span>
                                <span class="count">${{track.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }});
            }} else if (chartType === 'tracks') {{
                // Mostrar canciones mÃƒÂ¡s escuchadas
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(track => {{
                    const trackData = details[track];
                    content += `<div class="popup-item">
                        <span class="name">${{track}}</span>
                        <span class="count">${{trackData.user_plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'genres') {{
                // Mostrar artistas top para este gÃƒÂ©nero
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'years_labels') {{
                // Mostrar artistas top para esta dÃƒÂ©cada/sello
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'top_scrobbles') {{
                // Mostrar top canciones del artista para ambos usuarios
                title = `Top Artistas Coincidentes - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_plays + artistData.other_plays}} plays totales</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_days') {{
                // Mostrar artistas coincidentes con dÃƒÂ­as
                title = `Artistas "Vuelve a Casa" - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_days + artistData.other_days}} dÃƒÂ­as totales</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_discography') {{
                // Mostrar artistas coincidentes con nÃƒÂºmero de canciones
                title = `DiscografÃƒÂ­a Completada - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_tracks + artistData.other_tracks}} canciones</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_streaks') {{
                // Mostrar artistas coincidentes con streaks
                title = `Streaks Coincidentes - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">Max: ${{Math.max(artistData.user_streak, artistData.other_streak)}} dÃƒÂ­as</span>
                        </div>`;
                    }});
                }}
            }}

            if (content) {{
                document.getElementById('popupTitle').textContent = title;
                document.getElementById('popupContent').innerHTML = content;
                document.getElementById('popupOverlay').style.display = 'block';
                document.getElementById('popup').style.display = 'block';
            }}
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

        function renderCoincidencesEvolution(type, evolutionData) {{
            let canvas, chartId;

            // Mapear tipos a canvas IDs
            if (type === 'genres') {{
                canvas = document.getElementById('genresEvolutionChart');
                chartId = 'genresEvolutionChart';
            }} else if (type === 'labels') {{
                canvas = document.getElementById('labelsEvolutionChart');
                chartId = 'labelsEvolutionChart';
            }} else if (type === 'release_years') {{
                canvas = document.getElementById('releaseYearsEvolutionChart');
                chartId = 'releaseYearsEvolutionChart';
            }} else {{
                canvas = document.getElementById(type + 'EvolutionChart');
                chartId = type + 'EvolutionChart';
            }}

            if (!evolutionData || !evolutionData.data) {{
                return;
            }}

            // Para tipos bÃƒÂ¡sicos (artists, albums, tracks), usar evolutionData.data[type]
            // Para nuevos tipos (genres, labels, release_years), usar directamente evolutionData.data
            let typeData, detailsData;
            if (['artists', 'albums', 'tracks'].includes(type)) {{
                typeData = evolutionData.data[type];
                detailsData = evolutionData.details[type];
            }} else {{
                typeData = evolutionData.data;
                detailsData = evolutionData.details;
            }}

            if (!typeData) return;

            const datasets = [];
            let colorIndex = 0;

            Object.keys(typeData).forEach(user => {{
                datasets.push({{
                    label: user,
                    data: evolutionData.years.map(year => typeData[user][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const config = {{
                type: 'line',
                data: {{
                    labels: evolutionData.years,
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
                            borderWidth: 1
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
                            const user = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const coincidences = this.data.datasets[datasetIndex].data[pointIndex];

                            if (coincidences > 0 && detailsData && detailsData[user] && detailsData[user][year]) {{
                                const typeLabel = type === 'artists' ? 'Artistas' :
                                               type === 'albums' ? 'ÃƒÂlbumes' :
                                               type === 'tracks' ? 'Canciones' :
                                               type === 'genres' ? 'GÃƒÂ©neros' :
                                               type === 'labels' ? 'Sellos' :
                                               type === 'release_years' ? 'DÃƒÂ©cadas' : type;

                                // Para grÃƒÂ¡ficos bÃƒÂ¡sicos, mostrar top 10; para otros, top 5
                                const limit = ['artists', 'albums', 'tracks'].includes(type) ? 10 : 5;
                                const limitedDetails = detailsData[user][year].slice(0, limit);
                                showLinearPopup(`Top ${{limit}} ${{typeLabel}} - ${{user}} (${{year}})`, limitedDetails);
                            }}
                        }}
                    }}
                }}
            }};

            charts[chartId] = new Chart(canvas, config);
        }}

        function showLinearPopup(title, details) {{
            if (!details || details.length === 0) return;

            let content = '';
            details.slice(0, 10).forEach(item => {{
                // Verificar si es un detalle de coincidencia real (con artist, album, track)
                if (item.artist) {{
                    // Es una coincidencia real - mostrar información completa
                    content += `<div class="popup-item">
                        <div style="margin-bottom: 5px;">
                            <span class="name" style="font-weight: bold;">${{item.artist}}</span>
                        </div>`;

                    if (item.track) {{
                        content += `<div style="margin-left: 10px; color: #a6adc8;">
                            🎵 ${{item.track}}
                        </div>`;
                    }}

                    if (item.album) {{
                        content += `<div style="margin-left: 10px; color: #a6adc8;">
                            💿 ${{item.album}}
                        </div>`;
                    }}

                    if (item.user1_plays && item.user2_plays) {{
                        content += `<div style="margin-left: 10px; font-size: 0.9em; color: #6c7086;">
                            Usuario 1: ${{item.user1_plays}} plays | Usuario 2: ${{item.user2_plays}} plays
                        </div>`;
                    }}

                    content += `</div>`;
                }} else {{
                    // Es un detalle simple - mostrar como antes
                    content += `<div class="popup-item">
                        <span class="name">${{item.name}}</span>
                        <span class="count">${{item.plays}} plays</span>
                    </div>`;
                }}
            }});

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function renderIndividualCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar todos los grÃƒÂ¡ficos individuales
            if (userStats.individual) {{
                renderIndividualLineChart('individualGenresChart', userStats.individual.genres, 'GÃƒÂ©neros');
                renderIndividualLineChart('individualLabelsChart', userStats.individual.labels, 'Sellos');
                renderIndividualLineChart('individualArtistsChart', userStats.individual.artists, 'Artistas');
                renderIndividualLineChart('individualOneHitChart', userStats.individual.one_hit_wonders, 'One Hit Wonders');
                renderIndividualLineChart('individualStreakChart', userStats.individual.streak_artists, 'Artistas con Mayor Streak');
                renderIndividualLineChart('individualTrackCountChart', userStats.individual.track_count_artists, 'Artistas con Mayor DiscografÃƒÂ­a');
                renderIndividualLineChart('individualNewArtistsChart', userStats.individual.new_artists, 'Artistas Nuevos');
                renderIndividualLineChart('individualRisingChart', userStats.individual.rising_artists, 'Artistas en Ascenso');
                renderIndividualLineChart('individualFallingChart', userStats.individual.falling_artists, 'Artistas en Declive');
            }}
        }}

        function renderIndividualLineChart(canvasId, chartData, title) {{
            const canvas = document.getElementById(canvasId);

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            Object.keys(chartData.data).forEach(item => {{
                datasets.push({{
                    label: item,
                    data: chartData.years.map(year => chartData.data[item][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
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
                                afterBody: function(tooltipItems) {{
                                    if (tooltipItems.length > 0) {{
                                        const item = tooltipItems[0].dataset.label;
                                        const year = tooltipItems[0].label;

                                        if (chartData.details && chartData.details[item] && chartData.details[item][year]) {{
                                            const details = chartData.details[item][year];

                                            if (title === 'One Hit Wonders' && details.track && details.artist) {{
                                                return [`Artista: ${{details.artist}}`, `CanciÃƒÂ³n: ${{details.track}}`];
                                            }} else if (title === 'Artistas con Mayor Streak' && details.days !== undefined) {{
                                                return [`DÃƒÂ­as en ${{year}}: ${{details.days}}`];
                                            }} else if (title === 'Artistas con Mayor DiscografÃƒÂ­a' && details.track_count !== undefined) {{
                                                return [`Canciones ÃƒÅ¡nicas: ${{details.track_count}}`];
                                            }}
                                        }}
                                    }}
                                    return [];
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
                            }},
                            title: {{
                                display: true,
                                text: title === 'Artistas con Mayor Streak' ? 'DÃƒÂ­as' :
                                      title === 'Artistas con Mayor DiscografÃƒÂ­a' ? 'Canciones ÃƒÅ¡nicas' :
                                      'Reproducciones',
                                color: '#a6adc8'
                            }}
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const datasetIndex = elements[0].datasetIndex;
                            const pointIndex = elements[0].index;
                            const item = this.data.datasets[datasetIndex].label;
                            const year = this.data.labels[pointIndex];
                            const value = this.data.datasets[datasetIndex].data[pointIndex];

                            if (value > 0) {{
                                showIndividualPopupDetailed(title, item, year, value, chartData);
                            }}
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        function showIndividualPopupDetailed(category, item, year, value, chartData) {{
            let title = `${{category}} - ${{item}} (${{year}})`;
            let content = '';

            if (chartData.details && chartData.details[item] && chartData.details[item][year]) {{
                const details = chartData.details[item][year];

                if (category === 'One Hit Wonders') {{
                    // Mostrar artista y canciÃ³n especÃ­fica
                    content = `<div class="popup-item">
                        <span class="name">Artista: ${{details.artist}}</span>
                    </div>
                    <div class="popup-item">
                        <span class="name">CanciÃ³n: ${{details.track}}</span>
                        <span class="count">${{details.plays}} reproducciones</span>
                    </div>`;
                }} else if (category === 'GÃ©neros') {{
                    // Mostrar artistas que contribuyen al gÃ©nero
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{value}} reproducciones</span>
                    </div>`;
                    if (details.length > 0) {{
                        content += '<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">Top Artistas:</h4>';
                        details.slice(0, 5).forEach(artist => {{
                            content += `<div class="popup-item">
                                <span class="name">${{artist.name}}</span>
                                <span class="count">${{artist.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }} else if (category === 'Sellos') {{
                    // Mostrar artistas que contribuyen al sello
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{value}} reproducciones</span>
                    </div>`;
                    if (details.length > 0) {{
                        content += '<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">Top Artistas:</h4>';
                        details.slice(0, 5).forEach(artist => {{
                            content += `<div class="popup-item">
                                <span class="name">${{artist.name}}</span>
                                <span class="count">${{artist.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }} else if (category === 'Artistas con Mayor Streak') {{
                    // Mostrar datos de días
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{details.days}} dÃ­as de escucha</span>
                    </div>
                    <div class="popup-item">
                        <span class="name">Streak mÃ¡ximo general</span>
                        <span class="count">${{details.max_streak}} dÃ­as consecutivos</span>
                    </div>`;
                }} else if (category === 'Artistas con Mayor DiscografÃ­a') {{
                    // Mostrar nÃºmero de canciones y Ã¡lbumes
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{details.track_count}} canciones ÃºÃ­as</span>
                    </div>`;
                    if (details.albums && details.albums.length > 0) {{
                        content += '<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">Top 10 ÃƒÂlbumes:</h4>';
                        details.albums.forEach(album => {{
                            content += `<div class="popup-item">
                                <span class="name">${{album.name}}</span>
                                <span class="count">${{album.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }} else if (category === 'Artistas en Ascenso' || category === 'Artistas en Declive') {{
                    // Mostrar top 10 canciones
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{value}} reproducciones</span>
                    </div>`;
                    if (details && details.length > 0) {{
                        content += '<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">Top 10 Canciones:</h4>';
                        details.forEach(track => {{
                            content += `<div class="popup-item">
                                <span class="name">${{track.name}}</span>
                                <span class="count">${{track.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }} else {{
                    // Fallback para otras categorÃ­as
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{value}} ${{category.includes('DÃ­as') ? 'dÃ­as' : category.includes('Canciones') ? 'canciones' : 'reproducciones'}}</span>
                    </div>`;
                }}
            }} else {{
                // Fallback si no hay detalles
                content = `<div class="popup-item">
                    <span class="name">${{item}} en ${{year}}</span>
                    <span class="count">${{value}} ${{category.includes('DÃ­as') ? 'dÃ­as' : category.includes('Canciones') ? 'canciones' : 'reproducciones'}}</span>
                </div>`;
            }}

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function showEvolutionPopup(dataType, item, year, value) {{
            const title = `${{dataType.charAt(0).toUpperCase() + dataType.slice(1)}} - ${{item}} (${{year}})`;
            const content = `<div class="popup-item">
                <span class="name">${{item}} en ${{year}}</span>
                <span class="count">${{value}} ${{dataType.includes('coincidencias') ? 'coincidencias' : 'reproducciones'}}</span>
            </div>`;

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        // Siguiendo el patrÃƒÂ³n de html_anual.py: eventos directos al final
        userSelect.addEventListener('change', function() {{
            selectUser(this.value);
        }});

        // Seleccionar primer usuario automÃƒÂ¡ticamente si hay usuarios
        if (users.length > 0) {{
            selectUser(users[0]);
        }}
    </script>
</body>
</html>"""

    def _format_number(self, number: int) -> str:
        """Formatea nÃƒÂºmeros con separadores de miles"""
        return f"{number:,}".replace(",", ".")
