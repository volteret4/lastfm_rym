#!/usr/bin/env python3
"""
UserStatsHTMLGeneratorFixed - Clase para generar HTML con grÃ¡ficos interactivos de estadÃ­sticas de usuarios
FIXES:
- Corrige el enlace del botÃ³n TEMPORALES para que apunte a index.html#temporal
- Arregla la inicializaciÃ³n de genresData para mostrar los grÃ¡ficos de gÃ©neros
- Restaura funciones completas para scatter charts y grÃ¡ficos de evoluciÃ³n
"""

import json
import os
from typing import Dict, List


class UserStatsHTMLGeneratorFixed:
    """Clase para generar HTML con grÃ¡ficos interactivos de estadÃ­sticas de usuarios - CORREGIDA"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera el HTML completo para estadÃ­sticas de usuarios"""
        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(all_user_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        # âœ… FIX: AÃ±adir soporte para iconos de usuario
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
    <title>Last.fm Usuarios - EstadÃ­sticas Individuales</title>
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
            background: #45475a;
            border-color: #cba6f7;
        }}

        .user-option.selected {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
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

        .nav-tab.active::after {{
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            right: 0;
            height: 2px;
            background: #181825;
        }}

        .user-header {{
            background: linear-gradient(135deg, #1e1e2e, #181825);
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }}

        .user-name {{
            font-size: 1.4em;
            color: #cba6f7;
            font-weight: regular;
            margin-bottom: 15px;
        }}

        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 10px;
            max-width: 700px;
            margin: 0 auto;
        }}

        .summary-card {{
            background: rgba(203, 166, 247, 0.1);
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid rgba(203, 166, 247, 0.3);
        }}

        .summary-card .number {{
            font-size: 1.2em;
            font-weight: bold;
            color: #cba6f7;
            margin-bottom: 2px;
        }}

        .summary-card .label {{
            font-size: 0.8em;
            color: #a6adc8;
            text-transform: uppercase;
        }}

        .tab-content {{
            display: none;
        }}

        .tab-content.active {{
            display: block;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
        }}

        .chart-card {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 2px solid #313244;
            transition: border-color 0.3s;
        }}

        .chart-card:hover {{
            border-color: #cba6f7;
        }}

        .chart-header {{
            margin-bottom: 15px;
        }}

        .chart-title {{
            font-size: 1.2em;
            color: #cba6f7;
            margin-bottom: 8px;
            font-weight: 600;
        }}

        .chart-info {{
            font-size: 0.9em;
            color: #a6adc8;
            padding: 8px 12px;
            background: #313244;
            border-radius: 6px;
            margin-top: 10px;
        }}

        .chart-wrapper {{
            width: 100%;
            height: 300px;
            position: relative;
        }}

        .scatter-chart-wrapper {{
            width: 100%;
            height: 250px;
            position: relative;
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

        .provider-buttons {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .provider-btn {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 500;
        }}

        .provider-btn:hover {{
            background: #45475a;
            border-color: #cba6f7;
        }}

        .provider-btn.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .genres-section {{
            margin-bottom: 40px;
        }}

        .genres-section h3 {{
            color: #cba6f7;
            margin-bottom: 20px;
            font-size: 1.3em;
            text-align: center;
        }}

        .genres-pie-container {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 25px;
            border: 2px solid #313244;
        }}

        .genres-pie-container h4 {{
            color: #fab387;
            margin-bottom: 15px;
            text-align: center;
            font-size: 1.1em;
        }}

        .scatter-charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .scatter-chart-card {{
            background: #1e1e2e;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #313244;
        }}

        .scatter-chart-card h5 {{
            color: #cba6f7;
            font-size: 1em;
            margin-bottom: 10px;
            text-align: center;
            font-weight: 600;
        }}

        .evolution-charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 25px;
        }}

        .data-type-buttons {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .data-type-btn {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
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

        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 999;
            backdrop-filter: blur(5px);
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
            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            .scatter-charts-grid {{
                grid-template-columns: 1fr;
            }}

            .evolution-charts {{
                grid-template-columns: 1fr;
            }}

            .summary-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .nav-tabs {{
                justify-content: center;
            }}

            .provider-buttons {{
                flex-direction: column;
                align-items: center;
            }}

            h1 {{
                font-size: 1.5em;
            }}

            .user-name {{
                font-size: 1.5em;
            }}

            .popup {{
                width: 90%;
                max-width: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>ðŸŽµ RYM Hispano EstadÃ­sticas</h1>
                <div class="nav-buttons">
                    <a href="index.html#temporal" class="nav-button">TEMPORALES</a>
                    <a href="index.html#grupo" class="nav-button">GRUPO</a>
                    <a href="index.html#about" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">ðŸ‘¤</button>
        </header>

        <div id="userModal" class="user-modal">
            <div class="user-modal-content">
                <button class="user-modal-close" id="closeModal">&times;</button>
                <div class="user-modal-header">Seleccionar Usuario</div>
                <div class="user-options" id="userOptions">
                    <!-- Se llenarÃ¡n dinÃ¡micamente -->
                </div>
            </div>
        </div>

        <div class="content">
            <div class="user-header">
                <div class="user-name" id="currentUserName">Selecciona un usuario</div>
                <div class="summary-stats" id="summaryStats">
                    <!-- Se llenarÃ¡n dinÃ¡micamente -->
                </div>
            </div>

            <div class="nav-tabs">
                <div class="nav-tab active" data-view="individual">ðŸ“Š Individual</div>
                <div class="nav-tab" data-view="genres">ðŸŽµ GÃ©neros</div>
                <div class="nav-tab" data-view="labels">ðŸ’¿ Sellos</div>
                <div class="nav-tab" data-view="coincidences">ðŸ¤ Coincidencias</div>
                <div class="nav-tab" data-view="evolution">ðŸ“ˆ EvoluciÃ³n</div>


                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ‘¥ Top Artistas</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="topArtistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="topArtistsInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ’¿ Top Ãlbumes</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="topAlbumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="topAlbumsInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸŽ¶ Top Canciones</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="topTracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="topTracksInfo"></div>
                    </div>
                </div>

                <!-- SecciÃ³n de evoluciÃ³n individual -->
                <div class="evolution-section">
                    <h3>ðŸŽ­ EvoluciÃ³n de GÃ©neros Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 GÃ©neros por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualGenresChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸ·ï¸ EvoluciÃ³n de Sellos Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Sellos por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualLabelsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸŽ¤ EvoluciÃ³n de Artistas Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸŽ¯ One Hit Wonders</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas con 1 CanciÃ³n (+25 scrobbles)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualOneHitChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸ”¥ Artistas con Mayor Streak</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas con MÃ¡s DÃ­as Consecutivos</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualStreakChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸ“š Artistas con Mayor DiscografÃ­a</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas con MÃ¡s Canciones Ãšnicas</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualTrackCountChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>âœ¨ Artistas Nuevos</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas Nuevos (Sin Escuchas Previas)</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualNewArtistsChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸ“ˆ Artistas en Ascenso</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas que MÃ¡s RÃ¡pido Subieron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualRisingChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>ðŸ“‰ Artistas en Declive</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas que MÃ¡s RÃ¡pido Bajaron</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="individualFallingChart"></canvas>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
            </div>

            <div id="genresTab" class="tab-content">
                <div class="provider-buttons">
                    <button class="provider-btn active" data-provider="lastfm">Last.fm</button>
                    <button class="provider-btn" data-provider="musicbrainz">MusicBrainz</button>
                    <button class="provider-btn" data-provider="discogs">Discogs</button>
                </div>

                <div class="genres-section">
                    <h3>ðŸŽ¶ DistribuciÃ³n de GÃ©neros (Artistas)</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 GÃ©neros del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="genresPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ“ˆ EvoluciÃ³n de Artistas por GÃ©nero</h3>
                    <div class="scatter-charts-grid" id="genresScatterGrid">
                        <!-- Se llenarÃ¡n dinÃ¡micamente los 6 grÃ¡ficos de scatter -->
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ’¿ DistribuciÃ³n de GÃ©neros (Ãlbumes)</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 GÃ©neros de Ã¡lbumes del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="albumGenresPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumGenresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ“ˆ EvoluciÃ³n de Ãlbumes por GÃ©nero</h3>
                    <div class="scatter-charts-grid" id="albumGenresScatterGrid">
                        <!-- Se llenarÃ¡n dinÃ¡micamente los 6 grÃ¡ficos de scatter para Ã¡lbumes -->
                    </div>
                </div>
            </div>

            <div id="labelsTab" class="tab-content">
                <div class="genres-section">
                    <h3>ðŸ’¿ DistribuciÃ³n de Sellos</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Sellos DiscogrÃ¡ficos del Usuario</h4>
                        <div class="chart-wrapper">
                            <canvas id="labelsPieChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>ðŸ“ˆ EvoluciÃ³n de Ãlbumes por Sello</h3>
                    <div class="scatter-charts-grid" id="labelsScatterGrid">
                        <!-- Se llenarÃ¡n dinÃ¡micamente los 6 grÃ¡ficos de scatter para sellos -->
                    </div>
                </div>
            </div>

            <div id="coincidencesTab" class="tab-content">
                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ‘¥ Coincidencias de Artistas</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="artistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="artistsInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ’¿ Coincidencias de Ãlbumes</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="albumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumsInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸŽ¶ Coincidencias de Canciones</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="tracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="tracksInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸŽµ Coincidencias de GÃ©neros</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="genresChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ”„ GÃ©neros Compartidos</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="genreCoincidencesChart"></canvas>
                        </div>
                        <div class="chart-info" id="genreCoincidencesInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ’¿ Coincidencias de Sellos</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="labelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ“… AÃ±os de Lanzamiento</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="releaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="releaseYearsInfo"></div>
                    </div>
                </div>
            </div>

            <div id="evolutionTab" class="tab-content">
                <div class="evolution-charts">
                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸŽµ EvoluciÃ³n de GÃ©neros</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="genresEvolutionChart"></canvas>
                        </div>
                        <div class="chart-info" id="genresEvolutionInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ’¿ EvoluciÃ³n de Sellos</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="labelsEvolutionChart"></canvas>
                        </div>
                        <div class="chart-info" id="labelsEvolutionInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ“… EvoluciÃ³n de AÃ±os</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="releaseYearsEvolutionChart"></canvas>
                        </div>
                        <div class="chart-info" id="releaseYearsEvolutionInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ‘¥ EvoluciÃ³n de Artistas</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="artistsEvolutionChart"></canvas>
                        </div>
                        <div class="chart-info" id="artistsEvolutionInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸ’¿ EvoluciÃ³n de Ãlbumes</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="albumsEvolutionChart"></canvas>
                        </div>
                        <div class="chart-info" id="albumsEvolutionInfo"></div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-header">
                            <h3 class="chart-title">ðŸŽ¶ EvoluciÃ³n de Canciones</h3>
                        </div>
                        <div class="chart-wrapper">
                            <canvas id="tracksEvolutionChart"></canvas>
                        </div>
                        <div class="chart-info" id="tracksEvolutionInfo"></div>
                    </div>
                </div>
            </div>

            <div id="discoveriesTab" class="tab-content">
                <div class="evolution-section">
                    <h3>✨ Descubrimientos Musicales</h3>

                    <div class="loading-spinner" id="discoveriesLoading" style="display: none; text-align: center; padding: 40px; color: #a6adc8;">
                        <p>🔄 Cargando datos de novedades...</p>
                    </div>

                    <div class="discoveries-grid" id="discoveriesGrid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px;">
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
        // Datos globales
        const allUsers = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};
        const userIcons = {user_icons_json}; // âœ… FIX: AÃ±adir iconos de usuario

        // Variables globales
        let currentUser = null;
        let currentView = 'individual';
        let currentProvider = 'lastfm';
        let currentDataType = 'annual';
        let charts = {{}};
        let genresData = null; // âœ… FIX: Inicializar variable global genresData
        let discoveriesData = {}; // Cache para datos de novedades

        // InicializaciÃ³n
        document.addEventListener('DOMContentLoaded', function() {{
            initializeApp();
        }});

        function initializeApp() {{
            setupUserModal();
            setupNavigation();
            setupProviderButtons();
            setupPopup();

            // âœ… FIX: Cargar usuario guardado o seleccionar el primero
            const savedUser = loadSavedUser();
            const userToSelect = savedUser || (allUsers.length > 0 ? allUsers[0] : null);

            if (userToSelect) {{
                selectUser(userToSelect);
                updateUserButtonIcon(userToSelect);
                updateSelectedUserOption(userToSelect);
            }}
        }}

        function setupUserModal() {{
            const userButton = document.getElementById('userButton');
            const userModal = document.getElementById('userModal');
            const closeModal = document.getElementById('closeModal');
            const userOptions = document.getElementById('userOptions');

            // Llenar opciones de usuarios con iconos
            userOptions.innerHTML = allUsers.map(user => {{
                const icon = userIcons[user];
                let optionHTML = `<div class="user-option" data-user="${{user}}">`;

                if (icon) {{
                    if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {{
                        optionHTML += `<img src="${{icon}}" alt="${{user}}" style="width:24px;height:24px;border-radius:50%;vertical-align:middle;margin-right:8px;"> ${{user}}`;
                    }} else {{
                        optionHTML += `<span style="font-size:1.2em;margin-right:8px;">${{icon}}</span> ${{user}}`;
                    }}
                }} else {{
                    optionHTML += user;
                }}

                optionHTML += '</div>';
                return optionHTML;
            }}).join('');

            // Event listeners
            userButton.addEventListener('click', () => {{
                userModal.style.display = 'block';
            }});

            closeModal.addEventListener('click', () => {{
                userModal.style.display = 'none';
            }});

            userModal.addEventListener('click', (e) => {{
                if (e.target === userModal) {{
                    userModal.style.display = 'none';
                }}
            }});

            userOptions.addEventListener('click', (e) => {{
                if (e.target.classList.contains('user-option')) {{
                    const username = e.target.dataset.user;
                    selectUser(username);
                    userModal.style.display = 'none';

                    // Guardar usuario seleccionado en localStorage
                    if (username) {{
                        localStorage.setItem('lastfm_selected_user', username);
                    }}

                    updateUserButtonIcon(username);
                    updateSelectedUserOption(username);
                }}
            }});
        }}

        function setupNavigation() {{
            const navTabs = document.querySelectorAll('.nav-tab');
            const tabContents = document.querySelectorAll('.tab-content');

            navTabs.forEach(tab => {{
                tab.addEventListener('click', () => {{
                    const view = tab.dataset.view;

                    // Actualizar pestaÃ±as activas
                    navTabs.forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');

                    // Mostrar contenido correspondiente
                    tabContents.forEach(content => {{
                        content.classList.remove('active');
                    }});

                    document.getElementById(view + 'Tab').classList.add('active');

                    currentView = view;

                    // Re-render para la nueva vista
                    if (currentUser) {{
                        if (view === 'discoveries') {{
                            loadDiscoveriesData(currentUser);
                        }} else {{
                            selectUser(currentUser);
                        }}
                    }}
                }});
            }});
        }}

        function setupProviderButtons() {{
            const providerBtns = document.querySelectorAll('.provider-btn');

            providerBtns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    const provider = btn.dataset.provider;

                    // Actualizar botones activos
                    providerBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    currentProvider = provider;

                    // âœ… FIX: Recalcular estadÃ­sticas principales al cambiar proveedor
                    if (currentUser) {{
                        updateSummaryStats(allStats[currentUser]);
                    }}

                    // Re-render grÃ¡ficos de gÃ©neros
                    if (currentUser && currentView === 'genres') {{
                        renderGenresCharts(allStats[currentUser]);
                    }}
                }});
            }});

            // âœ… FIX: Configurar botones de tipo de datos
            const dataTypeBtns = document.querySelectorAll('.data-type-btn');

            dataTypeBtns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    const dataType = btn.dataset.type;

                    // Actualizar botones activos
                    dataTypeBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');

                    currentDataType = dataType;

                    // Re-render grÃ¡ficos individuales
                    if (currentUser && currentView === 'individual') {{
                        renderIndividualCharts(allStats[currentUser]);
                    }}
                }});
            }});
        }}

        function setupPopup() {{
            // Configurar cierre de popup
            document.getElementById('popupClose').addEventListener('click', function() {{
                document.getElementById('popupOverlay').style.display = 'none';
                document.getElementById('popup').style.display = 'none';
            }});

            document.getElementById('popupOverlay').addEventListener('click', function() {{
                document.getElementById('popupOverlay').style.display = 'none';
                document.getElementById('popup').style.display = 'none';
            }});
        }}

        // âœ… FIX: Funciones para manejar iconos de usuario
        function updateUserButtonIcon(user) {{
            const userButton = document.getElementById('userButton');
            const icon = userIcons[user];
            if (icon) {{
                if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {{
                    userButton.innerHTML = `<img src="${{icon}}" alt="${{user}}" style="width:100%;height:100%;border-radius:50%;">`;
                }} else {{
                    userButton.textContent = icon;
                }}
            }} else {{
                userButton.textContent = 'ðŸ‘¤';
            }}
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

        function loadSavedUser() {{
            const savedUser = localStorage.getItem('lastfm_selected_user');
            if (savedUser && allUsers.includes(savedUser)) {{
                return savedUser;
            }}
            return null;
        }}

        function selectUser(username) {{
            currentUser = username;
            const userStats = allStats[username];

            if (!userStats) {{
                console.error('No stats found for user:', username);
                return;
            }}

            // âœ… FIX: Inicializar genresData cuando se selecciona un usuario
            genresData = userStats.genres || null;

            document.getElementById('currentUserName').textContent = username;

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

            // âœ… FIX: Usar conteos Ãºnicos reales del analizador
            const totalArtists = userStats.unique_counts ? userStats.unique_counts.total_artists : 0;
            const totalAlbums = userStats.unique_counts ? userStats.unique_counts.total_albums : 0;
            const totalTracks = userStats.unique_counts ? userStats.unique_counts.total_tracks : 0;

            // âœ… NUEVO: Usar conteos Ãºnicos de gÃ©neros del proveedor seleccionado
            let totalGenres = 0;
            if (userStats.unique_counts && userStats.unique_counts.total_genres && userStats.unique_counts.total_genres[currentProvider]) {{
                totalGenres = userStats.unique_counts.total_genres[currentProvider];
            }}

            // âœ… NUEVO: Usar conteos Ãºnicos de sellos del usuario
            const totalLabels = userStats.unique_counts ? userStats.unique_counts.total_labels : 0;

            // AÃ±os Ãºnicos con scrobbles
            const totalYears = Object.keys(userStats.yearly_scrobbles || {{}}).length;

            console.log('ðŸ“Š Stats calculados:', {{
                totalScrobbles, totalArtists, totalAlbums, totalTracks,
                totalGenres, totalLabels, totalYears, currentProvider
            }});

            const summaryHTML = `
                <div class="summary-card">
                    <div class="number">${{totalScrobbles.toLocaleString()}}</div>
                    <div class="label">Scrobbles</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalArtists}}</div>
                    <div class="label">Artistas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalAlbums}}</div>
                    <div class="label">Ãlbumes</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalTracks}}</div>
                    <div class="label">Canciones</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">GÃ©neros</div>
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

            if (!genresData || !genresData[currentProvider]) {{
                // Mostrar mensaje de no datos
                document.getElementById('genresPieChart').style.display = 'none';
                document.getElementById('genresPieInfo').innerHTML = '<div class="no-data">No hay datos disponibles para ' + currentProvider + '</div>';
                document.getElementById('albumGenresPieChart').style.display = 'none';
                document.getElementById('albumGenresPieInfo').innerHTML = '<div class="no-data">No hay datos disponibles para ' + currentProvider + '</div>';
                document.getElementById('genresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter disponibles</div>';
                document.getElementById('albumGenresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter disponibles</div>';
                return;
            }}

            const providerData = genresData[currentProvider];

            // 1. GrÃ¡fico circular con top 15 gÃ©neros de artistas
            renderGenresPieChart(providerData.pie_chart, 'genresPieChart', 'genresPieInfo', 'Artistas');

            // 2. 6 grÃ¡ficos de scatter para top 6 gÃ©neros de artistas
            renderGenresScatterCharts(providerData.scatter_charts, providerData.years, 'genresScatterGrid', false);

            // 3. GrÃ¡fico circular con top 15 gÃ©neros de Ã¡lbumes
            if (providerData.album_pie_chart) {{
                renderGenresPieChart(providerData.album_pie_chart, 'albumGenresPieChart', 'albumGenresPieInfo', 'Ãlbumes');
            }} else {{
                document.getElementById('albumGenresPieChart').style.display = 'none';
                document.getElementById('albumGenresPieInfo').innerHTML = '<div class="no-data">No hay datos de gÃ©neros de Ã¡lbumes para ' + currentProvider + '</div>';
            }}

            // 4. 6 grÃ¡ficos de scatter para top 6 gÃ©neros de Ã¡lbumes
            if (providerData.album_scatter_charts) {{
                renderGenresScatterCharts(providerData.album_scatter_charts, providerData.years, 'albumGenresScatterGrid', true);
            }} else {{
                document.getElementById('albumGenresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter de Ã¡lbumes disponibles</div>';
            }}
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

            // 1. GrÃ¡fico circular con top 15 sellos
            renderGenresPieChart(labelsData.pie_chart, 'labelsPieChart', 'labelsPieInfo', 'Sellos');

            // 2. 6 grÃ¡ficos de scatter para top 6 sellos
            renderLabelsScatterCharts(labelsData.scatter_charts, labelsData.years, 'labelsScatterGrid');
        }}

        function renderGenresPieChart(pieData, canvasId, infoId, type) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!canvas || !info) {{
                console.error(`No se encontrÃ³ el canvas o info para ${{canvasId}}`);
                return;
            }}

            if (!pieData || !pieData.data || Object.keys(pieData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';
            const provider = type === 'Sellos' ? 'Sellos DiscogrÃ¡ficos' : `${{currentProvider}} (${{type}})`;
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

        // âœ… FIX: FunciÃ³n corregida para scatter charts de gÃ©neros
        function renderGenresScatterCharts(scatterData, years, containerId, isAlbums = false) {{
            const container = document.getElementById(containerId);
            if (!container) {{
                console.error(`No se encontrÃ³ el contenedor ${{containerId}}`);
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

                // Crear contenedor para este gÃ©nero
                const genreContainer = document.createElement('div');
                genreContainer.className = 'genres-pie-container';

                const title = document.createElement('h4');
                const itemType = isAlbums ? 'Ãlbumes' : 'Artistas';
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
                    canvas.parentElement.innerHTML = '<div class="no-data">No hay datos temporales para este gÃ©nero</div>';
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
                                    text: 'AÃ±o',
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
                                const itemType = isAlbums ? 'Ãlbum' : 'Artista';
                                showArtistPopup(point.itemName, genre, currentProvider, point.x, point.y, itemType);
                            }}
                        }}
                    }}
                }};

                charts[canvasId] = new Chart(canvas, config);
            }});
        }}

        // âœ… FIX: FunciÃ³n corregida para scatter charts de sellos
        function renderLabelsScatterCharts(scatterData, years, containerId) {{
            const container = document.getElementById(containerId);
            if (!container) {{
                console.error(`No se encontrÃ³ el contenedor ${{containerId}}`);
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
                                    text: 'AÃ±o',
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

        function renderIndividualCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            try {{
                // GrÃ¡fico de scrobbles por aÃ±o
                // if (userStats.yearly_scrobbles) {{
                //     renderYearlyChart(userStats.yearly_scrobbles);
                // }}

                // Top artistas, Ã¡lbumes y canciones (pie charts)
                renderTopChart(userStats.top_artists, 'topArtistsChart', 'topArtistsInfo', 'ðŸ‘¥ Top Artistas');
                renderTopChart(userStats.top_albums, 'topAlbumsChart', 'topAlbumsInfo', 'ðŸ’¿ Top Ãlbumes');
                renderTopChart(userStats.top_tracks, 'topTracksChart', 'topTracksInfo', 'ðŸŽ¶ Top Canciones');

                // âœ… FIX: GrÃ¡ficos de evoluciÃ³n individual
                if (userStats.individual) {{
                    const individualData = currentDataType === 'annual' ? userStats.individual.annual : userStats.individual.cumulative;

                    if (individualData) {{
                        console.log('Renderizando grÃ¡ficos individuales con datos:', Object.keys(individualData));

                        // Solo renderizar si existen los datos
                        if (individualData.genres) renderIndividualLineChart('individualGenresChart', individualData.genres, 'GÃ©neros');
                        if (individualData.labels) renderIndividualLineChart('individualLabelsChart', individualData.labels, 'Sellos');
                        if (individualData.artists) renderIndividualLineChart('individualArtistsChart', individualData.artists, 'Artistas');
                        if (individualData.one_hit_wonders) renderIndividualLineChart('individualOneHitChart', individualData.one_hit_wonders, 'One Hit Wonders');
                        if (individualData.streak_artists) renderIndividualLineChart('individualStreakChart', individualData.streak_artists, 'Artistas con Mayor Streak');
                        if (individualData.track_count_artists) renderIndividualLineChart('individualTrackCountChart', individualData.track_count_artists, 'Artistas con Mayor DiscografÃ­a');
                        if (individualData.new_artists) renderIndividualLineChart('individualNewArtistsChart', individualData.new_artists, 'Artistas Nuevos');
                        if (individualData.rising_artists) renderIndividualLineChart('individualRisingChart', individualData.rising_artists, 'Artistas en Ascenso');
                        if (individualData.falling_artists) renderIndividualLineChart('individualFallingChart', individualData.falling_artists, 'Artistas en Declive');

                    }} else {{
                        console.warn('No hay datos individuales para el tipo:', currentDataType);
                    }}
                }} else {{
                    console.warn('No hay datos individuales en userStats');
                }}
            }} catch (error) {{
                console.error('Error renderizando grÃ¡ficos individuales:', error);
            }}
        }}

        function renderYearlyChart(yearlyData) {{
            const canvas = document.getElementById('yearlyChart');
            const info = document.getElementById('yearlyInfo');

            if (!canvas) {{
                console.error('Canvas yearlyChart no encontrado');
                return;
            }}
            if (!info) {{
                console.error('Info yearlyInfo no encontrado');
                return;
            }}

            const years = Object.keys(yearlyData).sort();
            const scrobbles = years.map(year => yearlyData[year]);
            const totalScrobbles = scrobbles.reduce((a, b) => a + b, 0);

            info.innerHTML = `Total: ${{totalScrobbles.toLocaleString()}} scrobbles | AÃ±os: ${{years.length}}`;

            const data = {{
                labels: years,
                datasets: [{{
                    label: 'Scrobbles',
                    data: scrobbles,
                    backgroundColor: colors[0],
                    borderColor: colors[0],
                    borderWidth: 2,
                    fill: false
                }}]
            }};

            const config = {{
                type: 'line',
                data: data,
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        x: {{
                            title: {{
                                display: true,
                                text: 'AÃ±o',
                                color: '#cdd6f4'
                            }},
                            grid: {{
                                color: '#313244'
                            }},
                            ticks: {{
                                color: '#cdd6f4'
                            }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: 'Scrobbles',
                                color: '#cdd6f4'
                            }},
                            grid: {{
                                color: '#313244'
                            }},
                            ticks: {{
                                color: '#cdd6f4'
                            }}
                        }}
                    }},
                    plugins: {{
                        legend: {{
                            labels: {{
                                color: '#cdd6f4'
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

            charts['yearlyChart'] = new Chart(canvas, config);
        }}

        function renderTopChart(topData, canvasId, infoId, title) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!canvas) {{
                console.error(`Canvas ${{canvasId}} no encontrado`);
                return;
            }}
            if (!info) {{
                console.error(`Info ${{infoId}} no encontrado`);
                return;
            }}

            if (!topData || Object.keys(topData).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';

            const entries = Object.entries(topData)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 15);

            const totalPlays = Object.values(topData).reduce((a, b) => a + b, 0);
            info.innerHTML = `Total: ${{totalPlays.toLocaleString()}} reproducciones | Elementos: ${{Object.keys(topData).length}}`;

            const data = {{
                labels: entries.map(([name, _]) => name),
                datasets: [{{
                    data: entries.map(([_, count]) => count),
                    backgroundColor: colors.slice(0, entries.length),
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

        function renderCoincidenceCharts(userStats) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // GrÃ¡ficos bÃ¡sicos
            renderPieChart('artistsChart', userStats.coincidences.charts.artists, 'artistsInfo');
            renderPieChart('albumsChart', userStats.coincidences.charts.albums, 'albumsInfo');
            renderPieChart('tracksChart', userStats.coincidences.charts.tracks, 'tracksInfo');
            renderPieChart('genresChart', userStats.coincidences.charts.genres, 'genresInfo');

            // Nuevos grÃ¡ficos de coincidencias
            renderPieChart('genreCoincidencesChart', userStats.coincidences.charts.genre_coincidences, 'genreCoincidencesInfo');
            renderPieChart('labelsChart', userStats.coincidences.charts.labels, 'labelsInfo');
            renderPieChart('releaseYearsChart', userStats.coincidences.charts.release_years, 'releaseYearsInfo');
        }}

        function renderPieChart(canvasId, chartData, infoId) {{
            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);

            if (!canvas || !info) {{
                console.error(`No se encontrÃ³ canvas o info para ${{canvasId}}`);
                return;
            }}

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                canvas.style.display = 'none';
                info.innerHTML = '<div class="no-data">No hay datos disponibles</div>';
                return;
            }}

            canvas.style.display = 'block';

            const entries = Object.entries(chartData.data)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 15);

            info.innerHTML = `Total: ${{chartData.total.toLocaleString()}} elementos compartidos | Usuarios: ${{Object.keys(chartData.data).length}}`;

            const data = {{
                labels: entries.map(([user, _]) => user),
                datasets: [{{
                    data: entries.map(([_, count]) => count),
                    backgroundColor: colors.slice(0, entries.length),
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

        // âœ… FIX: FunciÃ³n corregida para grÃ¡ficos de evoluciÃ³n
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

        // âœ… FIX: FunciÃ³n corregida para evoluciÃ³n de coincidencias
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

            if (!canvas) {{
                console.error(`Canvas no encontrado para ${{chartId}}`);
                return;
            }}

            if (!evolutionData || !evolutionData.data) {{
                console.log(`No hay datos de evoluciÃ³n para ${{type}}`);
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

            if (!typeData) {{
                console.log(`No hay datos de tipo para ${{type}}`);
                return;
            }}

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
                                               type === 'albums' ? 'Ãlbumes' :
                                               type === 'tracks' ? 'Canciones' :
                                               type === 'genres' ? 'GÃ©neros' :
                                               type === 'labels' ? 'Sellos' :
                                               type === 'release_years' ? 'DÃ©cadas' : type;

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

        // âœ… FIX: FunciÃ³n para popup de artistas
        function showArtistPopup(itemName, category, provider, year, scrobbles, itemType = 'Artista') {{
            const title = `${{itemName}} - ${{category}} (${{year}})`;
            const content = `
                <div class="popup-item">
                    <span class="name">${{itemType}}: ${{itemName}}</span>
                </div>
                <div class="popup-item">
                    <span class="name">${{provider === 'Sello' ? 'Sello' : 'GÃ©nero'}}: ${{category}}</span>
                </div>
                <div class="popup-item">
                    <span class="name">AÃ±o: ${{year}}</span>
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

        // âœ… FIX: FunciÃ³n para popup lineal
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

        // âœ… FIX: FunciÃ³n para grÃ¡ficos de lÃ­neas individuales
        function renderIndividualLineChart(canvasId, chartData, title) {{
            const canvas = document.getElementById(canvasId);

            if (!canvas) {{
                console.warn(`Canvas ${{canvasId}} no encontrado para ${{title}}`);
                return;
            }}

            if (!chartData || !chartData.data || Object.keys(chartData.data).length === 0) {{
                console.log(`No hay datos para ${{title}} en ${{canvasId}}`);
                return;
            }}

            const datasets = [];
            let colorIndex = 0;

            // Obtener top 15 elementos con mÃ¡s datos
            const sortedItems = Object.entries(chartData.data)
                .sort((a, b) => {{
                    const aTotal = Object.values(a[1]).reduce((sum, val) => sum + val, 0);
                    const bTotal = Object.values(b[1]).reduce((sum, val) => sum + val, 0);
                    return bTotal - aTotal;
                }})
                .slice(0, 15);

            sortedItems.forEach(([item, yearlyData]) => {{
                datasets.push({{
                    label: item,
                    data: chartData.years.map(year => yearlyData[year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false,
                    pointRadius: 3,
                    pointHoverRadius: 6
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
                                usePointStyle: true,
                                font: {{
                                    size: 10
                                }}
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
                                text: 'AÃ±o',
                                color: '#cdd6f4'
                            }},
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: currentDataType === 'annual' ? 'Scrobbles/AÃ±o' : 'Scrobbles Acumulados',
                                color: '#cdd6f4'
                            }},
                            ticks: {{
                                color: '#a6adc8'
                            }},
                            grid: {{
                                color: '#313244'
                            }}
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        // 🆕 Función para cargar datos de novedades dinámicamente
        async function loadDiscoveriesData(username) {{
            console.log(`Cargando datos de novedades para ${{username}}...`);

            // Mostrar loading
            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) {{
                loadingElement.style.display = 'block';
            }}
            if (gridElement) {{
                gridElement.style.display = 'none';
            }}

            try {{
                // Verificar cache
                if (discoveriesData[username]) {{
                    console.log('Usando datos del cache');
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }}

                // Construir URL del archivo JSON
                const currentYear = new Date().getFullYear();
                const fromYear = currentYear - {years_back};
                const toYear = currentYear;
                const period = `${{fromYear}}-${{toYear}}`;
                const dataUrl = `data/usuarios/${{period}}/${{username}}.json`;

                console.log(`Cargando desde: ${{dataUrl}}`);

                const response = await fetch(dataUrl);

                if (!response.ok) {{
                    throw new Error(`Error HTTP: ${{response.status}} - Archivo no encontrado: ${{dataUrl}}`);
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

        // 🆕 Función para renderizar todos los gráficos de novedades
        function renderDiscoveriesCharts(userData) {{
            console.log('Renderizando gráficos de novedades...', userData);

            // Ocultar loading y mostrar grid
            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) {{
                loadingElement.style.display = 'none';
            }}
            if (gridElement) {{
                gridElement.style.display = 'grid';
            }}

            // Destruir gráficos existentes de discoveries
            const discoveryCanvases = ['discoveriesArtistsChart', 'discoveriesAlbumsChart', 'discoveriesTracksChart', 'discoveriesLabelsChart'];
            discoveryCanvases.forEach(canvasId => {{
                if (charts[canvasId]) {{
                    charts[canvasId].destroy();
                    delete charts[canvasId];
                }}
            }});

            // Renderizar cada tipo de gráfico
            const discoveryTypes = [
                {{ type: 'artists', canvasId: 'discoveriesArtistsChart', title: 'Nuevos Artistas' }},
                {{ type: 'albums', canvasId: 'discoveriesAlbumsChart', title: 'Nuevos Álbumes' }},
                {{ type: 'tracks', canvasId: 'discoveriesTracksChart', title: 'Nuevas Canciones' }},
                {{ type: 'labels', canvasId: 'discoveriesLabelsChart', title: 'Nuevos Sellos' }}
            ];

            discoveryTypes.forEach(config => {{
                const typeData = userData.discoveries[config.type];

                if (typeData && Object.keys(typeData).length > 0) {{
                    renderDiscoveryChart(config.canvasId, typeData, config.title, config.type);
                }} else {{
                    showNoDataForChart(config.canvasId, `Sin datos de ${{config.title.toLowerCase()}}`);
                }}
            }});
        }}

        // 🆕 Función para renderizar un gráfico individual de novedades
        function renderDiscoveryChart(canvasId, typeData, title, typeName) {{
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
                    const yearInt = parseInt(year);
                    const yearData = typeData[year];

                    years.push(yearInt);
                    counts.push(yearData.count || 0);
                    details[yearInt] = yearData.items || [];
                }}
            }});

            if (years.length === 0) {{
                showNoDataForChart(canvasId, `Sin datos para ${{title.toLowerCase()}}`);
                return;
            }}

            const config = {{
                type: 'line',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: title,
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
                            borderWidth: 1,
                            callbacks: {{
                                label: function(context) {{
                                    const count = context.parsed.y;
                                    return `${{title}}: ${{count}} nuevos`;
                                }}
                            }}
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

                            if (count > 0 && details[year] && details[year].length > 0) {{
                                showDiscoveryPopup(year, details[year], title, count);
                            }}
                        }}
                    }}
                }}
            }};

            charts[canvasId] = new Chart(canvas, config);
        }}

        // 🆕 Función para mostrar popup con detalles de novedades
        function showDiscoveryPopup(year, items, title, count) {{
            const popupTitle = `${{title}} - ${{year}} (${{count}} nuevos)`;

            let content = '';
            // Mostrar máximo 10 elementos (ya están limitados en el JSON)
            items.forEach((item, index) => {{
                content += `<div class="popup-item">
                    <span class="name">${{item.name}}</span>
                    <span class="count">${{item.date}}</span>
                </div>`;
            }});

            if (count > items.length) {{
                content += `<div style="text-align: center; padding: 10px; color: #a6adc8; font-style: italic;">
                    ... y ${{count - items.length}} más
                </div>`;
            }}

            document.getElementById('popupTitle').textContent = popupTitle;
            document.getElementById('popupContent').innerHTML = content;
            document.getElementById('popupOverlay').style.display = 'block';
            document.getElementById('popup').style.display = 'block';
        }}

        // 🆕 Función para mostrar error en carga de novedades
        function showDiscoveriesError(errorMessage) {{
            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) {{
                loadingElement.style.display = 'none';
            }}

            if (gridElement) {{
                gridElement.innerHTML = `
                    <div class="no-data" style="grid-column: 1/-1;">
                        <div>
                            <p>❌ Error cargando datos de novedades</p>
                            <p style="font-size: 0.9em; margin-top: 10px; color: #f38ba8;">${{errorMessage}}</p>
                            <p style="font-size: 0.8em; margin-top: 10px; color: #6c7086;">
                                Ejecuta: <code>python generate_discoveries_data.py</code>
                            </p>
                        </div>
                    </div>
                `;
                gridElement.style.display = 'grid';
            }}
        }}

        // 🆕 Función para mostrar "sin datos" en un gráfico específico
        function showNoDataForChart(canvasId, message = 'Sin datos') {{
            const canvas = document.getElementById(canvasId);
            if (canvas) {{
                canvas.style.display = 'none';
                const wrapper = canvas.parentElement;
                wrapper.innerHTML = `<div class="no-data" style="height: 200px;">${{message}}</div>`;
            }}
        }}

        // âœ… NUEVA FunciÃ³n para gráficos de novedades/descubrimientos
        }}
    </script>
</body>
</html>"""

    def _format_number(self, number: int) -> str:
        """Formatea nÃºmeros con separadores de miles"""
        return f"{number:,}".replace(",", ".")
