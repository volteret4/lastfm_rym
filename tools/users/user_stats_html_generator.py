#!/usr/bin/env python3
"""
UserStatsHTMLGenerator - Clase para generar HTML con gráficos interactivos de estadísticas de usuarios
"""

import json
from typing import Dict, List
import os

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
        icons_env = os.getenv('LASTFM_USERS_ICONS', '')
        user_icons = {}
        if icons_env:
            for pair in icons_env.split(','):
                if ':' in pair:
                    user, icon = pair.split(':', 1)
                    user_icons[user.strip()] = icon.strip()

        user_icons_json = json.dumps(user_icons, ensure_ascii=False)
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
            grid-template-columns: repeat(2, 1fr);
            gap: 25px;
            margin-bottom: 30px;
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
                <h1> RYM Hispano Estadísticas</h1>
                <div class="nav-buttons">
                    <a href="esta-semana.html" class="nav-button">TEMPORALES</a>
                    <a href="index.html#grupo" class="nav-button">GRUPO</a>
                    <a href="index.html#about" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">ðŸ‘¤</button>
        </header>

        <!-- Modal de selección de usuario -->
        <div class="user-modal" id="userModal">
            <div class="user-modal-content">
                <button class="user-modal-close" id="userModalClose">X</button>
                <div class="user-modal-header">Seleccionar Usuario</div>
                <div class="user-options" id="userOptions">
                    <!-- Se llenarán dinámicamente -->
                </div>
            </div>
        </div>

        <div class="controls">
            <div class="control-group">
                <label>Vista:</label>
                <div class="view-buttons">
                    <button class="view-btn active" data-view="individual">YoMiMeConMigo</button>
                    <button class="view-btn" data-view="genres">Géneros</button>
                    <button class="view-btn" data-view="labels">Sellos</button>
                    <button class="view-btn" data-view="coincidences">Coincidencias</button>
                    <button class="view-btn" data-view="evolution">Evolución</button>
                </div>
            </div>
        </div>

        <div class="stats-container">
            <!-- Vista Individual (YoMiMeConMigo) -->
            <div id="individualView" class="view active">
                <div class="data-type-buttons">
                    <button class="data-type-btn active" data-type="annual">Por Año</button>
                    <button class="data-type-btn" data-type="cumulative">Acumulativo</button>
                </div>

                <div class="evolution-section">
                    <h3>ðŸŽ­ Evolución de Géneros Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualGenresChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Evolución de Sellos Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualLabelsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Evolución de Artistas Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>One Hit Wonders</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con 1 Canción (+25 scrobbles)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualOneHitChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Artistas con Mayor Streak</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con Más Días Consecutivos</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualStreakChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Artistas con Mayor Discografía</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas con Más Canciones únicas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualTrackCountChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Artistas Nuevos</h3>
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
                    <h3>Artistas en Ascenso</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas que Más Rápido Subieron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualRisingChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Artistas en Declive</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Artistas que Más Rápido Bajaron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualFallingChart"></canvas>
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
                    <h3>ðŸŽ¶ Distribución de Géneros (Artistas)</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Géneros del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="genresPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ“ˆ Evolución de Artistas por Género</h3>
                    <div class="scatter-charts-grid" id="genresScatterGrid">
                        <!-- Se llenarán dinámicamente los 6 gráficos de scatter -->
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ’¿ Distribución de Géneros (Álbumes)</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Géneros de Álbumes del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="albumGenresPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumGenresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ“ˆ Evolución de Álbumes por Género</h3>
                    <div class="scatter-charts-grid" id="albumGenresScatterGrid">
                        <!-- Se llenarán dinámicamente los 6 gráficos de scatter para álbumes -->
                    </div>
                </div>
            </div>

            <!-- Vista de Sellos -->
            <div id="labelsView" class="view">
                <div class="genres-section">
                    <h3>ðŸ·ï¸ Distribución de Sellos</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Sellos del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="labelsPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ“ˆ Evolución de Artistas por Sello</h3>
                    <div class="scatter-charts-grid" id="labelsScatterGrid">
                        <!-- Se llenarán dinámicamente los 6 gráficos de scatter para sellos -->
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
                        <h3>Álbumes</h3>
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
                        <h3>Géneros (Individual)</h3>
                        <div class="chart-wrapper">
                            <canvas id="genresChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Géneros (Coincidencias)</h3>
                        <div class="chart-wrapper">
                            <canvas id="genreCoincidencesChart"></canvas>
                        </div>
                        <div class="chart-info" id="genreCoincidencesInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Sellos Discográficos</h3>
                        <div class="chart-wrapper">
                            <canvas id="labelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Años de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="releaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="releaseYearsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 10 Artistas por Escuchas</h3>
                        <div class="chart-wrapper">
                            <canvas id="topScrobblesChart"></canvas>
                        </div>
                        <div class="chart-info" id="topScrobblesInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Vuelve a Casa</h3>
                        <div class="chart-wrapper">
                            <canvas id="topDaysChart"></canvas>
                        </div>
                        <div class="chart-info" id="topDaysInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Discografía Completada</h3>
                        <div class="chart-wrapper">
                            <canvas id="topDiscographyChart"></canvas>
                        </div>
                        <div class="chart-info" id="topDiscographyInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Streaks</h3>
                        <div class="chart-wrapper">
                            <canvas id="topStreaksChart"></canvas>
                        </div>
                        <div class="chart-info" id="topStreaksInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de Evolución -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>Evolución de Géneros (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="genresEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Evolución de Sellos (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="labelsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Evolución de Años de Lanzamiento (Coincidencias)</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Años de Lanzamiento por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="releaseYearsEvolutionChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>Evolución de Coincidencias Básicas</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Coincidencias en Artistas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="artistsEvolutionChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Coincidencias en Álbumes</h4>
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

            <!-- Resumen de estadísticas -->
            <div id="summaryStats" class="summary-stats">
                <!-- Se llenará dinámicamente -->
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
        const userIcons = {user_icons_json};

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

                // Añadir icono si existe
                const icon = userIcons[user];
                if (icon) {{
                    if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg') || icon.endsWith('.jpeg') || icon.endsWith('.gif')) {{
                        option.innerHTML = `<img src="${icon}" alt="${user}" style="width:24px;height:24px;border-radius:50%;margin-right:12px;object-fit:cover;"> ${user}`;
                    }} else {{
                        option.innerHTML = `<span style="font-size:16px;margin-right:12px;">${icon}</span> ${user}`;
                    }}
                }} else {{
                    option.textContent = user;
                }}

                userOptions.appendChild(option);
            }});

            updateSelectedUserOption(selectedUser);
            updateUserButtonIcon(selectedUser);

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
                const option = e.target.closest('.user-option');
                if (!option) return;

                const user = option.dataset.user;

                selectedUser = user;

                if (user) {{
                    localStorage.setItem('lastfm_selected_user', user);
                }} else {{
                    localStorage.removeItem('lastfm_selected_user');
                }}

                updateSelectedUserOption(user);
                updateUserButtonIcon(user);
                userModal.style.display = 'none';

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

        function updateUserButtonIcon(user) {{
            const userButton = document.getElementById('userButton');
            const icon = userIcons[user];

            if (icon) {{
                if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg') || icon.endsWith('.jpeg') || icon.endsWith('.gif')) {{
                    userButton.innerHTML = `<img src="${icon}" alt="${user}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;">`;
                }} else {{
                    userButton.textContent = icon;
                }}
            }} else {{
                userButton.textContent = '👤';
            }}
        }}
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
                }} else if (view === 'labels') {{
                    renderLabelsCharts(userStats);
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

            updateSummaryStats(userStats);

            if (currentView === 'individual') {{
                renderIndividualCharts(userStats);
            }} else if (currentView === 'genres') {{
                renderGenresCharts(userStats);
            }} else if (currentView === 'labels') {{
                renderLabelsCharts(userStats);
            }} else if (currentView === 'coincidences') {{
                renderCoincidenceCharts(userStats);
            }} else if (currentView === 'evolution') {{
                renderEvolutionCharts(userStats);
            }}
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
                    <div class="label">Usuarios (Álbumes)</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">Géneros</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalReleaseYears}}</div>
                    <div class="label">Décadas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalLabels}}</div>
                    <div class="label">Sellos</div>
                </div>
            `;

            document.getElementById('summaryStats').innerHTML = summaryHTML;
        }}

        function renderGenresCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            const genresData = userStats.genres;
            if (!genresData || !genresData[currentProvider]) {{
                // Mostrar mensaje de no datos
                showNoGenresData();
                return;
            }}

            const providerData = genresData[currentProvider];

            // 1. Gráfico circular con top 15 géneros de artistas
            renderGenresPieChart(providerData.pie_chart, 'genresPieChart', 'genresPieInfo', 'Artistas');

            // 2. 6 gráficos de scatter para top 6 géneros de artistas
            renderGenresScatterCharts(providerData.scatter_charts, providerData.years, 'genresScatterGrid', false);

            // 3. Gráfico circular con top 15 géneros de álbumes (SOLO SI EXISTEN DATOS)
            if (providerData.album_pie_chart && providerData.album_pie_chart.data && Object.keys(providerData.album_pie_chart.data).length > 0) {{
                renderGenresPieChart(providerData.album_pie_chart, 'albumGenresPieChart', 'albumGenresPieInfo', 'Álbumes');

                // 4. 6 gráficos de scatter para top 6 géneros de álbumes (SOLO SI EXISTEN DATOS)
                if (providerData.album_scatter_charts && Object.keys(providerData.album_scatter_charts).length > 0) {{
                    renderGenresScatterCharts(providerData.album_scatter_charts, providerData.years, 'albumGenresScatterGrid', true);
                }} else {{
                    document.getElementById('albumGenresScatterGrid').innerHTML = '<div class="no-data">No hay datos de evolución de álbumes por género para ' + currentProvider + '</div>';
                }}
            }} else {{
                // Ocultar secciones de álbumes si no hay datos
                const albumGenresSection = document.querySelector('h3').nextElementSibling;
                if (albumGenresSection) {{
                    albumGenresSection.style.display = 'none';
                }}
                document.getElementById('albumGenresPieChart').style.display = 'none';
                document.getElementById('albumGenresPieInfo').innerHTML = '<div class="no-data">No hay datos de géneros de álbumes para ' + currentProvider + '</div>';
                document.getElementById('albumGenresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter de álbumes para ' + currentProvider + '</div>';
            }}
        }}

        function showNoGenresData() {{
            document.getElementById('genresPieChart').style.display = 'none';
            document.getElementById('genresPieInfo').innerHTML = '<div class="no-data">No hay datos disponibles para ' + currentProvider + '</div>';
            document.getElementById('albumGenresPieChart').style.display = 'none';
            document.getElementById('albumGenresPieInfo').innerHTML = '<div class="no-data">No hay datos disponibles para ' + currentProvider + '</div>';
            document.getElementById('genresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter disponibles</div>';
            document.getElementById('albumGenresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter disponibles</div>';
        }}

        function renderLabelsCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            const labelsData = userStats.labels;
            if (!labelsData) {{
                console.log('No hay datos de sellos disponibles');
                return;
            }}

            // 1. Gráfico circular con top 15 sellos
            renderGenresPieChart(labelsData.pie_chart, 'labelsPieChart', 'labelsPieInfo', 'Sellos');

            // 2. 6 gráficos de scatter para top 6 sellos
            renderLabelsScatterCharts(labelsData.scatter_charts, labelsData.years, 'labelsScatterGrid');
        }}

        function renderGenresPieChart(pieData, canvasId, infoId, type) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!canvas || !info) {{
                console.error(`No se encontró el canvas o info para ${{canvasId}}`);
                return;
            }}

            if (!pieData || !pieData.data || Object.keys(pieData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';
            const provider = type === 'Sellos' ? 'Sellos Discográficos' : `${{currentProvider}} (${{type}})`;
            info.innerHTML = `Total: ${{pieData.total.toLocaleString()}} scrobbles | Tipo: ${{provider}}`;

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

            charts[canvasId] = new Chart(canvas, config);
        }}

        function renderGenresScatterCharts(scatterData, years, containerId, isAlbums = false) {{
            const container = document.getElementById(containerId);
            if (!container) {{
                console.error(`No se encontró el contenedor ${{containerId}}`);
                return;
            }}

            container.innerHTML = '';

            if (!scatterData || Object.keys(scatterData).length === 0) {{
                container.innerHTML = '<div class="no-data">No hay datos de scatter disponibles</div>';
                return;
            }}

            Object.keys(scatterData).forEach((genre, index) => {{
                const items = scatterData[genre];

                if (!items || items.length === 0) return;

                // Crear contenedor para este género
                const genreContainer = document.createElement('div');
                genreContainer.className = 'genres-pie-container';

                const title = document.createElement('h4');
                const itemType = isAlbums ? 'Álbumes' : 'Artistas';
                title.textContent = `${{genre}} - Top ${{items.length}} ${{itemType}}`;
                title.style.color = '#cba6f7';
                title.style.textAlign = 'center';
                title.style.marginBottom = '15px';
                genreContainer.appendChild(title);

                const canvasWrapper = document.createElement('div');
                canvasWrapper.className = 'chart-wrapper';
                canvasWrapper.style.height = '300px';

                const canvas = document.createElement('canvas');
                const canvasId = `scatterChart_${{genre.replace(/[^a-zA-Z0-9]/g, '_')}}_${{index}}_${{containerId}}`;
                canvas.id = canvasId;
                canvasWrapper.appendChild(canvas);

                genreContainer.appendChild(canvasWrapper);
                container.appendChild(genreContainer);

                // Crear dataset para scatter plot
                const datasets = [];

                items.forEach((itemData, itemIndex) => {{
                    const points = [];

                    years.forEach(year => {{
                        const plays = itemData.yearly_data[year] || 0;
                        if (plays > 0) {{
                            points.push({{
                                x: year,
                                y: plays,
                                itemName: isAlbums ? itemData.album : itemData.artist
                            }});
                        }}
                    }});

                    if (points.length > 0) {{
                        datasets.push({{
                            label: isAlbums ? itemData.album : itemData.artist,
                            data: points,
                            backgroundColor: colors[itemIndex % colors.length],
                            borderColor: colors[itemIndex % colors.length],
                            pointRadius: 6,
                            pointHoverRadius: 10,
                            showLine: false
                        }});
                    }}
                }});

                if (datasets.length === 0) {{
                    canvas.parentElement.innerHTML = '<div class="no-data">No hay datos temporales para este género</div>';
                    return;
                }}

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
                                min: Math.min(...years) - 0.8,
                                max: Math.max(...years) + 0.8
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
                                display: true,
                                position: 'bottom',
                                labels: {{
                                    color: '#cdd6f4',
                                    padding: 12,
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    font: {{
                                        size: 11
                                    }},
                                    boxHeight: 10,
                                    boxWidth: 10,
                                    maxWidth: 100,
                                    textAlign: 'left'
                                }}
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
                                        return point.itemName;
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
                                const itemType = isAlbums ? 'Álbum' : 'Artista';
                                showArtistPopup(point.itemName, genre, currentProvider, point.x, point.y, itemType);
                            }}
                        }}
                    }}
                }};

                charts[canvasId] = new Chart(canvas, config);
            }});
        }}

        function renderLabelsScatterCharts(scatterData, years, containerId) {{
            const container = document.getElementById(containerId);
            if (!container) {{
                console.error(`No se encontró el contenedor ${{containerId}}`);
                return;
            }}

            container.innerHTML = '';

            if (!scatterData || Object.keys(scatterData).length === 0) {{
                container.innerHTML = '<div class="no-data">No hay datos de sellos disponibles</div>';
                return;
            }}

            Object.keys(scatterData).forEach((label, index) => {{
                const artists = scatterData[label];

                if (!artists || artists.length === 0) return;

                // Crear contenedor para este sello
                const labelContainer = document.createElement('div');
                labelContainer.className = 'genres-pie-container';

                const title = document.createElement('h4');
                title.textContent = `${{label}} - Top ${{artists.length}} Artistas`;
                title.style.color = '#cba6f7';
                title.style.textAlign = 'center';
                title.style.marginBottom = '15px';
                labelContainer.appendChild(title);

                const canvasWrapper = document.createElement('div');
                canvasWrapper.className = 'chart-wrapper';
                canvasWrapper.style.height = '300px';

                const canvas = document.createElement('canvas');
                const canvasId = `labelScatterChart_${{label.replace(/[^a-zA-Z0-9]/g, '_')}}_${{index}}`;
                canvas.id = canvasId;
                canvasWrapper.appendChild(canvas);

                labelContainer.appendChild(canvasWrapper);
                container.appendChild(labelContainer);

                // Crear dataset para scatter plot
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
                            pointRadius: 6,
                            pointHoverRadius: 10,
                            showLine: false
                        }});
                    }}
                }});

                if (datasets.length === 0) {{
                    canvas.parentElement.innerHTML = '<div class="no-data">No hay datos temporales para este sello</div>';
                    return;
                }}

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
                                min: Math.min(...years) - 0.8,
                                max: Math.max(...years) + 0.8
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
                                display: true,
                                position: 'bottom',
                                labels: {{
                                    color: '#cdd6f4',
                                    padding: 12,
                                    usePointStyle: true,
                                    pointStyle: 'circle',
                                    font: {{
                                        size: 11
                                    }},
                                    boxHeight: 10,
                                    boxWidth: 10,
                                    maxWidth: 100,
                                    textAlign: 'left'
                                }}
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
                                showArtistPopup(point.artistName, label, 'Sello', point.x, point.y, 'Artista');
                            }}
                        }}
                    }}
                }};

                charts[canvasId] = new Chart(canvas, config);
            }});
        }}

        function renderGenresScatterChartsOld(scatterData, years) {{
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

        function showArtistPopup(itemName, category, provider, year, scrobbles, itemType = 'Artista') {{
            const title = `${{itemName}} - ${{category}} (${{year}})`;
            const content = `
                <div class="popup-item">
                    <span class="name">${{itemType}}: ${{itemName}}</span>
                </div>
                <div class="popup-item">
                    <span class="name">${{provider === 'Sello' ? 'Sello' : 'Género'}}: ${{category}}</span>
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
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Seleccionar datos según el tipo actual
            const individualData = currentDataType === 'annual' ? userStats.individual.annual : userStats.individual.cumulative;

            // Renderizar todos los gráficos individuales
            if (individualData) {{
                renderIndividualLineChart('individualGenresChart', individualData.genres, 'Géneros');
                renderIndividualLineChart('individualLabelsChart', individualData.labels, 'Sellos');
                renderIndividualLineChart('individualArtistsChart', individualData.artists, 'Artistas');
                renderIndividualLineChart('individualOneHitChart', individualData.one_hit_wonders, 'One Hit Wonders');
                renderIndividualLineChart('individualStreakChart', individualData.streak_artists, 'Artistas con Mayor Streak');
                renderIndividualLineChart('individualTrackCountChart', individualData.track_count_artists, 'Artistas con Mayor Discografía');
                renderIndividualLineChart('individualNewArtistsChart', individualData.new_artists, 'Artistas Nuevos');
                renderIndividualLineChart('individualRisingChart', individualData.rising_artists, 'Artistas en Ascenso');
                renderIndividualLineChart('individualFallingChart', individualData.falling_artists, 'Artistas en Declive');
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
                                                return [`Artista: ${{details.artist}}`, `Canción: ${{details.track}}`];
                                            }} else if (title === 'Artistas con Mayor Streak' && details.days !== undefined) {{
                                                return [`Días en ${{year}}: ${{details.days}}`];
                                            }} else if (title === 'Artistas con Mayor Discografía' && details.track_count !== undefined) {{
                                                return [`Canciones únicas: ${{details.track_count}}`];
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
                                text: title === 'Artistas con Mayor Streak' ? (currentDataType === 'cumulative' ? 'Días acumulados' : 'Días') :
                                      title === 'Artistas con Mayor Discografía' ? (currentDataType === 'cumulative' ? 'Canciones únicas acumuladas' : 'Canciones únicas') :
                                      currentDataType === 'cumulative' ? 'Reproducciones acumuladas' : 'Reproducciones',
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
                    content = `<div class="popup-item">
                        <span class="name">Artista: ${{details.artist}}</span>
                    </div>
                    <div class="popup-item">
                        <span class="name">Canción: ${{details.track}}</span>
                        <span class="count">${{details.plays}} reproducciones</span>
                    </div>`;
                }} else if (category === 'Géneros') {{
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
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{details.days}} días de escucha</span>
                    </div>
                    <div class="popup-item">
                        <span class="name">Streak máximo general</span>
                        <span class="count">${{details.max_streak}} días consecutivos</span>
                    </div>`;
                }} else if (category === 'Artistas con Mayor Discografía') {{
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{details.track_count}} canciones únicas</span>
                    </div>`;
                    if (details.albums && details.albums.length > 0) {{
                        content += '<h4 style="color: #cba6f7; margin: 10px 0 5px 0;">Top 10 Álbumes:</h4>';
                        details.albums.forEach(album => {{
                            content += `<div class="popup-item">
                                <span class="name">${{album.name}}</span>
                                <span class="count">${{album.plays}} plays</span>
                            </div>`;
                        }});
                    }}
                }} else if (category === 'Artistas en Ascenso' || category === 'Artistas en Declive') {{
                    const playText = currentDataType === 'cumulative' ? 'reproducciones acumuladas' : 'reproducciones';
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{value}} ${{playText}}</span>
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
                    content = `<div class="popup-item">
                        <span class="name">${{item}} en ${{year}}</span>
                        <span class="count">${{value}} ${{category.includes('Días') ? 'días' : category.includes('Canciones') ? 'canciones' : 'reproducciones'}}</span>
                    </div>`;
                }}
            }} else {{
                content = `<div class="popup-item">
                    <span class="name">${{item}} en ${{year}}</span>
                    <span class="count">${{value}} ${{category.includes('Días') ? 'días' : category.includes('Canciones') ? 'canciones' : 'reproducciones'}}</span>
                </div>`;
            }}

            document.getElementById('popupTitle').textContent = title;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        function renderCoincidenceCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Gráficos básicos
            renderPieChart('artistsChart', userStats.coincidences.charts.artists, 'artistsInfo');
            renderPieChart('albumsChart', userStats.coincidences.charts.albums, 'albumsInfo');
            renderPieChart('tracksChart', userStats.coincidences.charts.tracks, 'tracksInfo');
            renderPieChart('genresChart', userStats.coincidences.charts.genres, 'genresInfo');

            // Nuevos gráficos de coincidencias
            renderPieChart('genreCoincidencesChart', userStats.coincidences.charts.genre_coincidences, 'genreCoincidencesInfo');
            renderPieChart('labelsChart', userStats.coincidences.charts.labels, 'labelsInfo');
            renderPieChart('releaseYearsChart', userStats.coincidences.charts.release_years, 'releaseYearsInfo');

            // Gráficos especiales
            renderPieChart('topScrobblesChart', userStats.coincidences.charts.top_scrobbles, 'topScrobblesInfo');
            renderPieChart('topDaysChart', userStats.coincidences.charts.top_days, 'topDaysInfo');
            renderPieChart('topDiscographyChart', userStats.coincidences.charts.top_discography, 'topDiscographyInfo');
            renderPieChart('topStreaksChart', userStats.coincidences.charts.top_streaks, 'topStreaksInfo');
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
            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}} | Click en una porción para ver detalles`;

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
                title = `Top Álbumes - ${{selectedLabel}}`;
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
                title = `Top Canciones - ${{selectedLabel}}`;
                Object.keys(details).slice(0, 5).forEach(track => {{
                    const trackData = details[track];
                    content += `<div class="popup-item">
                        <span class="name">${{track}}</span>
                        <span class="count">${{trackData.user_plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'genres') {{
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'years_labels') {{
                title = `Top Artistas - ${{selectedLabel}}`;
                details.forEach(artist => {{
                    content += `<div class="popup-item">
                        <span class="name">${{artist.name}}</span>
                        <span class="count">${{artist.plays}} plays</span>
                    </div>`;
                }});
            }} else if (chartType === 'top_scrobbles') {{
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
                title = `Artistas "Vuelve a Casa" - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">${{artistData.user_days + artistData.other_days}} días totales</span>
                        </div>`;
                    }});
                }}
            }} else if (chartType === 'top_discography') {{
                title = `Discografía Completada - ${{selectedLabel}}`;
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
                title = `Streaks Coincidentes - ${{selectedLabel}}`;
                if (details.artists) {{
                    Object.keys(details.artists).forEach(artist => {{
                        const artistData = details.artists[artist];
                        content += `<div class="popup-item">
                            <span class="name">${{artist}}</span>
                            <span class="count">Max: ${{Math.max(artistData.user_streak, artistData.other_streak)}} días</span>
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

        function renderCoincidencesEvolution(type, evolutionData) {{
            let canvas, chartId;

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
                                               type === 'albums' ? 'Álbumes' :
                                               type === 'tracks' ? 'Canciones' :
                                               type === 'genres' ? 'Géneros' :
                                               type === 'labels' ? 'Sellos' :
                                               type === 'release_years' ? 'Décadas' : type;

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
                if (item.artist) {{
                    content += `<div class="popup-item">
                        <div style="margin-bottom: 5px;">
                            <span class="name" style="font-weight: bold;">${{item.artist}}</span>
                        </div>`;

                    if (item.track) {{
                        content += `<div style="margin-left: 10px; color: #a6adc8;">
                            ðŸŽµ ${{item.track}}
                        </div>`;
                    }}

                    if (item.album) {{
                        content += `<div style="margin-left: 10px; color: #a6adc8;">
                            ðŸ’¿ ${{item.album}}
                        </div>`;
                    }}

                    if (item.user1_plays && item.user2_plays) {{
                        content += `<div style="margin-left: 10px; font-size: 0.9em; color: #6c7086;">
                            Usuario 1: ${{item.user1_plays}} plays | Usuario 2: ${{item.user2_plays}} plays
                        </div>`;
                    }}

                    content += `</div>`;
                }} else {{
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

        // Configurar cierre de popup
        document.getElementById('popupClose').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        document.getElementById('popupOverlay').addEventListener('click', function() {{
            document.getElementById('popupOverlay').style.display = 'none';
            document.getElementById('popup').style.display = 'none';
        }});

        // Inicializar
        const initialUser = initializeUserSelector();
        if (initialUser && users.includes(initialUser)) {{
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
