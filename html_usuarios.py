#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión FINAL con conteos únicos correctos + NOVEDADES
Genera estadísticas individuales de usuarios usando clases extendidas + pestaña de novedades integrada
"""

import os
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

# Importar las clases como propones
from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database_extended import UserStatsDatabaseExtended
from tools.users.user_stats_html_generator import UserStatsHTMLGeneratorFixed
from tools.users.user_stats_discoveries import DiscoveriesDataGenerator



def generate_discoveries_data(users: List[str], years_back: int, output_dir: str) -> bool:
    """Genera archivos JSON de novedades para cada usuario"""
    if not DiscoveriesDataGenerator:
        print("⚠️  Saltando generación de datos de novedades (módulo no disponible)")
        return False

    print(f"📊 Generando datos de novedades (top 10 por año)...")

    try:
        generator = DiscoveriesDataGenerator()

        # Verificar que las tablas de primeras escuchas existan
        if not generator._check_tables():
            print("⚠️  Tablas de primeras escuchas no encontradas.")
            print("💡 Ejecuta: python create_first_listen_tables.py")
            generator.close()
            return False

        # Crear directorio específico para el periodo
        current_year = datetime.now().year
        from_year = current_year - years_back
        to_year = current_year
        period = f"{from_year}-{to_year}"

        discoveries_dir = f"{output_dir}/data/usuarios/{period}"
        os.makedirs(discoveries_dir, exist_ok=True)

        # Generar archivos JSON para cada usuario
        generated_files = []
        for user in users:
            try:
                output_file = generator.generate_user_json(user, from_year, to_year, discoveries_dir)
                generated_files.append(output_file)
            except Exception as e:
                print(f"    ❌ Error generando datos para {user}: {e}")

        # Generar archivo índice
        index_file = generator._generate_index_file(discoveries_dir, users, period)

        generator.close()

        print(f"    ✅ Generados {len(generated_files)} archivos JSON")
        print(f"    📁 Directorio: {discoveries_dir}")

        return True

    except Exception as e:
        print(f"    ❌ Error generando datos de novedades: {e}")
        return False


def modify_html_for_discoveries(html_content: str, users: List[str], years_back: int) -> str:
    """Modifica el HTML generado para agregar la funcionalidad de novedades"""

    # 1. Agregar pestaña de novedades en nav-tabs
    discoveries_tab = '                <div class="nav-tab" data-view="discoveries">✨ Novedades</div>'

    # Buscar donde está la pestaña de evolución y agregar después
    evolution_tab = 'data-view="evolution">📈 Evolución</div>'
    if evolution_tab in html_content:
        html_content = html_content.replace(
            evolution_tab,
            evolution_tab + '\n' + discoveries_tab
        )

    # 2. Agregar el contenido del tab de discoveries
    discoveries_content = f'''
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
            </div>'''

    # Buscar donde termina evolutionTab y agregar después
    evolution_end = '            </div>\n\n        </div>'
    if evolution_end in html_content:
        html_content = html_content.replace(evolution_end, evolution_end + discoveries_content + '\n\n')

    # 3. Agregar variables JavaScript necesarias
    js_vars = f'''
        let discoveriesData = {{}}; // Cache para datos de novedades
        const yearsBackConfig = {years_back}; // Configuración de años
'''

    # Buscar donde están las variables JavaScript y agregar
    existing_vars = 'let genresData = null;'
    if existing_vars in html_content:
        html_content = html_content.replace(existing_vars, existing_vars + '\n        ' + js_vars)

    # 4. Modificar setupNavigation para manejar discoveries
    original_setup = '''                    // Re-render para la nueva vista
                    if (currentUser) {
                        selectUser(currentUser);
                    }'''

    new_setup = '''                    // Re-render para la nueva vista
                    if (currentUser) {
                        if (view === 'discoveries') {
                            loadDiscoveriesData(currentUser);
                        } else {
                            selectUser(currentUser);
                        }
                    }'''

    if original_setup in html_content:
        html_content = html_content.replace(original_setup, new_setup)

    # 5. Agregar funciones JavaScript para novedades
    discoveries_js = f'''
        // 🆕 Funciones para manejo de novedades
        async function loadDiscoveriesData(username) {{
            console.log(`Cargando datos de novedades para ${{username}}...`);

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'block';
            if (gridElement) gridElement.style.display = 'none';

            try {{
                if (discoveriesData[username]) {{
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }}

                const currentYear = new Date().getFullYear();
                const fromYear = currentYear - yearsBackConfig;
                const period = `${{fromYear}}-${{currentYear}}`;
                const dataUrl = `data/usuarios/${{period}}/${{username}}.json`;

                const response = await fetch(dataUrl);
                if (!response.ok) throw new Error(`Error HTTP: ${{response.status}}`);

                const userData = await response.json();
                discoveriesData[username] = userData;
                renderDiscoveriesCharts(userData);

            }} catch (error) {{
                console.error('Error:', error);
                showDiscoveriesError(error.message);
            }}
        }}

        function renderDiscoveriesCharts(userData) {{
            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'none';
            if (gridElement) gridElement.style.display = 'grid';

            const discoveryTypes = [
                {{type: 'artists', canvasId: 'discoveriesArtistsChart', title: 'Nuevos Artistas'}},
                {{type: 'albums', canvasId: 'discoveriesAlbumsChart', title: 'Nuevos Álbumes'}},
                {{type: 'tracks', canvasId: 'discoveriesTracksChart', title: 'Nuevas Canciones'}},
                {{type: 'labels', canvasId: 'discoveriesLabelsChart', title: 'Nuevos Sellos'}}
            ];

            discoveryTypes.forEach(config => {{
                const typeData = userData.discoveries[config.type];
                if (typeData) {{
                    renderDiscoveryChart(config.canvasId, typeData, config.title);
                }} else {{
                    showNoDataForChart(config.canvasId);
                }}
            }});
        }}

        function renderDiscoveryChart(canvasId, typeData, title) {{
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;

            const years = [];
            const counts = [];
            const details = {{}};

            Object.keys(typeData).sort((a, b) => parseInt(a) - parseInt(b)).forEach(year => {{
                if (!isNaN(year)) {{
                    const yearInt = parseInt(year);
                    years.push(yearInt);
                    counts.push(typeData[year].count || 0);
                    details[yearInt] = typeData[year].items || [];
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
                        label: title,
                        data: counts,
                        borderColor: '#cba6f7',
                        backgroundColor: '#cba6f7' + '30',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 6,
                        pointHoverRadius: 10
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{position: 'bottom', labels: {{color: '#cdd6f4'}}}},
                        tooltip: {{backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4'}}
                    }},
                    scales: {{
                        x: {{title: {{display: true, text: 'Año', color: '#cdd6f4'}}, ticks: {{color: '#a6adc8'}}}},
                        y: {{title: {{display: true, text: 'Novedades', color: '#cdd6f4'}}, ticks: {{color: '#a6adc8'}}, beginAtZero: true}}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const pointIndex = elements[0].index;
                            const year = this.data.labels[pointIndex];
                            const count = this.data.datasets[0].data[pointIndex];

                            if (count > 0 && details[year]) {{
                                showDiscoveryPopup(year, details[year], title, count);
                            }}
                        }}
                    }}
                }}
            }};

            if (charts[canvasId]) charts[canvasId].destroy();
            charts[canvasId] = new Chart(canvas, config);
        }}

        function showDiscoveryPopup(year, items, title, count) {{
            const popupTitle = `${{title}} - ${{year}} (${{count}} nuevos)`;
            let content = '';

            items.forEach(item => {{
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

        function showDiscoveriesError(errorMessage) {{
            const gridElement = document.getElementById('discoveriesGrid');
            if (gridElement) {{
                gridElement.innerHTML = `<div class="no-data" style="grid-column: 1/-1;">
                    <p>❌ Error: ${{errorMessage}}</p>
                    <p style="font-size: 0.8em; color: #6c7086;">Ejecuta: python create_first_listen_tables.py</p>
                </div>`;
                gridElement.style.display = 'grid';
            }}
        }}

        function showNoDataForChart(canvasId) {{
            const canvas = document.getElementById(canvasId);
            if (canvas) {{
                canvas.style.display = 'none';
                canvas.parentElement.innerHTML = '<div class="no-data">Sin datos</div>';
            }}
        }}
'''

    # Agregar las funciones antes del cierre del script
    script_end = '    </script>'
    if script_end in html_content:
        html_content = html_content.replace(script_end, discoveries_js + '\n' + script_end)

    return html_content


def main():
    """Función principal para generar estadísticas de usuarios con conteos únicos CORRECTOS + NOVEDADES"""
    parser = argparse.ArgumentParser(description='Generador de estadísticas individuales de usuarios de Last.fm + Novedades')
    parser.add_argument('--years-back', type=int, default=5,
                       help='Número de años hacia atrás para analizar (por defecto: 5)')
    parser.add_argument('--output', type=str, default=None,
                       help='Archivo de salida HTML (por defecto: auto-generado con fecha)')
    parser.add_argument('--skip-discoveries', action='store_true',
                       help='Omitir generación de datos de novedades')
    args = parser.parse_args()

    # Auto-generar nombre de archivo si no se especifica
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/usuarios_{from_year}-{current_year}.html'

    try:
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            raise ValueError("LASTFM_USERS no encontrada en las variables de entorno")

        print("🎵 Iniciando análisis de usuarios con conteos únicos CORRECTOS + NOVEDADES...")

        # Paso 1: Generar datos de novedades si no se salta
        discoveries_available = False
        if not args.skip_discoveries:
            output_dir = os.path.dirname(args.output) or 'docs'
            discoveries_available = generate_discoveries_data(users, args.years_back, output_dir)

        # Paso 2: Usar base de datos extendida con funciones adicionales
        database = UserStatsDatabaseExtended()
        analyzer = UserStatsAnalyzer(database, years_back=args.years_back)
        html_generator = UserStatsHTMLGeneratorFixed()

        # Paso 3: Analizar estadísticas para todos los usuarios
        print(f"👤 Analizando {len(users)} usuarios...")
        all_user_stats = {}

        for user in users:
            print(f"  • Procesando {user}...")
            user_stats = analyzer.analyze_user(user, users)

            # Remover datos de novedades del JSON principal para optimizar
            if 'individual' in user_stats and 'discoveries' in user_stats['individual']:
                del user_stats['individual']['discoveries']

            all_user_stats[user] = user_stats

        # Paso 4: Generar HTML base
        print("🎨 Generando HTML con conteos únicos...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Paso 5: Modificar HTML para agregar novedades si están disponibles
        if discoveries_available:
            print("✨ Integrando funcionalidad de novedades...")
            html_content = modify_html_for_discoveries(html_content, users, args.years_back)

        # Paso 6: Guardar archivo
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Calcular tamaño del archivo
        file_size = os.path.getsize(args.output) / 1024 / 1024  # MB

        print(f"✅ Archivo generado: {args.output} ({file_size:.2f} MB)")
        print(f"📊 Características FINALES:")
        print(f"  • Géneros diferenciados por proveedor (Last.fm, MusicBrainz, Discogs)")
        print(f"  • Gráficos scatter con leyendas visibles y márgenes adecuados")
        print(f"  • Soporte para géneros de álbumes por separado")
        print(f"  • Sección de sellos completamente funcional")
        print(f"  • Manejo mejorado de datos vacíos")
        print(f"  • ✅ CORREGIDO: Gráficos de géneros se muestran correctamente")
        print(f"  • ✅ RESTAURADO: Funciones completas de scatter charts")
        print(f"  • ✅ RESTAURADO: Funciones completas de evolución")
        print(f"  • ✅ AÑADIDO: Popups interactivos con detalles")
        print(f"  • ✅ NUEVO: Conteos únicos reales del usuario (SOLUCIONADO)")
        if discoveries_available:
            print(f"  • ✨ NUEVO: Pestaña de Novedades integrada con carga dinámica")
            print(f"  • ✨ NUEVO: Popups con top 10 descubrimientos por año")
        else:
            print(f"  • ⚠️  Novedades omitidas (usar --skip-discoveries=false y ejecutar create_first_listen_tables.py)")

        # Mostrar resumen con conteos reales
        print(f"\n📈 Resumen con conteos únicos REALES:")
        for user, stats in all_user_stats.items():
            total_scrobbles = sum(stats['yearly_scrobbles'].values())

            # Mostrar conteos únicos reales
            if 'unique_counts' in stats:
                unique_counts = stats['unique_counts']
                print(f"  • {user}: {total_scrobbles:,} scrobbles")
                print(f"    - ✅ {unique_counts['total_artists']} artistas únicos")
                print(f"    - ✅ {unique_counts['total_albums']} álbumes únicos")
                print(f"    - ✅ {unique_counts['total_tracks']} canciones únicas")

                # Mostrar información sobre géneros por proveedor
                if 'genres' in stats:
                    for provider in ['lastfm', 'musicbrainz', 'discogs']:
                        if provider in stats['genres']:
                            provider_data = stats['genres'][provider]
                            if 'pie_chart' in provider_data and provider_data['pie_chart']['total'] > 0:
                                genres_count = len(provider_data['pie_chart']['data'])
                                print(f"    - {provider}: {genres_count} géneros")

                # Mostrar información sobre sellos
                if 'labels' in stats and 'pie_chart' in stats['labels']:
                    labels_count = len(stats['labels']['pie_chart']['data'])
                    print(f"    - {labels_count} sellos discográficos")
            else:
                print(f"  • {user}: {total_scrobbles:,} scrobbles (❌ sin conteos únicos)")

        database.close()

        if discoveries_available:
            print(f"\n🎯 Uso de la funcionalidad de Novedades:")
            print(f"  1. Abre {args.output}")
            print(f"  2. Selecciona un usuario (botón 👤 con iconos)")
            print(f"  3. Ve a la pestaña '✨ Novedades'")
            print(f"  4. Los datos se cargarán automáticamente")
            print(f"  5. Haz click en puntos de los gráficos para ver detalles")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
