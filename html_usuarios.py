#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión FINAL con conteos únicos correctos + NOVEDADES CORREGIDA
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
import re

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

# Importar generador de datos de novedades
try:
    sys.path.append(os.path.dirname(__file__))
    from generate_discoveries_data import DiscoveriesDataGenerator
except ImportError:
    print("⚠️  Generador de datos de novedades no encontrado. La funcionalidad de novedades no estará disponible.")
    DiscoveriesDataGenerator = None


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
            print("💡 Ejecuta: python create_first_listen_tables_mbid.py")
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
    """Modifica el HTML generado para agregar la funcionalidad de novedades - VERSIÓN CORREGIDA"""

    print("🔧 Modificando HTML para agregar funcionalidad de novedades...")

    # 1. Verificar que el HTML base tenga la estructura esperada
    if 'nav-tabs' not in html_content:
        print("⚠️  Estructura nav-tabs no encontrada en HTML")
        return html_content

    # 2. Agregar pestaña de novedades en nav-tabs de forma más robusta
    # Buscar el patrón específico de la pestaña evolution
    evolution_patterns = [
        r'(<div class="nav-tab" data-view="evolution">.*?</div>)',
        r'(<div class="nav-tab" data-view="evolution">[^<]*📈[^<]*</div>)',
        r'(data-view="evolution">[^<]*</div>)'
    ]

    tab_added = False
    for pattern in evolution_patterns:
        matches = re.findall(pattern, html_content, re.DOTALL)
        if matches:
            evolution_tab = matches[0]
            discoveries_tab = '                <div class="nav-tab" data-view="discoveries">✨ Novedades</div>'
            html_content = html_content.replace(evolution_tab, evolution_tab + '\n' + discoveries_tab)
            print("  ✅ Pestaña Novedades agregada")
            tab_added = True
            break

    if not tab_added:
        print("  ⚠️  No se pudo agregar la pestaña Novedades")
        return html_content

    # 3. Agregar el contenido del tab de discoveries de forma más robusta
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
            </div>

        '''

    # Buscar diferentes patrones posibles donde insertar el contenido
    insertion_patterns = [
        # Patrón más específico primero
        r'(</div>\s*</div>\s*</div>\s*</div>\s*<!-- Popup para mostrar detalles -->)',
        # Patrones más generales como fallback
        r'(</div>\s*</div>\s*</div>\s*<!-- Popup para mostrar detalles -->)',
        r'(</div>\s*<!-- Popup para mostrar detalles -->)',
        r'(<!-- Popup para mostrar detalles -->)',
        # Si no encuentra popup, buscar antes del cierre del contenedor principal
        r'(</div>\s*</div>\s*<script>)',
        r'(</div>\s*<script>)'
    ]

    content_inserted = False
    for pattern in insertion_patterns:
        matches = re.findall(pattern, html_content, re.DOTALL)
        if matches:
            before_insertion = matches[0]
            html_content = html_content.replace(before_insertion, discoveries_content + '\n        ' + before_insertion)
            print("  ✅ Contenido del tab Novedades agregado")
            content_inserted = True
            break

    if not content_inserted:
        print("  ⚠️  No se pudo insertar el contenido del tab")
        return html_content

    # 4. Agregar variables JavaScript necesarias de forma más robusta
    js_vars_patterns = [
        r'(let genresData = null;[^\n]*)',
        r'(let charts = \{\}[^;]*;)',
        r'(// Variables globales[^\n]*)'
    ]

    vars_added = False
    for pattern in js_vars_patterns:
        matches = re.findall(pattern, html_content)
        if matches:
            original_line = matches[0]
            new_vars = f'''{original_line}
        let discoveriesData = {{}}; // Cache para datos de novedades
        const yearsBackConfig = {years_back}; // Configuración de años'''
            html_content = html_content.replace(original_line, new_vars)
            print("  ✅ Variables JavaScript agregadas")
            vars_added = True
            break

    if not vars_added:
        print("  ⚠️  No se pudieron agregar las variables JavaScript")

    # 5. Modificar setupNavigation para manejar discoveries de forma más robusta
    setup_patterns = [
        r'(// Re-render para la nueva vista\s*if \(currentUser\) \{\{\s*selectUser\(currentUser\);\s*\}\})',
        r'(if \(currentUser\) \{\{\s*selectUser\(currentUser\);\s*\}\})',
        r'(selectUser\(currentUser\);)'
    ]

    setup_modified = False
    for pattern in setup_patterns:
        matches = re.findall(pattern, html_content, re.DOTALL)
        if matches:
            original_setup = matches[0]

            new_setup = '''// Re-render para la nueva vista
                    if (currentUser) {
                        if (view === 'discoveries') {
                            loadDiscoveriesData(currentUser);
                        } else {
                            selectUser(currentUser);
                        }
                    }'''

            html_content = html_content.replace(original_setup, new_setup)
            print("  ✅ setupNavigation modificado")
            setup_modified = True
            break

    if not setup_modified:
        print("  ⚠️  No se pudo modificar setupNavigation")

    # 6. Agregar funciones JavaScript para novedades antes del cierre del script
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
                    console.log('Usando datos del cache');
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }}

                const currentYear = new Date().getFullYear();
                const fromYear = currentYear - yearsBackConfig;
                const period = `${{fromYear}}-${{currentYear}}`;
                const dataUrl = `data/usuarios/${{period}}/${{username}}.json`;

                console.log(`Cargando desde: ${{dataUrl}}`);

                const response = await fetch(dataUrl);
                if (!response.ok) throw new Error(`Error HTTP: ${{response.status}} - ${{dataUrl}}`);

                const userData = await response.json();
                console.log('Datos cargados:', userData);

                discoveriesData[username] = userData;
                renderDiscoveriesCharts(userData);

            }} catch (error) {{
                console.error('Error cargando novedades:', error);
                showDiscoveriesError(error.message);
            }}
        }}

        function renderDiscoveriesCharts(userData) {{
            console.log('Renderizando gráficos de novedades...');

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
                if (typeData && Object.keys(typeData).length > 0) {{
                    console.log(`Renderizando ${{config.type}}:`, typeData);
                    renderDiscoveryChart(config.canvasId, typeData, config.title);
                }} else {{
                    console.log(`Sin datos para ${{config.type}}`);
                    showNoDataForChart(config.canvasId);
                }}
            }});
        }}

        function renderDiscoveryChart(canvasId, typeData, title) {{
            const canvas = document.getElementById(canvasId);
            if (!canvas) {{
                console.error(`Canvas ${{canvasId}} no encontrado`);
                return;
            }}

            console.log(`Renderizando gráfico ${{canvasId}} con datos:`, typeData);

            const years = [];
            const counts = [];
            const details = {{}};

            // Procesar datos por año
            Object.keys(typeData).sort((a, b) => parseInt(a) - parseInt(b)).forEach(year => {{
                const yearInt = parseInt(year);
                if (!isNaN(yearInt) && typeData[year]) {{
                    years.push(yearInt);
                    counts.push(typeData[year].count || 0);
                    details[yearInt] = typeData[year].items || [];
                }}
            }});

            if (years.length === 0 || counts.every(c => c === 0)) {{
                console.log(`Sin datos válidos para ${{canvasId}}`);
                showNoDataForChart(canvasId);
                return;
            }}

            console.log(`Años: ${{years}}, Conteos: ${{counts}}`);

            const config = {{
                type: 'line',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: title,
                        data: counts,
                        borderColor: '#cba6f7',
                        backgroundColor: '#cba6f730',
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
                            labels: {{color: '#cdd6f4', padding: 15}}
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
                            title: {{display: true, text: 'Año', color: '#cdd6f4'}},
                            ticks: {{color: '#a6adc8'}},
                            grid: {{color: '#313244'}}
                        }},
                        y: {{
                            title: {{display: true, text: 'Novedades', color: '#cdd6f4'}},
                            ticks: {{color: '#a6adc8', precision: 0}},
                            grid: {{color: '#313244'}},
                            beginAtZero: true
                        }}
                    }},
                    onClick: function(event, elements) {{
                        if (elements.length > 0) {{
                            const pointIndex = elements[0].index;
                            const year = this.data.labels[pointIndex];
                            const count = this.data.datasets[0].data[pointIndex];

                            console.log(`Click en año ${{year}}, count: ${{count}}`);

                            if (count > 0 && details[year] && details[year].length > 0) {{
                                showDiscoveryPopup(year, details[year], title, count);
                            }}
                        }}
                    }}
                }}
            }};

            // Destruir gráfico existente si existe
            if (charts[canvasId]) {{
                console.log(`Destruyendo gráfico existente ${{canvasId}}`);
                charts[canvasId].destroy();
                delete charts[canvasId];
            }}

            console.log(`Creando nuevo gráfico ${{canvasId}}`);
            charts[canvasId] = new Chart(canvas, config);
        }}

        function showDiscoveryPopup(year, items, title, count) {{
            console.log(`Mostrando popup para ${{title}} - ${{year}}:`, items);

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
            console.error('Error en novedades:', errorMessage);

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'none';

            if (gridElement) {{
                gridElement.innerHTML = `<div class="no-data" style="grid-column: 1/-1; text-align: center; padding: 40px;">
                    <h4 style="color: #f38ba8; margin-bottom: 15px;">❌ Error cargando novedades</h4>
                    <p style="color: #cdd6f4; margin-bottom: 10px;">No se pudieron cargar los datos de descubrimientos.</p>
                    <p style="font-size: 0.9em; color: #a6adc8; margin-bottom: 10px;">${{errorMessage}}</p>
                    <p style="font-size: 0.8em; color: #6c7086;">
                        Ejecuta: <code style="background: #313244; padding: 2px 6px; border-radius: 4px;">python create_first_listen_tables_mbid.py</code>
                    </p>
                </div>`;
                gridElement.style.display = 'grid';
            }}
        }}

        function showNoDataForChart(canvasId) {{
            const canvas = document.getElementById(canvasId);
            if (canvas) {{
                canvas.style.display = 'none';
                const wrapper = canvas.parentElement;
                wrapper.innerHTML = '<div class="no-data" style="height: 200px; display: flex; align-items: center; justify-content: center; color: #a6adc8; font-style: italic;">Sin datos de descubrimientos</div>';
            }}
        }}
'''

    # Buscar el cierre del script de forma más robusta
    script_end_patterns = [
        r'(\s*</script>\s*</body>\s*</html>"""\s*$)',
        r'(\s*</script>\s*</body>\s*</html>)',
        r'(\s*</script>)',
        r'(</body>\s*</html>""")'
    ]

    js_added = False
    for pattern in script_end_patterns:
        matches = re.findall(pattern, html_content, re.MULTILINE | re.DOTALL)
        if matches:
            script_end = matches[0]
            html_content = html_content.replace(script_end, discoveries_js + '\n' + script_end)
            print("  ✅ Funciones JavaScript de novedades agregadas")
            js_added = True
            break

    if not js_added:
        print("  ⚠️  No se pudieron agregar las funciones JavaScript")

    print("🎉 Modificación del HTML completada")
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
            print(f"  • ✨ NUEVO: Filtro MBID para artistas únicos válidos")
        else:
            print(f"  • ⚠️  Novedades omitidas (usar --skip-discoveries=false y ejecutar create_first_listen_tables_mbid.py)")

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
            print(f"  6. Solo se consideran artistas con MBID válido")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
