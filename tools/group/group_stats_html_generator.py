#!/usr/bin/env python3
"""
GroupStatsHTMLGenerator - Clase para generar HTML con gráficos interactivos de estadísticas grupales
"""

import json
from datetime import datetime
from typing import Dict, List


class GroupStatsHTMLGenerator:
    """Clase para generar HTML con gráficos interactivos de estadísticas grupales"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def _get_user_icons(self):
        """Obtiene los iconos de usuarios desde variables de entorno"""
        import os

        icons_env = os.getenv('LASTFM_USERS_ICONS', '')
        user_icons = {}
        if icons_env:
            for pair in icons_env.split(','):
                if ':' in pair:
                    user, icon = pair.split(':', 1)
                    user_icons[user.strip()] = icon.strip()
        return user_icons

    def generate_html(self, group_stats: Dict, years_back: int, period_folder: str = None) -> str:
        """Genera el HTML completo para estadísticas grupales"""
        stats_json = json.dumps(group_stats, indent=2, ensure_ascii=False)
        colors_json = json.dumps(self.colors, ensure_ascii=False)
        user_icons = self._get_user_icons()
        user_icons_json = json.dumps(user_icons, ensure_ascii=False)

        # Si no se proporciona period_folder, calcularlo desde group_stats
        if period_folder is None:
            period_parts = group_stats.get('period', '').split('-')
            if len(period_parts) == 2:
                period_folder = group_stats['period']
            else:
                # Fallback por si acaso
                current_year = datetime.now().year
                from_year = current_year - years_back
                period_folder = f"{from_year}-{current_year}"

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Grupo - Estadísticas Grupales</title>
    <link rel="icon" type="image/png" href="images/music.png">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --page-padding: 16px;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: var(--page-padding);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1600px;
            margin: 0 auto;
            background: #181825;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            overflow: hidden;
            position: relative;
        }}

        header {{
            background: #1e1e2e;
            padding: 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        h1 {{
            font-size: 1.8em;
            color: #cba6f7;
            margin-bottom: 10px;
        }}

        @media (max-width: 768px) {{
            h1 {{
                font-size: 1.4em;
            }}
            :root {{
                --page-padding: 6px;
            }}
        }}

        .subtitle {{
            color: #a6adc8;
            font-size: 1em;
        }}

        /* Botón de usuario circular */
        .user-button {{
            position: fixed;
            top: 20px;
            right: 20px;
            width: 50px;
            height: 50px;
            background: #181825;
            color: #1e1e2e;
            border: none;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
            z-index: 1000;
            transition: all 0.3s;
            box-shadow: 0 4px 16px rgba(203, 166, 247, 0.3);
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .user-button:hover {{
            background: #ddb6f2;
            transform: scale(1.1);
        }}

        .user-button img {{
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
        }}

        /* Modal de selección de usuario */
        .user-modal {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 999;
            display: none;
        }}

        .user-modal-content {{
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
        }}

        .user-modal-header {{
            color: #cba6f7;
            font-size: 1.0em;
            font-weight: 500;
            margin-bottom: 15px;
            text-align: center;
        }}

        .user-options {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .user-option {{
            padding: 12px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}

        .user-option img {{
            width: 24px;
            height: 24px;
            border-radius: 50%;
            object-fit: cover;
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

        .user-modal-close {{
            display: block;
            margin: 15px auto 0;
            padding: 8px 16px;
            background: #45475a;
            color: #cdd6f4;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        }}

        .user-modal-close:hover {{
            background: #6c7086;
        }}

        .controls {{
            padding: var(--page-padding);
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

        .stats-container {{
            padding: var(--page-padding);
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
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-bottom: 30px;
        }}

        .summary-card {{
            background: #1e1e2e;
            padding: 10px;
            border-radius: 8px;
            border: 1px solid #313244;
            text-align: center;
        }}

        .summary-card .number {{
            font-size: 1.4em;
            font-weight: 600;
            color: #cba6f7;
            margin-bottom: 3px;
        }}

        .summary-card .label {{
            font-size: 0.8em;
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

        /* Estilos para la sección de datos */
        .data-section {{
            margin-bottom: 40px;
        }}

        .data-controls {{
            padding: var(--page-padding);
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
            padding: var(--page-padding);
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

        /* Estilos para filtros de usuarios */
        .user-filters {{
            padding: var(--page-padding);
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: none; /* Oculto por defecto, se muestra solo en vistas específicas */
        }}

        .user-filters.active {{
            display: block;
        }}

        .user-filters h4 {{
            color: #cba6f7;
            font-size: 1.1em;
            margin-bottom: 15px;
        }}

        .user-filter-buttons {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .user-filter-btn {{
            padding: 8px 16px;
            background: #cba6f7;
            color: #1e1e2e;
            border: 2px solid #cba6f7;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .user-filter-btn img {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            object-fit: cover;
        }}

        .user-filter-btn:hover {{
            background: #ddb6f2;
            border-color: #ddb6f2;
        }}

        .user-filter-btn.inactive {{
            background: #313244;
            color: #cdd6f4;
            border-color: #45475a;
        }}

        .user-filter-btn.inactive:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .filter-info {{
            margin-left: 20px;
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .loading-message {{
            text-align: center;
            padding: 20px;
            color: #cba6f7;
            font-style: italic;
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
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }}

            .summary-stats {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .data-display {{
                grid-template-columns: 1fr;
                padding: var(--page-padding);
            }}

            .data-controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            @media (max-width: 768px) {{
                .data-control-group {{
                    flex-direction: column;
                    align-items: flex-start;
                }}
            }}

            .data-categories {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }}


            .user-button {{
                top: 15px;
                right: 15px;
                width: 45px;
                height: 45px;
                font-size: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Botón de usuario circular -->
        <button class="user-button" id="userButton" title="Seleccionar usuario destacado">ðŸ‘¤</button>

        <!-- Modal de selección de usuario -->
        <div class="user-modal" id="userModal">
            <div class="user-modal-content">
                <div class="user-modal-header">Seleccionar Usuario Destacado</div>
                <div class="user-options" id="userOptions">
                    <div class="user-option selected" data-user="">Ninguno</div>
                    <!-- Se llenarán dinámicamente -->
                </div>
                <button class="user-modal-close" id="userModalClose">Cerrar</button>
            </div>
        </div>

        <header>
            <h1>Estadísticas Grupales</h1>
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

        <!-- Filtros de usuarios para vistas específicas -->
        <div id="userFilters" class="user-filters">

            <div class="user-filter-buttons" id="userFilterButtons">
                <!-- Se llenarán dinámicamente -->
            </div>
            <div class="filter-info" id="filterInfo">
                Selecciona al menos 2 usuarios para mostrar los gráficos
            </div>
        </div>

        <div class="stats-container">

            <!-- Vista de Datos -->
            <div id="dataView" class="view active">
                <div class="data-section">
                    <div class="data-controls">
                        <div class="data-control-group">

                            <select id="userLevelSelect" class="data-select">
                                <!-- Se llenará dinámicamente -->
                            </select>
                        </div>

                        <div class="data-control-group">

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

                    <!-- Resumen de estadísticas -->
                    <div id="summaryStats" class="summary-stats">
                        <!-- Se llenará dinámicamente -->
                    </div>
                </div>
            </div>

            <!-- Vista Por Usuarios Compartidos -->
            <div id="sharedView" class="view">
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>Top 15 Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedArtistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedArtistsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Álbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedAlbumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedAlbumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedTracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedTracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Géneros</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedGenresChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedGenresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Sellos</h3>
                        <div class="chart-wrapper">
                            <canvas id="sharedLabelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="sharedLabelsInfo"></div>
                    </div>

                    <div class="chart-container">
                    <h3>Top 15 Años de Lanzamiento</h3>
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
                        <h3>Top 15 Artistas</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesArtistsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesArtistsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Álbumes</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesAlbumsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesAlbumsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Canciones</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesTracksChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesTracksInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Géneros</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesGenresChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesGenresInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Sellos</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesLabelsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesLabelsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Años de Lanzamiento</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesReleaseYearsChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesReleaseYearsInfo"></div>
                    </div>

                    <div class="chart-container">
                        <h3>Top 15 Global</h3>
                        <div class="chart-wrapper">
                            <canvas id="scrobblesAllCombinedChart"></canvas>
                        </div>
                        <div class="chart-info" id="scrobblesAllCombinedInfo"></div>
                    </div>
                </div>
            </div>

            <!-- Vista de Evolución -->
            <div id="evolutionView" class="view">
                <div class="evolution-section">
                    <h3>Evolución Temporal por Scrobbles</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionArtistsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Top 15 Álbumes por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionAlbumsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Top 15 Canciones por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionTracksChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Top 15 Géneros por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionGenresChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Top 15 Sellos por Año</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="evolutionLabelsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Top 15 Años de Lanzamiento por Año</h4>
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
                    <button id="popupClose" class="popup-close">X</button>
                </div>
                <div id="popupContent" class="popup-content"></div>
            </div>
        </div>
    </div>

    <script>
        const groupStats = {stats_json};
        const colors = {colors_json};
        const userIcons = {user_icons_json};
        const periodFolder = "{period_folder}";

        let currentView = 'data';
        let charts = {{}};

        // Variables para la sección de datos
        let activeDataCategories = new Set(['artists']); // Por defecto mostrar artistas
        let currentUserLevel = '';
        let selectedHighlightUser = '';

        // Variables para filtrado de usuarios dinámico
        let activeUsers = new Set(groupStats.users); // Por defecto todos los usuarios activos
        let dynamicDataCache = {{}}; // Cache para datos cargados dinámicamente
        let isLoadingData = false;

        // Funcionalidad del botón de usuario
        function initializeUserSelector() {{
            const userButton = document.getElementById('userButton');
            const userModal = document.getElementById('userModal');
            const userModalClose = document.getElementById('userModalClose');
            const userOptions = document.getElementById('userOptions');

            // Cargar usuario guardado desde localStorage
            selectedHighlightUser = localStorage.getItem('lastfm_selected_user') || '';

            // Llenar opciones de usuarios
            groupStats.users.forEach(user => {{
                const option = document.createElement('div');
                option.className = 'user-option';
                option.dataset.user = user;

                const icon = userIcons[user];
                if (icon) {{
                    if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {{
                        option.innerHTML = `<img src="${{icon}}" alt="${{user}}"> ${{user}}`;
                    }} else {{
                        option.innerHTML = `<span style="font-size:1.2em;">${{icon}}</span> ${{user}}`;
                    }}
                }} else {{
                    option.textContent = user;
                }}

                userOptions.appendChild(option);
            }});

            // Marcar opción seleccionada y actualizar botón
            updateSelectedUserOption();
            updateUserButtonIcon();

            // Event listeners
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
                    selectedHighlightUser = user;

                    // Guardar en localStorage
                    if (user) {{
                        localStorage.setItem('lastfm_selected_user', user);
                    }} else {{
                        localStorage.removeItem('lastfm_selected_user');
                    }}

                    updateSelectedUserOption();
                    updateUserButtonIcon();
                    userModal.style.display = 'none';

                    // Actualizar vista si estamos en datos
                    if (currentView === 'data') {{
                        renderDataView();
                    }}
                }}
            }});
        }}

        function updateUserButtonIcon() {{
            const userButton = document.getElementById('userButton');
            const icon = userIcons[selectedHighlightUser];
            if (selectedHighlightUser && icon) {{
                if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {{
                    userButton.innerHTML = `<img src="${{icon}}" alt="${{selectedHighlightUser}}">`;
                }} else {{
                    userButton.textContent = icon;
                }}
            }} else {{
                userButton.textContent = '👤';
            }}
        }}

        function updateSelectedUserOption() {{
            const userOptions = document.getElementById('userOptions');
            userOptions.querySelectorAll('.user-option').forEach(option => {{
                option.classList.remove('selected');
                if (option.dataset.user === selectedHighlightUser) {{
                    option.classList.add('selected');
                }}
            }});
        }}

        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {{
            initializeUserSelector();
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

            // Inicializar filtros de usuarios
            initializeUserFilters();

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

            // Mostrar/ocultar filtros de usuarios según la vista
            const userFilters = document.getElementById('userFilters');
            if (view === 'shared' || view === 'scrobbles' || view === 'evolution') {{
                userFilters.classList.add('active');
            }} else {{
                userFilters.classList.remove('active');
            }}

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
                renderSharedChartsWithFilter();
            }} else if (view === 'scrobbles') {{
                renderScrobblesChartsWithFilter();
            }} else if (view === 'evolution') {{
                renderEvolutionChartsWithFilter();
            }}
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
                    <div class="label">Artistas Compartidos</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedAlbums}}</div>
                    <div class="label">Álbumes Compartidos</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedTracks}}</div>
                    <div class="label">Canciones Compartidas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedGenres}}</div>
                    <div class="label">Géneros Compartidos</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalSharedLabels}}</div>
                    <div class="label">Sellos Compartidos</div>
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

            // Renderizar gráficos por usuarios compartidos
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

            // Renderizar gráficos por scrobbles totales
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

            // Renderizar gráficos de evolución
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
                content += `<div class="details">Artista: ${{details.artist}} | Álbum: ${{details.album}}</div>`;
            }} else if (details.artist && details.track) {{
                content += `<div class="details">Artista: ${{details.artist}} | Canción: ${{details.track}}</div>`;
            }}

            if (chartData.type === 'combined') {{
                content += `<div class="details">Categoría: ${{details.category}}</div>`;
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

        // Funciones para la sección de datos
        function initializeDataControls() {{
            console.log('Inicializando controles de datos...'); // Debug
            const userLevelSelect = document.getElementById('userLevelSelect');

            // Llenar select de niveles de usuarios
            if (groupStats.data_by_levels) {{
                console.log('data_by_levels encontrado:', Object.keys(groupStats.data_by_levels)); // Debug
                const levels = Object.keys(groupStats.data_by_levels);
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
                console.error('data_by_levels no encontrado en groupStats'); // Debug
            }}

            // Event listeners
            userLevelSelect.addEventListener('change', function() {{
                currentUserLevel = this.value;
                console.log('Cambiando a nivel:', currentUserLevel); // Debug
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
            console.log('=== RENDER DATA VIEW ==='); // Debug
            console.log('currentUserLevel:', currentUserLevel); // Debug
            console.log('data_by_levels keys:', Object.keys(groupStats.data_by_levels || {{}})); // Debug

            const dataDisplay = document.getElementById('dataDisplay');
            console.log('dataDisplay element:', dataDisplay); // Debug
            dataDisplay.innerHTML = '';
            console.log('innerHTML cleared'); // Debug

            if (!currentUserLevel || !groupStats.data_by_levels || !groupStats.data_by_levels[currentUserLevel]) {{
                console.log('No hay datos para el nivel:', currentUserLevel); // Debug
                console.log('Niveles disponibles:', Object.keys(groupStats.data_by_levels || {{}})); // Debug
                dataDisplay.innerHTML = '<div class="data-no-data">No hay datos disponibles</div>';
                return;
            }}

            const levelData = groupStats.data_by_levels[currentUserLevel];
            console.log('Datos del nivel seleccionado:', levelData); // Debug
            console.log('Categorías activas:', Array.from(activeDataCategories)); // Debug

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
            let elementsAdded = 0;

            categoryOrder.forEach(categoryKey => {{
                console.log(`Procesando categoría: ${{categoryKey}}`); // Debug
                console.log(`- Está activa: ${{activeDataCategories.has(categoryKey)}}`); // Debug
                console.log(`- Tiene datos: ${{levelData[categoryKey] ? levelData[categoryKey].length : 0}} items`); // Debug

                if (!activeDataCategories.has(categoryKey)) return;
                if (!levelData[categoryKey] || levelData[categoryKey].length === 0) return;

                hasVisibleData = true;

                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'data-category visible';
                console.log(`Creando div para ${{categoryKey}}, className: ${{categoryDiv.className}}`); // Debug

                const title = document.createElement('h4');
                title.textContent = `${{categoryTitles[categoryKey]}} (${{levelData[categoryKey].length}})`;
                categoryDiv.appendChild(title);
                console.log(`Título agregado: ${{title.textContent}}`); // Debug

                let itemsAdded = 0;
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
                    // Ordenar usuarios por scrobbles descendente antes de mostrarlos
                    const sortedUsers = Object.entries(item.user_counts)
                        .sort((a, b) => b[1] - a[1])
                        .map(([user]) => user);

                    sortedUsers.forEach(user => {{
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
                    itemsAdded++;
                }});

                console.log(`Items agregados a ${{categoryKey}}: ${{itemsAdded}}`); // Debug
                dataDisplay.appendChild(categoryDiv);
                elementsAdded++;
                console.log(`CategoryDiv agregado al DOM. Total elementos en dataDisplay: ${{dataDisplay.children.length}}`); // Debug
            }});

            console.log('hasVisibleData:', hasVisibleData); // Debug
            console.log('elementsAdded:', elementsAdded); // Debug
            console.log('dataDisplay final innerHTML length:', dataDisplay.innerHTML.length); // Debug
            console.log('dataDisplay final children count:', dataDisplay.children.length); // Debug

            if (!hasVisibleData) {{
                const noDataDiv = document.createElement('div');
                noDataDiv.className = 'data-no-data';
                noDataDiv.textContent = activeDataCategories.size === 0
                    ? 'Selecciona al menos una categoría para ver los datos'
                    : 'No hay datos disponibles para este nivel';
                dataDisplay.appendChild(noDataDiv);
                console.log('Agregado mensaje de no data'); // Debug
            }}

            // Forzar un repaint
            dataDisplay.style.display = 'none';
            dataDisplay.offsetHeight; // trigger reflow
            dataDisplay.style.display = '';
            console.log('Repaint forzado'); // Debug
        }}

        // ==================== FUNCIONES PARA FILTRADO DINÁMICO ====================

        function initializeUserFilters() {{
            console.log('Inicializando filtros de usuarios...');
            const userFilterButtons = document.getElementById('userFilterButtons');

            // Crear botones para cada usuario
            groupStats.users.forEach(user => {{
                const btn = document.createElement('button');
                btn.className = 'user-filter-btn'; // Empezar sin clase active/inactive
                btn.dataset.user = user;

                const icon = userIcons[user];
                if (icon) {{
                    if (icon.startsWith('http') || icon.startsWith('/') || icon.endsWith('.png') || icon.endsWith('.jpg')) {{
                        btn.innerHTML = `<img src="${{icon}}" alt="${{user}}"> ${{user}}`;
                    }} else {{
                        btn.innerHTML = `<span style="font-size:1.1em;">${{icon}}</span> ${{user}}`;
                    }}
                }} else {{
                    btn.textContent = user;
                }}

                btn.addEventListener('click', () => {{
                    toggleUser(user);
                }});

                userFilterButtons.appendChild(btn);
            }});

            // Actualizar estados iniciales
            updateUserFilterButtons();
            updateFilterInfo();
        }}

        function updateUserFilterButtons() {{
            const userFilterButtons = document.getElementById('userFilterButtons');
            userFilterButtons.querySelectorAll('.user-filter-btn').forEach(btn => {{
                const user = btn.dataset.user;
                // Remover clases existentes
                btn.classList.remove('inactive');

                if (activeUsers.has(user)) {{
                    // Usuario activo: clase base (sin inactive)
                    // El CSS por defecto ya maneja el estilo activo
                }} else {{
                    // Usuario inactivo: agregar clase inactive
                    btn.classList.add('inactive');
                }}
            }});
        }}

        function toggleUser(user) {{
            const btn = document.querySelector(`[data-user="${{user}}"]`);

            if (activeUsers.has(user)) {{
                // Si solo queda este usuario activo, no permitir desactivarlo
                if (activeUsers.size <= 1) {{
                    alert('Debe haber al menos 1 usuario activo');
                    return;
                }}
                activeUsers.delete(user);
            }} else {{
                activeUsers.add(user);
            }}

            updateUserFilterButtons();
            updateFilterInfo();

            // Recargar gráficos si estamos en una vista filtrable
            if (['shared', 'scrobbles', 'evolution'].includes(currentView)) {{
                refreshCurrentView();
            }}
        }}

        function updateFilterInfo() {{
            const filterInfo = document.getElementById('filterInfo');
            const activeCount = activeUsers.size;
            const totalCount = groupStats.users.length;

            if (activeCount < 2) {{
                filterInfo.textContent = `${{activeCount}}/${{totalCount}} usuarios activos - Selecciona al menos 2 usuarios`;
                filterInfo.style.color = '#f38ba8'; // Color de advertencia
            }} else {{
                filterInfo.textContent = `${{activeCount}}/${{totalCount}} usuarios activos`;
                filterInfo.style.color = '#a6adc8'; // Color normal
            }}
        }}

        function refreshCurrentView() {{
            console.log('Refrescando vista actual:', currentView);

            if (activeUsers.size < 2) {{
                showLoadingMessage('Selecciona al menos 2 usuarios');
                return;
            }}

            if (currentView === 'shared') {{
                renderSharedChartsWithFilter();
            }} else if (currentView === 'scrobbles') {{
                renderScrobblesChartsWithFilter();
            }} else if (currentView === 'evolution') {{
                renderEvolutionChartsWithFilter();
            }}
        }}

        function getUserKey() {{
            return Array.from(activeUsers).sort().join('_');
        }}

        function showLoadingMessage(message) {{
            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Mostrar mensaje en todos los contenedores de gráficos
            const containers = document.querySelectorAll('.chart-info, .chart-wrapper canvas');
            containers.forEach(container => {{
                if (container.tagName === 'CANVAS') {{
                    container.style.display = 'none';
                }} else {{
                    container.innerHTML = `<div class="loading-message">${{message}}</div>`;
                }}
            }});
        }}

        async function loadDynamicData(dataType, userKey) {{
            if (dynamicDataCache[`${{dataType}}_${{userKey}}`]) {{
                return dynamicDataCache[`${{dataType}}_${{userKey}}`];
            }}

            try {{
                const response = await fetch(`data/${{periodFolder}}/${{dataType}}_${{userKey}}.json`);
                if (!response.ok) {{
                    throw new Error(`HTTP error! status: ${{response.status}}`);
                }}
                const data = await response.json();
                dynamicDataCache[`${{dataType}}_${{userKey}}`] = data;
                return data;
            }} catch (error) {{
                console.error(`Error cargando datos ${{dataType}}_${{userKey}}:`, error);
                return null;
            }}
        }}

        async function renderSharedChartsWithFilter() {{
            if (isLoadingData) return;
            isLoadingData = true;

            console.log('Renderizando gráficos compartidos con filtro...');
            showLoadingMessage('Cargando datos...');

            const userKey = getUserKey();
            const sharedData = await loadDynamicData('shared', userKey);

            if (!sharedData) {{
                showLoadingMessage('Error cargando datos');
                isLoadingData = false;
                return;
            }}

            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar gráficos por usuarios compartidos
            renderPieChart('sharedArtistsChart', sharedData.artists, 'sharedArtistsInfo');
            renderPieChart('sharedAlbumsChart', sharedData.albums, 'sharedAlbumsInfo');
            renderPieChart('sharedTracksChart', sharedData.tracks, 'sharedTracksInfo');
            renderPieChart('sharedGenresChart', sharedData.genres, 'sharedGenresInfo');
            renderPieChart('sharedLabelsChart', sharedData.labels, 'sharedLabelsInfo');
            renderPieChart('sharedReleaseYearsChart', sharedData.release_years, 'sharedReleaseYearsInfo');

            isLoadingData = false;
        }}

        async function renderScrobblesChartsWithFilter() {{
            if (isLoadingData) return;
            isLoadingData = true;

            console.log('Renderizando gráficos de scrobbles con filtro...');
            showLoadingMessage('Cargando datos...');

            const userKey = getUserKey();
            const scrobblesData = await loadDynamicData('scrobbles', userKey);

            if (!scrobblesData) {{
                showLoadingMessage('Error cargando datos');
                isLoadingData = false;
                return;
            }}

            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar gráficos por scrobbles totales
            renderPieChart('scrobblesArtistsChart', scrobblesData.artists, 'scrobblesArtistsInfo');
            renderPieChart('scrobblesAlbumsChart', scrobblesData.albums, 'scrobblesAlbumsInfo');
            renderPieChart('scrobblesTracksChart', scrobblesData.tracks, 'scrobblesTracksInfo');
            renderPieChart('scrobblesGenresChart', scrobblesData.genres, 'scrobblesGenresInfo');
            renderPieChart('scrobblesLabelsChart', scrobblesData.labels, 'scrobblesLabelsInfo');
            renderPieChart('scrobblesReleaseYearsChart', scrobblesData.release_years, 'scrobblesReleaseYearsInfo');
            renderPieChart('scrobblesAllCombinedChart', scrobblesData.all_combined, 'scrobblesAllCombinedInfo');

            isLoadingData = false;
        }}

        async function renderEvolutionChartsWithFilter() {{
            if (isLoadingData) return;
            isLoadingData = true;

            console.log('Renderizando gráficos de evolución con filtro...');
            showLoadingMessage('Cargando datos...');

            const userKey = getUserKey();
            const evolutionData = await loadDynamicData('evolution', userKey);

            if (!evolutionData) {{
                showLoadingMessage('Error cargando datos');
                isLoadingData = false;
                return;
            }}

            // Destruir charts existentes
            Object.values(charts).forEach(chart => {{
                if (chart) chart.destroy();
            }});
            charts = {{}};

            // Renderizar gráficos de evolución
            renderLineChart('evolutionArtistsChart', evolutionData.artists);
            renderLineChart('evolutionAlbumsChart', evolutionData.albums);
            renderLineChart('evolutionTracksChart', evolutionData.tracks);
            renderLineChart('evolutionGenresChart', evolutionData.genres);
            renderLineChart('evolutionLabelsChart', evolutionData.labels);
            renderLineChart('evolutionReleaseYearsChart', evolutionData.release_years);

            isLoadingData = false;
        }}
    </script>
</body>
</html>"""

    def _format_number(self, number: int) -> str:
        """Formatea números con separadores de miles"""
        return f"{number:,}".replace(",", ".")
