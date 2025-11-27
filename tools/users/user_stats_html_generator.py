#!/usr/bin/env python3
"""
UserStatsHTMLGeneratorCOMPLETO - TODOS los gráficos del original pero con datos optimizados
- Mantiene TODOS los gráficos de las 6 pestañas
- Optimiza los datos para evitar JSON gigante
- Funciona en el navegador
"""

import json
import os
from typing import Dict, List


class UserStatsHTMLGeneratorCompleto:
    """TODOS los gráficos pero con datos optimizados para el navegador"""

    def __init__(self):
        self.colors = [
            '#cba6f7', '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1',
            '#94e2d5', '#89dceb', '#74c7ec', '#89b4fa', '#b4befe',
            '#f5c2e7', '#f2cdcd', '#ddb6f2', '#ffc6ff', '#caffbf'
        ]

    def _optimize_for_browser(self, user_stats: dict) -> dict:
        """Optimiza datos pero mantiene TODOS los necesarios para todos los gráficos"""
        print(f"    🔧 Optimizando datos COMPLETOS para {user_stats.get('user', 'unknown')}")

        optimized = {
            'user': user_stats.get('user', ''),
            'yearly_scrobbles': user_stats.get('yearly_scrobbles', {}),
        }

        # Conteos únicos (esenciales)
        if 'unique_counts' in user_stats:
            optimized['unique_counts'] = user_stats['unique_counts']

        # Top charts básicos (pie charts principales)
        for chart_type in ['top_artists', 'top_albums', 'top_tracks']:
            if chart_type in user_stats:
                original = user_stats[chart_type]
                if isinstance(original, dict):
                    optimized[chart_type] = dict(list(original.items())[:15])
                else:
                    optimized[chart_type] = original

        # GÉNEROS: pie charts + scatter reducido (no todos los años)
        if 'genres' in user_stats:
            optimized['genres'] = {}
            for provider in ['lastfm', 'musicbrainz', 'discogs']:
                if provider in user_stats['genres']:
                    provider_data = user_stats['genres'][provider]
                    optimized['genres'][provider] = {
                        'pie_chart': provider_data.get('pie_chart', {}),
                        'album_pie_chart': provider_data.get('album_pie_chart', {}),
                        'years': provider_data.get('years', [])
                    }

                    # Scatter charts MUY reducidos (solo top 3 géneros, datos anuales simples)
                    if 'scatter_charts' in provider_data:
                        optimized_scatter = {}
                        scatter_data = provider_data['scatter_charts']
                        for i, (genre, artists) in enumerate(scatter_data.items()):
                            if i >= 3:  # Solo top 3 géneros
                                break
                            optimized_scatter[genre] = []
                            for j, artist_data in enumerate(artists[:5]):  # Solo top 5 artistas por género
                                if j >= 5:
                                    break
                                # Solo datos anuales simples
                                simplified_yearly = {}
                                for year, plays in artist_data.get('yearly_data', {}).items():
                                    if plays > 0:  # Solo años con datos
                                        simplified_yearly[year] = plays

                                if simplified_yearly:  # Solo incluir si tiene datos
                                    optimized_scatter[genre].append({
                                        'artist': artist_data.get('artist', ''),
                                        'yearly_data': simplified_yearly,
                                        'total_plays': artist_data.get('total_plays', 0)
                                    })

                        if optimized_scatter:
                            optimized['genres'][provider]['scatter_charts'] = optimized_scatter

                    # Album scatter charts (también reducidos)
                    if 'album_scatter_charts' in provider_data:
                        optimized_album_scatter = {}
                        album_scatter_data = provider_data['album_scatter_charts']
                        for i, (genre, albums) in enumerate(album_scatter_data.items()):
                            if i >= 3:
                                break
                            optimized_album_scatter[genre] = []
                            for j, album_data in enumerate(albums[:5]):
                                if j >= 5:
                                    break
                                simplified_yearly = {}
                                for year, plays in album_data.get('yearly_data', {}).items():
                                    if plays > 0:
                                        simplified_yearly[year] = plays

                                if simplified_yearly:
                                    optimized_album_scatter[genre].append({
                                        'album': album_data.get('album', ''),
                                        'yearly_data': simplified_yearly,
                                        'total_plays': album_data.get('total_plays', 0)
                                    })

                        if optimized_album_scatter:
                            optimized['genres'][provider]['album_scatter_charts'] = optimized_album_scatter

        # LABELS: pie chart + scatter reducido
        if 'labels' in user_stats:
            optimized['labels'] = {
                'pie_chart': user_stats['labels'].get('pie_chart', {}),
                'years': user_stats['labels'].get('years', [])
            }

            # Labels scatter reducido
            if 'scatter_charts' in user_stats['labels']:
                optimized_labels_scatter = {}
                labels_scatter_data = user_stats['labels']['scatter_charts']
                for i, (label, artists) in enumerate(labels_scatter_data.items()):
                    if i >= 3:  # Solo top 3 labels
                        break
                    optimized_labels_scatter[label] = []
                    for j, artist_data in enumerate(artists[:5]):
                        if j >= 5:
                            break
                        simplified_yearly = {}
                        for year, plays in artist_data.get('yearly_data', {}).items():
                            if plays > 0:
                                simplified_yearly[year] = plays

                        if simplified_yearly:
                            optimized_labels_scatter[label].append({
                                'artist': artist_data.get('artist', ''),
                                'yearly_data': simplified_yearly,
                                'total_plays': artist_data.get('total_plays', 0)
                            })

                if optimized_labels_scatter:
                    optimized['labels']['scatter_charts'] = optimized_labels_scatter

        # COINCIDENCIAS: solo resúmenes básicos
        if 'coincidences' in user_stats:
            optimized['coincidences'] = {'charts': {}}
            charts = user_stats['coincidences'].get('charts', {})
            for chart_type, chart_data in charts.items():
                if isinstance(chart_data, dict):
                    optimized['coincidences']['charts'][chart_type] = {
                        'title': chart_data.get('title', ''),
                        'data': dict(list(chart_data.get('data', {}).items())[:8]),  # Top 8 usuarios
                        'total': chart_data.get('total', 0),
                        'type': chart_data.get('type', '')
                    }

        # EVOLUTION: datos básicos para line charts
        if 'evolution' in user_stats:
            optimized['evolution'] = {}
            evolution = user_stats['evolution']
            for evo_type in ['genres', 'labels', 'release_years', 'coincidences']:
                if evo_type in evolution:
                    evo_data = evolution[evo_type]
                    optimized['evolution'][evo_type] = {
                        'data': {},
                        'years': evo_data.get('years', []),
                        'users': evo_data.get('users', [])[:5]
                    }
                    # Solo datos de 3 usuarios máximo para evolution
                    data = evo_data.get('data', {})
                    if evo_type == 'coincidences':
                        # Para coincidences, hay sub-tipos
                        for sub_type in ['artists', 'albums', 'tracks']:
                            if sub_type in data:
                                optimized['evolution'][evo_type]['data'][sub_type] = {}
                                for user_key in list(data[sub_type].keys())[:3]:
                                    optimized['evolution'][evo_type]['data'][sub_type][user_key] = data[sub_type][user_key]
                    else:
                        for user_key in list(data.keys())[:3]:
                            optimized['evolution'][evo_type]['data'][user_key] = data[user_key]

        # INDIVIDUAL: datos esenciales para line charts (MUY reducidos)
        if 'individual' in user_stats:
            optimized['individual'] = {}
            individual = user_stats['individual']

            for data_type in ['annual', 'cumulative']:
                if data_type in individual:
                    optimized['individual'][data_type] = {}
                    type_data = individual[data_type]

                    # Para cada categoría individual
                    for category in ['genres', 'labels', 'artists', 'one_hit_wonders',
                                   'streak_artists', 'track_count_artists', 'new_artists',
                                   'rising_artists', 'falling_artists']:
                        if category in type_data:
                            cat_data = type_data[category]
                            optimized['individual'][data_type][category] = {
                                'data': {},
                                'years': cat_data.get('years', [])
                            }

                            # Solo top 5 elementos por categoría para line charts
                            data = cat_data.get('data', {})
                            for i, (item_name, yearly_data) in enumerate(data.items()):
                                if i >= 5:  # Solo top 5 por categoría
                                    break
                                # Incluir todos los años pero verificar que hay datos
                                if isinstance(yearly_data, dict) and any(v > 0 for v in yearly_data.values()):
                                    optimized['individual'][data_type][category]['data'][item_name] = yearly_data

        size_before = len(str(user_stats))
        size_after = len(str(optimized))
        reduction = ((size_before - size_after) / size_before * 100) if size_before > 0 else 0

        print(f"      ✅ Reducido {reduction:.1f}% pero manteniendo TODOS los gráficos")
        return optimized

    def generate_html(self, all_user_stats: Dict, users: List[str], years_back: int) -> str:
        """Genera HTML COMPLETO con todos los gráficos pero datos optimizados"""
        print("🎨 Generando HTML COMPLETO con todos los gráficos...")

        # Optimizar datos para cada usuario
        optimized_stats = {}
        for user in users:
            if user in all_user_stats:
                optimized_stats[user] = self._optimize_for_browser(all_user_stats[user])
            else:
                print(f"    ⚠️ Usuario {user} no encontrado")

        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(optimized_stats, ensure_ascii=False, separators=(',', ':'))
        colors_json = json.dumps(self.colors, ensure_ascii=False)

        # Iconos de usuario
        icons_env = os.getenv('LASTFM_USERS_ICONS', '')
        user_icons = {}
        if icons_env:
            for pair in icons_env.split(','):
                if ':' in pair:
                    user, icon = pair.split(':', 1)
                    user_icons[user.strip()] = icon.strip()
        user_icons_json = json.dumps(user_icons, ensure_ascii=False)

        json_size_kb = len(stats_json) / 1024
        print(f"📏 JSON optimizado: {json_size_kb:.1f} KB (vs varios MB del original)")

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Usuarios - Estadísticas Individuales COMPLETAS</title>
    <link rel="icon" type="image/png" href="images/music.png">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e; color: #cdd6f4; padding: 20px; line-height: 1.6;
        }}
        .container {{
            max-width: 1600px; margin: 0 auto; background: #181825;
            border-radius: 16px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); overflow: hidden;
        }}
        header {{
            background: #1e1e2e; padding: 20px 30px; border-bottom: 2px solid #cba6f7;
            display: flex; justify-content: space-between; align-items: center; min-height: 80px;
        }}
        .header-content {{ display: flex; flex-direction: column; align-items: center; flex-grow: 1; }}
        h1 {{ font-size: 2em; color: #cba6f7; margin-bottom: 10px; }}
        .nav-buttons {{ display: flex; gap: 15px; margin-top: 10px; }}
        .nav-button {{
            padding: 8px 16px; background: #313244; color: #cdd6f4; border: 2px solid #45475a;
            border-radius: 8px; cursor: pointer; transition: all 0.3s; font-size: 0.9em; font-weight: 600;
            text-decoration: none; display: inline-block;
        }}
        .nav-button:hover {{ border-color: #cba6f7; background: #45475a; }}
        .user-button {{
            width: 50px; height: 50px; border-radius: 50%; background: #cba6f7; color: #1e1e2e;
            border: none; cursor: pointer; font-size: 1.2em; font-weight: bold;
            display: flex; align-items: center; justify-content: center; transition: all 0.3s;
        }}
        .user-button:hover {{ background: #b4a3e8; transform: scale(1.1); }}
        .user-modal {{
            display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.8); z-index: 1000; backdrop-filter: blur(5px);
        }}
        .user-modal-content {{
            position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
            background: #1e1e2e; border-radius: 12px; padding: 30px; width: 90%; max-width: 400px; border: 2px solid #cba6f7;
        }}
        .user-modal-header {{ color: #cba6f7; font-size: 1.3em; font-weight: 600; margin-bottom: 20px; text-align: center; }}
        .user-modal-close {{
            position: absolute; top: 15px; right: 20px; background: none; border: none;
            color: #cdd6f4; font-size: 1.5em; cursor: pointer; padding: 0;
        }}
        .user-modal-close:hover {{ color: #cba6f7; }}
        .user-options {{ display: flex; flex-direction: column; gap: 10px; }}
        .user-option {{
            padding: 12px 20px; background: #313244; border: 2px solid #45475a; border-radius: 8px;
            color: #cdd6f4; cursor: pointer; transition: all 0.3s; text-align: center;
        }}
        .user-option:hover {{ background: #45475a; border-color: #cba6f7; }}
        .user-option.selected {{ background: #cba6f7; color: #1e1e2e; border-color: #cba6f7; }}
        .content {{ padding: 30px; }}
        .nav-tabs {{
            display: flex; gap: 15px; margin-bottom: 30px; border-bottom: 2px solid #313244;
            padding-bottom: 15px; flex-wrap: wrap;
        }}
        .nav-tab {{
            padding: 12px 20px; background: #313244; color: #cdd6f4; border: 2px solid #45475a;
            border-radius: 8px 8px 0 0; cursor: pointer; transition: all 0.3s; font-weight: 600; position: relative;
        }}
        .nav-tab:hover {{ background: #45475a; border-color: #cba6f7; }}
        .nav-tab.active {{ background: #cba6f7; color: #1e1e2e; border-color: #cba6f7; border-bottom-color: #181825; }}
        .nav-tab.active::after {{
            content: ''; position: absolute; bottom: -2px; left: 0; right: 0; height: 2px; background: #181825;
        }}
        .user-header {{
            background: linear-gradient(135deg, #1e1e2e, #181825); padding: 25px; border-radius: 12px;
            margin-bottom: 30px; text-align: center;
        }}
        .user-name {{ font-size: 1.4em; color: #cba6f7; font-weight: regular; margin-bottom: 15px; }}
        .summary-stats {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px;
            max-width: 700px; margin: 0 auto;
        }}
        .summary-card {{
            background: rgba(203, 166, 247, 0.1); padding: 10px; border-radius: 8px; text-align: center;
            border: 1px solid rgba(203, 166, 247, 0.3);
        }}
        .summary-card .number {{ font-size: 1.2em; font-weight: bold; color: #cba6f7; margin-bottom: 2px; }}
        .summary-card .label {{ font-size: 0.8em; color: #a6adc8; text-transform: uppercase; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .data-type-buttons {{ display: flex; gap: 10px; margin-bottom: 20px; justify-content: center; flex-wrap: wrap; }}
        .data-type-btn {{
            padding: 8px 16px; background: #313244; color: #cdd6f4; border: 2px solid #45475a;
            border-radius: 6px; cursor: pointer; transition: all 0.3s; font-size: 0.9em; font-weight: 600;
        }}
        .data-type-btn:hover {{ border-color: #f38ba8; background: #45475a; }}
        .data-type-btn.active {{ background: #f38ba8; color: #1e1e2e; border-color: #f38ba8; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 25px; }}
        .chart-card {{
            background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #313244;
            transition: border-color 0.3s;
        }}
        .chart-card:hover {{ border-color: #cba6f7; }}
        .chart-header {{ margin-bottom: 15px; }}
        .chart-title {{ font-size: 1.2em; color: #cba6f7; margin-bottom: 8px; font-weight: 600; }}
        .chart-info {{
            font-size: 0.9em; color: #a6adc8; padding: 8px 12px; background: #313244;
            border-radius: 6px; margin-top: 10px;
        }}
        .chart-wrapper {{ width: 100%; height: 300px; position: relative; }}
        .scatter-chart-wrapper {{ width: 100%; height: 250px; position: relative; }}
        .line-chart-wrapper {{ position: relative; height: 400px; }}
        .no-data {{
            display: flex; align-items: center; justify-content: center; height: 200px;
            background: #313244; border-radius: 8px; color: #a6adc8; font-style: italic;
        }}
        .provider-buttons {{ display: flex; gap: 10px; margin-bottom: 20px; justify-content: center; flex-wrap: wrap; }}
        .provider-btn {{
            padding: 8px 16px; background: #313244; color: #cdd6f4; border: 2px solid #45475a;
            border-radius: 6px; cursor: pointer; transition: all 0.3s; font-size: 0.9em; font-weight: 500;
        }}
        .provider-btn:hover {{ background: #45475a; border-color: #cba6f7; }}
        .provider-btn.active {{ background: #cba6f7; color: #1e1e2e; border-color: #cba6f7; }}
        .genres-section {{ margin-bottom: 40px; }}
        .genres-section h3 {{ color: #cba6f7; margin-bottom: 20px; font-size: 1.3em; text-align: center; }}
        .genres-pie-container {{ background: #1e1e2e; border-radius: 12px; padding: 25px; border: 2px solid #313244; }}
        .genres-pie-container h4 {{ color: #fab387; margin-bottom: 15px; text-align: center; font-size: 1.1em; }}
        .scatter-charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; margin-top: 20px; }}
        .scatter-chart-card {{ background: #1e1e2e; border-radius: 8px; padding: 15px; border: 1px solid #313244; }}
        .scatter-chart-card h5 {{ color: #cba6f7; font-size: 1em; margin-bottom: 10px; text-align: center; font-weight: 600; }}
        .evolution-section {{ margin-bottom: 40px; }}
        .evolution-section h3 {{
            color: #cba6f7; font-size: 1.3em; margin-bottom: 20px; border-bottom: 2px solid #cba6f7; padding-bottom: 10px;
        }}
        .evolution-charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(600px, 1fr)); gap: 25px; }}
        .evolution-chart {{ background: #1e1e2e; border-radius: 12px; padding: 20px; border: 1px solid #313244; }}
        .evolution-chart h4 {{ color: #cba6f7; font-size: 1.1em; margin-bottom: 15px; text-align: center; }}
        /* Discoveries styles */
        .discoveries-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; }}
        @media (max-width: 768px) {{
            .charts-grid {{ grid-template-columns: 1fr; }}
            .scatter-charts-grid {{ grid-template-columns: 1fr; }}
            .evolution-charts {{ grid-template-columns: 1fr; }}
            .summary-stats {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>🎵 RYM Hispano Estadísticas COMPLETAS</h1>
                <div class="nav-buttons">
                    <a href="index.html#temporal" class="nav-button">TEMPORALES</a>
                    <a href="index.html#grupo" class="nav-button">GRUPO</a>
                    <a href="index.html#about" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">👤</button>
        </header>

        <div id="userModal" class="user-modal">
            <div class="user-modal-content">
                <button class="user-modal-close" id="closeModal">&times;</button>
                <div class="user-modal-header">Seleccionar Usuario</div>
                <div class="user-options" id="userOptions"></div>
            </div>
        </div>

        <div class="content">
            <div class="user-header">
                <div class="user-name" id="currentUserName">Selecciona un usuario</div>
                <div class="summary-stats" id="summaryStats"></div>
            </div>

            <div class="nav-tabs">
                <div class="nav-tab active" data-view="individual">📊 Individual</div>
                <div class="nav-tab" data-view="genres">🎵 Géneros</div>
                <div class="nav-tab" data-view="labels">💿 Sellos</div>
                <div class="nav-tab" data-view="coincidences">🤝 Coincidencias</div>
                <div class="nav-tab" data-view="evolution">📈 Evolución</div>
                <div class="nav-tab" data-view="discoveries">✨ Novedades</div>
            </div>

            <!-- PESTAÑA INDIVIDUAL COMPLETA -->
            <div id="individualTab" class="tab-content active">
                <div class="data-type-buttons">
                    <button class="data-type-btn active" data-type="annual">Por Año</button>
                    <button class="data-type-btn" data-type="cumulative">Acumulativo</button>
                </div>

                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">👥 Top Artistas</h3></div>
                        <div class="chart-wrapper"><canvas id="topArtistsChart"></canvas></div>
                        <div class="chart-info" id="topArtistsInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">💿 Top Álbumes</h3></div>
                        <div class="chart-wrapper"><canvas id="topAlbumsChart"></canvas></div>
                        <div class="chart-info" id="topAlbumsInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">🎶 Top Canciones</h3></div>
                        <div class="chart-wrapper"><canvas id="topTracksChart"></canvas></div>
                        <div class="chart-info" id="topTracksInfo"></div>
                    </div>
                </div>

                <!-- Secciones de evolución individual -->
                <div class="evolution-section">
                    <h3>🎭 Evolución de Géneros Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Géneros por Año</h4>
                            <div class="line-chart-wrapper"><canvas id="individualGenresChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🏷️ Evolución de Sellos Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 10 Sellos por Año</h4>
                            <div class="line-chart-wrapper"><canvas id="individualLabelsChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🎤 Evolución de Artistas Individuales</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas por Año</h4>
                            <div class="line-chart-wrapper"><canvas id="individualArtistsChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🎯 One Hit Wonders</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas con 1 Canción (+25 scrobbles)</h4>
                            <div class="line-chart-wrapper"><canvas id="individualOneHitChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>🔥 Artistas con Mayor Streak</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas con Más Días Consecutivos</h4>
                            <div class="line-chart-wrapper"><canvas id="individualStreakChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📚 Artistas con Mayor Discografía</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas con Más Canciones Únicas</h4>
                            <div class="line-chart-wrapper"><canvas id="individualTrackCountChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>✨ Artistas Nuevos</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas Nuevos (Sin Escuchas Previas)</h4>
                            <div class="line-chart-wrapper"><canvas id="individualNewArtistsChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📈 Artistas en Ascenso</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas que Más Rápido Subieron</h4>
                            <div class="line-chart-wrapper"><canvas id="individualRisingChart"></canvas></div>
                        </div>
                    </div>
                </div>

                <div class="evolution-section">
                    <h3>📉 Artistas en Declive</h3>
                    <div class="evolution-charts">
                        <div class="evolution-chart">
                            <h4>Top 15 Artistas que Más Rápido Bajaron</h4>
                            <div class="line-chart-wrapper"><canvas id="individualFallingChart"></canvas></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- PESTAÑA GÉNEROS COMPLETA -->
            <div id="genresTab" class="tab-content">
                <div class="provider-buttons">
                    <button class="provider-btn active" data-provider="lastfm">Last.fm</button>
                    <button class="provider-btn" data-provider="musicbrainz">MusicBrainz</button>
                    <button class="provider-btn" data-provider="discogs">Discogs</button>
                </div>

                <div class="genres-section">
                    <h3>🎶 Distribución de Géneros (Artistas)</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Géneros del Usuario</h4>
                        <div class="chart-wrapper"><canvas id="genresPieChart"></canvas></div>
                        <div class="chart-info" id="genresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>📈 Evolución de Artistas por Género</h3>
                    <div class="scatter-charts-grid" id="genresScatterGrid"></div>
                </div>

                <div class="genres-section">
                    <h3>💿 Distribución de Géneros (Álbumes)</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Géneros de álbumes del Usuario</h4>
                        <div class="chart-wrapper"><canvas id="albumGenresPieChart"></canvas></div>
                        <div class="chart-info" id="albumGenresPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>📈 Evolución de Álbumes por Género</h3>
                    <div class="scatter-charts-grid" id="albumGenresScatterGrid"></div>
                </div>
            </div>

            <!-- PESTAÑA SELLOS COMPLETA -->
            <div id="labelsTab" class="tab-content">
                <div class="genres-section">
                    <h3>💿 Distribución de Sellos</h3>
                    <div class="genres-pie-container">
                        <h4>Top 15 Sellos Discográficos del Usuario</h4>
                        <div class="chart-wrapper"><canvas id="labelsPieChart"></canvas></div>
                        <div class="chart-info" id="labelsPieInfo"></div>
                    </div>
                </div>

                <div class="genres-section">
                    <h3>📈 Evolución de Álbumes por Sello</h3>
                    <div class="scatter-charts-grid" id="labelsScatterGrid"></div>
                </div>
            </div>

            <!-- PESTAÑA COINCIDENCIAS COMPLETA -->
            <div id="coincidencesTab" class="tab-content">
                <div class="charts-grid">
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">👥 Coincidencias de Artistas</h3></div>
                        <div class="chart-wrapper"><canvas id="artistsChart"></canvas></div>
                        <div class="chart-info" id="artistsInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">💿 Coincidencias de Álbumes</h3></div>
                        <div class="chart-wrapper"><canvas id="albumsChart"></canvas></div>
                        <div class="chart-info" id="albumsInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">🎶 Coincidencias de Canciones</h3></div>
                        <div class="chart-wrapper"><canvas id="tracksChart"></canvas></div>
                        <div class="chart-info" id="tracksInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">🎵 Coincidencias de Géneros</h3></div>
                        <div class="chart-wrapper"><canvas id="genresChart"></canvas></div>
                        <div class="chart-info" id="genresInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">🔄 Géneros Compartidos</h3></div>
                        <div class="chart-wrapper"><canvas id="genreCoincidencesChart"></canvas></div>
                        <div class="chart-info" id="genreCoincidencesInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">💿 Coincidencias de Sellos</h3></div>
                        <div class="chart-wrapper"><canvas id="labelsChart"></canvas></div>
                        <div class="chart-info" id="labelsInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">📅 Años de Lanzamiento</h3></div>
                        <div class="chart-wrapper"><canvas id="releaseYearsChart"></canvas></div>
                        <div class="chart-info" id="releaseYearsInfo"></div>
                    </div>
                </div>
            </div>

            <!-- PESTAÑA EVOLUCIÓN COMPLETA -->
            <div id="evolutionTab" class="tab-content">
                <div class="evolution-charts">
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">🎵 Evolución de Géneros</h3></div>
                        <div class="chart-wrapper"><canvas id="genresEvolutionChart"></canvas></div>
                        <div class="chart-info" id="genresEvolutionInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">💿 Evolución de Sellos</h3></div>
                        <div class="chart-wrapper"><canvas id="labelsEvolutionChart"></canvas></div>
                        <div class="chart-info" id="labelsEvolutionInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">📅 Evolución de Años</h3></div>
                        <div class="chart-wrapper"><canvas id="releaseYearsEvolutionChart"></canvas></div>
                        <div class="chart-info" id="releaseYearsEvolutionInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">👥 Evolución de Artistas</h3></div>
                        <div class="chart-wrapper"><canvas id="artistsEvolutionChart"></canvas></div>
                        <div class="chart-info" id="artistsEvolutionInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">💿 Evolución de Álbumes</h3></div>
                        <div class="chart-wrapper"><canvas id="albumsEvolutionChart"></canvas></div>
                        <div class="chart-info" id="albumsEvolutionInfo"></div>
                    </div>
                    <div class="chart-card">
                        <div class="chart-header"><h3 class="chart-title">🎶 Evolución de Canciones</h3></div>
                        <div class="chart-wrapper"><canvas id="tracksEvolutionChart"></canvas></div>
                        <div class="chart-info" id="tracksEvolutionInfo"></div>
                    </div>
                </div>
            </div>

            <!-- PESTAÑA DISCOVERIES -->
            <div id="discoveriesTab" class="tab-content">
                <div id="discoveriesLoading" style="display: none; text-align: center; padding: 40px; color: #a6adc8;">
                    <p>🔄 Cargando datos de novedades...</p>
                </div>
                <div class="discoveries-grid" id="discoveriesGrid">
                    <div class="evolution-chart">
                        <h4>Nuevos Artistas por Año</h4>
                        <div class="line-chart-wrapper"><canvas id="discoveriesArtistsChart"></canvas></div>
                    </div>
                    <div class="evolution-chart">
                        <h4>Nuevos Álbumes por Año</h4>
                        <div class="line-chart-wrapper"><canvas id="discoveriesAlbumsChart"></canvas></div>
                    </div>
                    <div class="evolution-chart">
                        <h4>Nuevas Canciones por Año</h4>
                        <div class="line-chart-wrapper"><canvas id="discoveriesTracksChart"></canvas></div>
                    </div>
                    <div class="evolution-chart">
                        <h4>Nuevos Sellos por Año</h4>
                        <div class="line-chart-wrapper"><canvas id="discoveriesLabelsChart"></canvas></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        console.log('🚀 Iniciando aplicación COMPLETA...');

        // Datos globales optimizados
        const allUsers = {users_json};
        const allStats = {stats_json};
        const colors = {colors_json};
        const userIcons = {user_icons_json};

        // Variables de estado
        let currentUser = null;
        let currentView = 'individual';
        let currentProvider = 'lastfm';
        let currentDataType = 'annual';
        let charts = {{}};
        let discoveriesData = {{}};
        const yearsBackConfig = {years_back};

        console.log('📊 Datos cargados:', {{
            usuarios: allUsers.length,
            estadísticas: Object.keys(allStats).length,
            jsonSize: JSON.stringify(allStats).length
        }});

        document.addEventListener('DOMContentLoaded', initializeApp);

        function initializeApp() {{
            try {{
                console.log('🎯 Configurando aplicación COMPLETA...');
                setupUserModal();
                setupNavigation();
                setupProviderButtons();
                setupDataTypeButtons();

                if (allUsers.length > 0) {{
                    selectUser(allUsers[0]);
                    updateUserButtonIcon(allUsers[0]);
                }}

                console.log('✅ Aplicación COMPLETA lista');
            }} catch (error) {{
                console.error('❌ Error inicializando:', error);
            }}
        }}

        function setupUserModal() {{
            const userButton = document.getElementById('userButton');
            const userModal = document.getElementById('userModal');
            const closeModal = document.getElementById('closeModal');
            const userOptions = document.getElementById('userOptions');

            userOptions.innerHTML = allUsers.map(user => {{
                const icon = userIcons[user] || '👤';
                return `<div class="user-option" data-user="${{user}}">${{icon}} ${{user}}</div>`;
            }}).join('');

            userButton.addEventListener('click', () => userModal.style.display = 'block');
            closeModal.addEventListener('click', () => userModal.style.display = 'none');
            userModal.addEventListener('click', (e) => {{
                if (e.target === userModal) userModal.style.display = 'none';
            }});

            userOptions.addEventListener('click', (e) => {{
                if (e.target.classList.contains('user-option')) {{
                    const username = e.target.dataset.user;
                    selectUser(username);
                    userModal.style.display = 'none';
                    updateUserButtonIcon(username);
                    updateSelectedUserOption(username);
                }}
            }});
        }}

        function setupNavigation() {{
            const navTabs = document.querySelectorAll('.nav-tab');

            navTabs.forEach(tab => {{
                tab.addEventListener('click', () => {{
                    const view = tab.dataset.view;
                    switchToView(view);
                }});
            }});
        }}

        function setupProviderButtons() {{
            const providerBtns = document.querySelectorAll('.provider-btn');

            providerBtns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    const provider = btn.dataset.provider;
                    providerBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentProvider = provider;

                    if (currentView === 'genres' && currentUser) {{
                        renderGenresCharts();
                    }}
                }});
            }});
        }}

        function setupDataTypeButtons() {{
            const dataTypeBtns = document.querySelectorAll('.data-type-btn');

            dataTypeBtns.forEach(btn => {{
                btn.addEventListener('click', () => {{
                    const dataType = btn.dataset.type;
                    dataTypeBtns.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentDataType = dataType;

                    if (currentView === 'individual' && currentUser) {{
                        renderIndividualCharts();
                    }}
                }});
            }});
        }}

        function switchToView(view) {{
            console.log('🎯 Cambiando a vista COMPLETA:', view);

            document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
            document.querySelector(`[data-view="${{view}}"]`).classList.add('active');

            document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
            document.getElementById(view + 'Tab').classList.add('active');

            currentView = view;

            if (currentUser) {{
                if (view === 'discoveries') {{
                    loadDiscoveriesData(currentUser);
                }} else {{
                    renderCurrentView();
                }}
            }}
        }}

        function selectUser(username) {{
            console.log('👤 Seleccionando usuario:', username);
            currentUser = username;

            if (!allStats[username]) {{
                console.error('No hay datos para:', username);
                return;
            }}

            document.getElementById('currentUserName').textContent = username;
            updateSummaryStats();
            renderCurrentView();
        }}

        function updateUserButtonIcon(user) {{
            const userButton = document.getElementById('userButton');
            const icon = userIcons[user] || '👤';
            userButton.textContent = icon;
        }}

        function updateSelectedUserOption(selectedUser) {{
            document.querySelectorAll('.user-option').forEach(option => {{
                option.classList.toggle('selected', option.dataset.user === selectedUser);
            }});
        }}

        function updateSummaryStats() {{
            if (!currentUser || !allStats[currentUser]) return;

            const userStats = allStats[currentUser];
            const totalScrobbles = Object.values(userStats.yearly_scrobbles || {{}}).reduce((a, b) => a + b, 0);
            const counts = userStats.unique_counts || {{}};

            let totalGenres = 0;
            if (counts.total_genres && counts.total_genres[currentProvider]) {{
                totalGenres = counts.total_genres[currentProvider];
            }}

            document.getElementById('summaryStats').innerHTML = `
                <div class="summary-card">
                    <div class="number">${{totalScrobbles.toLocaleString()}}</div>
                    <div class="label">Scrobbles</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{counts.total_artists || 0}}</div>
                    <div class="label">Artistas</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{counts.total_albums || 0}}</div>
                    <div class="label">Álbumes</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{counts.total_tracks || 0}}</div>
                    <div class="label">Canciones</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{totalGenres}}</div>
                    <div class="label">Géneros</div>
                </div>
                <div class="summary-card">
                    <div class="number">${{counts.total_labels || 0}}</div>
                    <div class="label">Sellos</div>
                </div>
            `;
        }}

        function renderCurrentView() {{
            if (!currentUser) return;

            console.log('🎨 Renderizando vista COMPLETA:', currentView);

            switch (currentView) {{
                case 'individual': renderIndividualCharts(); break;
                case 'genres': renderGenresCharts(); break;
                case 'labels': renderLabelsCharts(); break;
                case 'coincidences': renderCoincidencesCharts(); break;
                case 'evolution': renderEvolutionCharts(); break;
                default: console.log('Vista no implementada:', currentView);
            }}
        }}

        function destroyExistingCharts() {{
            Object.values(charts).forEach(chart => {{ if (chart) chart.destroy(); }});
            charts = {{}};
        }}

        function renderIndividualCharts() {{
            console.log('📊 Renderizando pestaña Individual COMPLETA...');
            const userStats = allStats[currentUser];
            if (!userStats) return;

            destroyExistingCharts();

            // Pie charts básicos
            renderTopChart(userStats.top_artists, 'topArtistsChart', 'topArtistsInfo', 'Top Artistas');
            renderTopChart(userStats.top_albums, 'topAlbumsChart', 'topAlbumsInfo', 'Top Álbumes');
            renderTopChart(userStats.top_tracks, 'topTracksChart', 'topTracksInfo', 'Top Canciones');

            // Gráficos de líneas individuales
            if (userStats.individual && userStats.individual[currentDataType]) {{
                const individualData = userStats.individual[currentDataType];
                console.log('Datos individual disponibles:', Object.keys(individualData));

                if (individualData.genres) renderIndividualLineChart('individualGenresChart', individualData.genres, 'Géneros');
                if (individualData.labels) renderIndividualLineChart('individualLabelsChart', individualData.labels, 'Sellos');
                if (individualData.artists) renderIndividualLineChart('individualArtistsChart', individualData.artists, 'Artistas');
                if (individualData.one_hit_wonders) renderIndividualLineChart('individualOneHitChart', individualData.one_hit_wonders, 'One Hit Wonders');
                if (individualData.streak_artists) renderIndividualLineChart('individualStreakChart', individualData.streak_artists, 'Artistas con Mayor Streak');
                if (individualData.track_count_artists) renderIndividualLineChart('individualTrackCountChart', individualData.track_count_artists, 'Artistas con Mayor Discografía');
                if (individualData.new_artists) renderIndividualLineChart('individualNewArtistsChart', individualData.new_artists, 'Artistas Nuevos');
                if (individualData.rising_artists) renderIndividualLineChart('individualRisingChart', individualData.rising_artists, 'Artistas en Ascenso');
                if (individualData.falling_artists) renderIndividualLineChart('individualFallingChart', individualData.falling_artists, 'Artistas en Declive');
            }} else {{
                console.warn('No hay datos individual para:', currentDataType);
            }}
        }}

        function renderGenresCharts() {{
            console.log('🎵 Renderizando pestaña Géneros COMPLETA...');
            const userStats = allStats[currentUser];

            if (!userStats?.genres?.[currentProvider]) {{
                showNoDataMessage('genresPieChart', `No hay datos de géneros para ${{currentProvider}}`);
                return;
            }}

            destroyExistingCharts();

            const providerData = userStats.genres[currentProvider];

            // 1. Pie chart géneros de artistas
            renderGenresPieChart(providerData.pie_chart, 'genresPieChart', 'genresPieInfo', 'Géneros de Artistas');

            // 2. Scatter charts artistas por género
            renderGenresScatterCharts(providerData.scatter_charts, providerData.years, 'genresScatterGrid', false);

            // 3. Pie chart géneros de álbumes
            if (providerData.album_pie_chart) {{
                renderGenresPieChart(providerData.album_pie_chart, 'albumGenresPieChart', 'albumGenresPieInfo', 'Géneros de Álbumes');
            }} else {{
                showNoDataMessage('albumGenresPieChart', `No hay datos de géneros de álbumes para ${{currentProvider}}`);
            }}

            // 4. Scatter charts álbumes por género
            if (providerData.album_scatter_charts) {{
                renderGenresScatterCharts(providerData.album_scatter_charts, providerData.years, 'albumGenresScatterGrid', true);
            }} else {{
                document.getElementById('albumGenresScatterGrid').innerHTML = '<div class="no-data">No hay datos de scatter de álbumes disponibles</div>';
            }}
        }}

        function renderLabelsCharts() {{
            console.log('💿 Renderizando pestaña Sellos COMPLETA...');
            const userStats = allStats[currentUser];

            if (!userStats?.labels) {{
                showNoDataMessage('labelsPieChart', 'No hay datos de sellos');
                return;
            }}

            destroyExistingCharts();

            // 1. Pie chart sellos
            renderGenresPieChart(userStats.labels.pie_chart, 'labelsPieChart', 'labelsPieInfo', 'Sellos Discográficos');

            // 2. Scatter charts por sello
            renderLabelsScatterCharts(userStats.labels.scatter_charts, userStats.labels.years, 'labelsScatterGrid');
        }}

        function renderCoincidencesCharts() {{
            console.log('🤝 Renderizando pestaña Coincidencias COMPLETA...');
            const userStats = allStats[currentUser];

            if (!userStats?.coincidences?.charts) {{
                showNoDataMessage('artistsChart', 'No hay datos de coincidencias');
                return;
            }}

            destroyExistingCharts();

            const chartsData = userStats.coincidences.charts;

            // Renderizar todos los pie charts de coincidencias
            if (chartsData.artists) renderPieChart(chartsData.artists, 'artistsChart', 'artistsInfo', 'Coincidencias de Artistas');
            if (chartsData.albums) renderPieChart(chartsData.albums, 'albumsChart', 'albumsInfo', 'Coincidencias de Álbumes');
            if (chartsData.tracks) renderPieChart(chartsData.tracks, 'tracksChart', 'tracksInfo', 'Coincidencias de Canciones');
            if (chartsData.genres) renderPieChart(chartsData.genres, 'genresChart', 'genresInfo', 'Coincidencias de Géneros');
            if (chartsData.genre_coincidences) renderPieChart(chartsData.genre_coincidences, 'genreCoincidencesChart', 'genreCoincidencesInfo', 'Géneros Compartidos');
            if (chartsData.labels) renderPieChart(chartsData.labels, 'labelsChart', 'labelsInfo', 'Coincidencias de Sellos');
            if (chartsData.release_years) renderPieChart(chartsData.release_years, 'releaseYearsChart', 'releaseYearsInfo', 'Años de Lanzamiento');
        }}

        function renderEvolutionCharts() {{
            console.log('📈 Renderizando pestaña Evolución COMPLETA...');
            const userStats = allStats[currentUser];

            if (!userStats?.evolution) {{
                showNoDataMessage('genresEvolutionChart', 'No hay datos de evolución');
                return;
            }}

            destroyExistingCharts();

            const evolutionData = userStats.evolution;

            // Renderizar todos los line charts de evolución
            if (evolutionData.genres) renderEvolutionLineChart('genresEvolutionChart', evolutionData.genres, 'Evolución de Géneros');
            if (evolutionData.labels) renderEvolutionLineChart('labelsEvolutionChart', evolutionData.labels, 'Evolución de Sellos');
            if (evolutionData.release_years) renderEvolutionLineChart('releaseYearsEvolutionChart', evolutionData.release_years, 'Evolución de Años');
            if (evolutionData.coincidences && evolutionData.coincidences.data.artists) {{
                renderEvolutionLineChart('artistsEvolutionChart', {{
                    data: evolutionData.coincidences.data.artists,
                    years: evolutionData.coincidences.years,
                    users: evolutionData.coincidences.users
                }}, 'Evolución de Artistas');
            }}
            if (evolutionData.coincidences && evolutionData.coincidences.data.albums) {{
                renderEvolutionLineChart('albumsEvolutionChart', {{
                    data: evolutionData.coincidences.data.albums,
                    years: evolutionData.coincidences.years,
                    users: evolutionData.coincidences.users
                }}, 'Evolución de Álbumes');
            }}
            if (evolutionData.coincidences && evolutionData.coincidences.data.tracks) {{
                renderEvolutionLineChart('tracksEvolutionChart', {{
                    data: evolutionData.coincidences.data.tracks,
                    years: evolutionData.coincidences.years,
                    users: evolutionData.coincidences.users
                }}, 'Evolución de Canciones');
            }}
        }}

        // FUNCIONES DE RENDERIZADO ESPECÍFICAS

        function renderTopChart(data, canvasId, infoId, title) {{
            if (!data || Object.keys(data).length === 0) {{
                showNoDataMessage(canvasId, `No hay datos para ${{title}}`);
                return;
            }}

            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);
            if (!canvas || !info) return;

            const entries = Object.entries(data).slice(0, 15);
            const total = Object.values(data).reduce((a, b) => a + b, 0);

            info.innerHTML = `${{title}} | Total: ${{total.toLocaleString()}} reproducciones | Elementos: ${{Object.keys(data).length}}`;

            const chart = new Chart(canvas, {{
                type: 'pie',
                data: {{
                    labels: entries.map(([name]) => name),
                    datasets: [{{
                        data: entries.map(([, count]) => count),
                        backgroundColor: colors.slice(0, entries.length),
                        borderColor: '#181825',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#cdd6f4', padding: 15, usePointStyle: true }} }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7', borderWidth: 1
                        }}
                    }}
                }}
            }});

            charts[canvasId] = chart;
        }}

        function renderGenresPieChart(pieData, canvasId, infoId, title) {{
            if (!pieData?.data || Object.keys(pieData.data).length === 0) {{
                showNoDataMessage(canvasId, `No hay datos para ${{title}}`);
                return;
            }}

            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);
            if (!canvas || !info) return;

            const entries = Object.entries(pieData.data).slice(0, 15);
            info.innerHTML = `${{title}} (${{currentProvider}}) | Total: ${{pieData.total.toLocaleString()}} reproducciones`;

            const chart = new Chart(canvas, {{
                type: 'pie',
                data: {{
                    labels: entries.map(([name]) => name),
                    datasets: [{{
                        data: entries.map(([, count]) => count),
                        backgroundColor: colors.slice(0, entries.length),
                        borderColor: '#181825',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#cdd6f4', padding: 15, usePointStyle: true }} }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7', borderWidth: 1
                        }}
                    }}
                }}
            }});

            charts[canvasId] = chart;
        }}

        function renderPieChart(chartData, canvasId, infoId, title) {{
            if (!chartData?.data || Object.keys(chartData.data).length === 0) {{
                showNoDataMessage(canvasId, `No hay datos para ${{title}}`);
                return;
            }}

            const canvas = document.getElementById(canvasId);
            const info = document.getElementById(infoId);
            if (!canvas || !info) return;

            const entries = Object.entries(chartData.data).slice(0, 15);
            info.innerHTML = `${{title}} | Total: ${{chartData.total.toLocaleString()}} elementos compartidos`;

            const chart = new Chart(canvas, {{
                type: 'pie',
                data: {{
                    labels: entries.map(([name]) => name),
                    datasets: [{{
                        data: entries.map(([, count]) => count),
                        backgroundColor: colors.slice(0, entries.length),
                        borderColor: '#181825',
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#cdd6f4', padding: 15, usePointStyle: true }} }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7', borderWidth: 1
                        }}
                    }}
                }}
            }});

            charts[canvasId] = chart;
        }}

        function renderIndividualLineChart(canvasId, chartData, title) {{
            if (!chartData?.data || Object.keys(chartData.data).length === 0) {{
                showNoDataMessage(canvasId, `No hay datos para ${{title}}`);
                return;
            }}

            const canvas = document.getElementById(canvasId);
            if (!canvas) return;

            const datasets = [];
            let colorIndex = 0;

            // Top 5 elementos para line charts
            const sortedItems = Object.entries(chartData.data)
                .sort((a, b) => {{
                    const aTotal = Object.values(a[1]).reduce((sum, val) => sum + val, 0);
                    const bTotal = Object.values(b[1]).reduce((sum, val) => sum + val, 0);
                    return bTotal - aTotal;
                }})
                .slice(0, 5);

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

            const chart = new Chart(canvas, {{
                type: 'line',
                data: {{
                    labels: chartData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#cdd6f4', padding: 10, usePointStyle: true, font: {{ size: 10 }} }} }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7', borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            title: {{ display: true, text: 'Año', color: '#cdd6f4' }},
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        y: {{
                            title: {{ display: true, text: currentDataType === 'annual' ? 'Scrobbles/Año' : 'Scrobbles Acumulados', color: '#cdd6f4' }},
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }}
                    }}
                }}
            }});

            charts[canvasId] = chart;
        }}

        function renderEvolutionLineChart(canvasId, evolutionData, title) {{
            if (!evolutionData?.data || Object.keys(evolutionData.data).length === 0) {{
                showNoDataMessage(canvasId, `No hay datos para ${{title}}`);
                return;
            }}

            const canvas = document.getElementById(canvasId);
            if (!canvas) return;

            const datasets = [];
            let colorIndex = 0;

            Object.keys(evolutionData.data).forEach(user => {{
                datasets.push({{
                    label: user,
                    data: evolutionData.years.map(year => evolutionData.data[user][year] || 0),
                    borderColor: colors[colorIndex % colors.length],
                    backgroundColor: colors[colorIndex % colors.length] + '20',
                    tension: 0.4,
                    fill: false
                }});
                colorIndex++;
            }});

            const chart = new Chart(canvas, {{
                type: 'line',
                data: {{
                    labels: evolutionData.years,
                    datasets: datasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ position: 'bottom', labels: {{ color: '#cdd6f4', padding: 10, usePointStyle: true }} }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7', borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        y: {{
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }}
                    }}
                }}
            }});

            charts[canvasId] = chart;
        }}

        function renderGenresScatterCharts(scatterData, years, containerId, isAlbums = false) {{
            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = '';

            if (!scatterData || Object.keys(scatterData).length === 0) {{
                container.innerHTML = '<div class="no-data">No hay datos de scatter disponibles</div>';
                return;
            }}

            Object.keys(scatterData).forEach((genre, index) => {{
                const items = scatterData[genre];
                if (!items || items.length === 0) return;

                const genreContainer = document.createElement('div');
                genreContainer.className = 'genres-pie-container';

                const title = document.createElement('h4');
                title.textContent = `${{genre}} - Top ${{items.length}} ${{isAlbums ? 'Álbumes' : 'Artistas'}}`;
                genreContainer.appendChild(title);

                const canvasWrapper = document.createElement('div');
                canvasWrapper.className = 'scatter-chart-wrapper';

                const canvas = document.createElement('canvas');
                const canvasId = `scatterChart_${{genre.replace(/[^a-zA-Z0-9]/g, '_')}}_${{index}}_${{containerId}}`;
                canvas.id = canvasId;
                canvasWrapper.appendChild(canvas);

                genreContainer.appendChild(canvasWrapper);
                container.appendChild(genreContainer);

                const datasets = [];
                items.forEach((itemData, itemIndex) => {{
                    const points = [];
                    years.forEach(year => {{
                        const plays = itemData.yearly_data[year] || 0;
                        if (plays > 0) {{
                            points.push({{ x: year, y: plays }});
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
                    canvas.parentElement.innerHTML = '<div class="no-data">No hay datos temporales</div>';
                    return;
                }}

                charts[canvasId] = new Chart(canvas, {{
                    type: 'scatter',
                    data: {{ datasets }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{
                                type: 'linear',
                                position: 'bottom',
                                title: {{ display: true, text: 'Año', color: '#a6adc8' }},
                                ticks: {{ color: '#a6adc8', stepSize: 1 }},
                                grid: {{ color: '#313244' }},
                                min: Math.min(...years) - 0.5,
                                max: Math.max(...years) + 0.5
                            }},
                            y: {{
                                title: {{ display: true, text: 'Scrobbles', color: '#a6adc8' }},
                                ticks: {{ color: '#a6adc8' }},
                                grid: {{ color: '#313244' }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'bottom',
                                labels: {{ color: '#cdd6f4', padding: 8, usePointStyle: true, font: {{ size: 10 }} }}
                            }},
                            tooltip: {{
                                backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                                borderColor: '#cba6f7', borderWidth: 1
                            }}
                        }}
                    }}
                }});
            }});
        }}

        function renderLabelsScatterCharts(scatterData, years, containerId) {{
            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = '';

            if (!scatterData || Object.keys(scatterData).length === 0) {{
                container.innerHTML = '<div class="no-data">No hay datos de sellos disponibles</div>';
                return;
            }}

            Object.keys(scatterData).forEach((label, index) => {{
                const artists = scatterData[label];
                if (!artists || artists.length === 0) return;

                const labelContainer = document.createElement('div');
                labelContainer.className = 'genres-pie-container';

                const title = document.createElement('h4');
                title.textContent = `${{label}} - Top ${{artists.length}} Artistas`;
                labelContainer.appendChild(title);

                const canvasWrapper = document.createElement('div');
                canvasWrapper.className = 'scatter-chart-wrapper';

                const canvas = document.createElement('canvas');
                const canvasId = `labelScatterChart_${{label.replace(/[^a-zA-Z0-9]/g, '_')}}_${{index}}`;
                canvas.id = canvasId;
                canvasWrapper.appendChild(canvas);

                labelContainer.appendChild(canvasWrapper);
                container.appendChild(labelContainer);

                const datasets = [];
                artists.forEach((artistData, artistIndex) => {{
                    const points = [];
                    years.forEach(year => {{
                        const plays = artistData.yearly_data[year] || 0;
                        if (plays > 0) {{
                            points.push({{ x: year, y: plays }});
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
                    canvas.parentElement.innerHTML = '<div class="no-data">No hay datos temporales</div>';
                    return;
                }}

                charts[canvasId] = new Chart(canvas, {{
                    type: 'scatter',
                    data: {{ datasets }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {{
                            x: {{
                                type: 'linear',
                                position: 'bottom',
                                title: {{ display: true, text: 'Año', color: '#a6adc8' }},
                                ticks: {{ color: '#a6adc8', stepSize: 1 }},
                                grid: {{ color: '#313244' }},
                                min: Math.min(...years) - 0.5,
                                max: Math.max(...years) + 0.5
                            }},
                            y: {{
                                title: {{ display: true, text: 'Scrobbles', color: '#a6adc8' }},
                                ticks: {{ color: '#a6adc8' }},
                                grid: {{ color: '#313244' }}
                            }}
                        }},
                        plugins: {{
                            legend: {{
                                display: true,
                                position: 'bottom',
                                labels: {{ color: '#cdd6f4', padding: 8, usePointStyle: true, font: {{ size: 10 }} }}
                            }},
                            tooltip: {{
                                backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                                borderColor: '#cba6f7', borderWidth: 1
                            }}
                        }}
                    }}
                }});
            }});
        }}

        // FUNCIONES AUXILIARES
        function showNoDataMessage(elementId, message) {{
            const element = document.getElementById(elementId);
            if (element) {{
                const wrapper = element.closest('.chart-card') || element.parentElement;
                wrapper.innerHTML = `<div class="no-data">${{message}}</div>`;
            }}
        }}

        // FUNCIONES DE DISCOVERIES (copiadas del original funcional)
        async function loadDiscoveriesData(username) {{
            console.log(`✨ Cargando datos de novedades para ${{username}}...`);

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'block';
            if (gridElement) gridElement.style.display = 'none';

            try {{
                if (discoveriesData[username]) {{
                    console.log('📋 Usando datos del cache');
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }}

                const currentYear = new Date().getFullYear();
                const fromYear = currentYear - yearsBackConfig;
                const period = `${{fromYear}}-${{currentYear}}`;
                const dataUrl = `data/usuarios/${{period}}/${{username}}.json`;

                console.log(`📥 Cargando desde: ${{dataUrl}}`);

                const response = await fetch(dataUrl);
                if (!response.ok) throw new Error(`Error HTTP: ${{response.status}} - ${{dataUrl}}`);

                const userData = await response.json();
                console.log('📊 Datos cargados:', userData);

                discoveriesData[username] = userData;
                renderDiscoveriesCharts(userData);

            }} catch (error) {{
                console.error('❌ Error cargando novedades:', error);
                showDiscoveriesError(error.message);
            }}
        }}

        function renderDiscoveriesCharts(userData) {{
            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'none';
            if (gridElement) gridElement.style.display = 'grid';

            if (!userData?.discoveries) {{
                showDiscoveriesError('Datos de novedades inválidos');
                return;
            }}

            const discoveryTypes = [
                {{type: 'artists', canvasId: 'discoveriesArtistsChart', title: 'Nuevos Artistas'}},
                {{type: 'albums', canvasId: 'discoveriesAlbumsChart', title: 'Nuevos Álbumes'}},
                {{type: 'tracks', canvasId: 'discoveriesTracksChart', title: 'Nuevas Canciones'}},
                {{type: 'labels', canvasId: 'discoveriesLabelsChart', title: 'Nuevos Sellos'}}
            ];

            discoveryTypes.forEach(config => {{
                const typeData = userData.discoveries[config.type];
                if (typeData && Object.keys(typeData).length > 0) {{
                    renderDiscoveryChart(config.canvasId, typeData, config.title);
                }} else {{
                    showNoDataForDiscoveryChart(config.canvasId);
                }}
            }});
        }}

        function renderDiscoveryChart(canvasId, typeData, title) {{
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;

            const years = [];
            const counts = [];

            Object.keys(typeData).sort((a, b) => parseInt(a) - parseInt(b)).forEach(year => {{
                const yearInt = parseInt(year);
                if (!isNaN(yearInt) && typeData[year]) {{
                    years.push(yearInt);
                    counts.push(typeData[year].count || 0);
                }}
            }});

            if (years.length === 0 || counts.every(c => c === 0)) {{
                showNoDataForDiscoveryChart(canvasId);
                return;
            }}

            if (charts[canvasId]) {{
                charts[canvasId].destroy();
            }}

            charts[canvasId] = new Chart(canvas, {{
                type: 'line',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: title,
                        data: counts,
                        borderColor: '#cba6f7',
                        backgroundColor: 'rgba(203, 166, 247, 0.1)',
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
                        legend: {{ position: 'bottom', labels: {{ color: '#cdd6f4', padding: 15 }} }},
                        tooltip: {{
                            backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7', borderWidth: 1
                        }}
                    }},
                    scales: {{
                        x: {{
                            title: {{ display: true, text: 'Año', color: '#cdd6f4' }},
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        y: {{
                            title: {{ display: true, text: 'Novedades', color: '#cdd6f4' }},
                            ticks: {{ color: '#a6adc8', precision: 0 }},
                            grid: {{ color: '#313244' }},
                            beginAtZero: true
                        }}
                    }}
                }}
            }});
        }}

        function showDiscoveriesError(errorMessage) {{
            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'none';

            if (gridElement) {{
                gridElement.innerHTML = `<div class="no-data" style="grid-column: 1/-1; text-align: center; padding: 40px;">
                    <h4 style="color: #f38ba8; margin-bottom: 15px;">⚠ Error cargando novedades</h4>
                    <p style="color: #cdd6f4; margin-bottom: 10px;">No se pudieron cargar los datos de descubrimientos.</p>
                    <p style="font-size: 0.9em; color: #a6adc8;">${{errorMessage}}</p>
                </div>`;
                gridElement.style.display = 'grid';
            }}
        }}

        function showNoDataForDiscoveryChart(canvasId) {{
            const canvas = document.getElementById(canvasId);
            if (canvas) {{
                canvas.style.display = 'none';
                const wrapper = canvas.parentElement;
                if (wrapper) {{
                    wrapper.innerHTML = '<div class="no-data">Sin datos de descubrimientos</div>';
                }}
            }}
        }}

        console.log('✅ Aplicación COMPLETA con todos los gráficos cargada');
    </script>
</body>
</html>"""
