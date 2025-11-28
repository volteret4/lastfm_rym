#!/usr/bin/env python3
"""
Last.fm User Stats Generator - Versión FINAL con opción de JSONs separados
Mantiene TODA la estructura HTML original, opcionalmente guarda JSONs aparte
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

# Importar las clases originales
from tools.users.user_stats_analyzer import UserStatsAnalyzer
from tools.users.user_stats_database_extended import UserStatsDatabaseExtended
from tools.users.user_stats_html_generator import UserStatsHTMLGenerator


from tools.users.user_stats_discoveries import DiscoveriesDataGenerator


def generate_discoveries_data(users, years_back, output_dir):
    """Genera archivos JSON de novedades para cada usuario"""
    if not DiscoveriesDataGenerator:
        print("⚠️  Saltando generación de datos de novedades (módulo no disponible)")
        return False

    print(f"📊 Generando datos de novedades...")

    try:
        generator = DiscoveriesDataGenerator()

        if not generator._check_tables():
            print("    ⚠️  Tablas de primeras escuchas no encontradas.")
            generator.close()
            return False

        current_year = datetime.now().year
        from_year = current_year - years_back
        to_year = current_year
        period = f"{from_year}-{to_year}"

        discoveries_dir = f"{output_dir}/data/usuarios/{period}"
        os.makedirs(discoveries_dir, exist_ok=True)

        generated_files = []
        for user in users:
            try:
                output_file = generator.generate_user_json(user, from_year, to_year, discoveries_dir)
                generated_files.append(output_file)
            except Exception as e:
                print(f"    ❌ Error generando datos para {user}: {e}")

        generator._generate_index_file(discoveries_dir, users, period)
        generator.close()

        print(f"    ✅ Generados {len(generated_files)} archivos JSON")
        return True

    except Exception as e:
        print(f"    ❌ Error generando datos de novedades: {e}")
        return False


def modify_html_for_discoveries(html_content, users, years_back):
    """Modifica el HTML para agregar funcionalidad de novedades - mantiene estructura original"""
    import re

    current_year = datetime.now().year
    from_year = current_year - years_back
    period = f"{from_year}-{current_year}"

    print("🔧 Modificando HTML para agregar novedades...")

    # 1. Agregar pestaña de novedades (solo una vez)
    evolution_pattern = r'(<div class="nav-tab" data-view="evolution">.*?</div>)'
    matches = re.findall(evolution_pattern, html_content, re.DOTALL)
    if matches:
        evolution_tab = matches[0]
        discoveries_tab = '                <div class="nav-tab" data-view="discoveries">✨ Novedades</div>'
        # Usar replace con count=1 para reemplazar solo la primera ocurrencia
        html_content = html_content.replace(evolution_tab, evolution_tab + '\n' + discoveries_tab, 1)
        print("  ✅ Pestaña Novedades agregada")

    # 2. Agregar contenido del tab (después del último tab-content)
    discoveries_content = f'''
            <div id="discoveriesTab" class="tab-content">
                <div class="evolution-section">
                    <h3>✨ Descubrimientos Musicales</h3>

                    <div class="loading-spinner" id="discoveriesLoading" style="display: none; text-align: center; padding: 40px;">
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

    # Buscar antes del popup
    popup_pattern = r'(<!-- Popup para mostrar detalles -->)'
    html_content = re.sub(popup_pattern, discoveries_content + r'\n\1', html_content, count=1)

    # 3. Agregar JavaScript para cargar novedades
    discoveries_js = f'''
        // Funcionalidad de novedades
        const DISCOVERIES_PERIOD = '{period}';
        let discoveriesData = null;

        async function loadDiscoveriesData(user) {{
            if (discoveriesData && discoveriesData.user === user) {{
                return discoveriesData;
            }}

            try {{
                const response = await fetch(`data/usuarios/${{DISCOVERIES_PERIOD}}/${{user}}.json`);
                if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
                discoveriesData = await response.json();
                return discoveriesData;
            }} catch (error) {{
                console.error('Error cargando novedades:', error);
                return null;
            }}
        }}

        function renderDiscoveriesTab() {{
            const user = selectedUser;
            if (!user) return;

            document.getElementById('discoveriesLoading').style.display = 'block';
            document.getElementById('discoveriesGrid').style.display = 'none';

            loadDiscoveriesData(user).then(data => {{
                document.getElementById('discoveriesLoading').style.display = 'none';

                if (!data) {{
                    document.getElementById('discoveriesGrid').innerHTML = '<p style="color: #a6adc8; text-align: center; padding: 40px;">No hay datos de novedades disponibles</p>';
                    document.getElementById('discoveriesGrid').style.display = 'block';
                    return;
                }}

                document.getElementById('discoveriesGrid').style.display = 'grid';

                // Renderizar gráficos
                renderDiscoveriesChart('discoveriesArtistsChart', data.discoveries.artists, 'Artistas');
                renderDiscoveriesChart('discoveriesAlbumsChart', data.discoveries.albums, 'Álbumes');
                renderDiscoveriesChart('discoveriesTracksChart', data.discoveries.tracks, 'Tracks');
                renderDiscoveriesChart('discoveriesLabelsChart', data.discoveries.labels, 'Sellos');
            }});
        }}

        function renderDiscoveriesChart(canvasId, discoveriesData, label) {{
            const canvas = document.getElementById(canvasId);
            if (!canvas) return;

            const years = Object.keys(discoveriesData).filter(k => !isNaN(k)).sort();
            const counts = years.map(year => discoveriesData[year].count || 0);

            if (discoveryCharts[canvasId]) {{
                discoveryCharts[canvasId].destroy();
            }}

            discoveryCharts[canvasId] = new Chart(canvas, {{
                type: 'bar',
                data: {{
                    labels: years,
                    datasets: [{{
                        label: label,
                        data: counts,
                        backgroundColor: COLORS[2],
                        borderColor: COLORS[2],
                        borderWidth: 2
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }},
                        x: {{
                            ticks: {{ color: '#a6adc8' }},
                            grid: {{ color: '#313244' }}
                        }}
                    }},
                    onClick: (event, elements) => {{
                        if (elements.length > 0) {{
                            const index = elements[0].index;
                            const year = years[index];
                            showDiscoveryPopup(year, discoveriesData[year], label);
                        }}
                    }}
                }}
            }});
        }}

        function showDiscoveryPopup(year, yearData, type) {{
            const items = yearData.items || [];
            const hasMore = yearData.has_more || false;

            let itemsHTML = items.map(item => `
                <div style="padding: 10px; border-bottom: 1px solid #313244;">
                    <div style="color: #cdd6f4;">${{item.name}}</div>
                    <div style="color: #a6adc8; font-size: 0.9em;">${{item.date}}</div>
                </div>
            `).join('');

            if (hasMore) {{
                itemsHTML += `<div style="padding: 10px; text-align: center; color: #a6adc8;">
                    ... y ${{yearData.count - 10}} más
                </div>`;
            }}

            showPopup(`${{type}} descubiertos en ${{year}}`, itemsHTML);
        }}

        const discoveryCharts = {{}};
'''

    # Insertar antes del cierre del script
    script_end_pattern = r'(\s*</script>\s*</body>\s*</html>""")'
    html_content = re.sub(script_end_pattern, discoveries_js + r'\n\1', html_content, count=1)

    print("🎉 Modificación del HTML completada")
    return html_content


def main():
    """Función principal - genera HTML completo con opción de JSONs separados"""
    parser = argparse.ArgumentParser(
        description='Generador de estadísticas de usuarios Last.fm - HTML completo con JSONs opcionales'
    )
    parser.add_argument(
        '--years-back',
        type=int,
        default=5,
        help='Número de años hacia atrás (default: 5)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Archivo HTML de salida (default: auto)'
    )
    parser.add_argument(
        '--skip-discoveries',
        action='store_true',
        help='Omitir novedades'
    )
    parser.add_argument(
        '--save-json',
        action='store_true',
        help='Guardar JSONs separados además del HTML (para análisis)'
    )

    args = parser.parse_args()

    # Auto-generar nombre
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/usuarios_{from_year}-{current_year}.html'

    try:
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            raise ValueError("LASTFM_USERS no configurada")

        print("🎵 Generador de estadísticas de usuarios")
        print(f"👥 Usuarios: {', '.join(users)}")
        print(f"📅 Años: {args.years_back}")

        # Paso 1: Novedades
        discoveries_available = False
        if not args.skip_discoveries:
            output_dir = os.path.dirname(args.output) or 'docs'
            discoveries_available = generate_discoveries_data(users, args.years_back, output_dir)

        # Paso 2: Análisis
        database = UserStatsDatabaseExtended()
        analyzer = UserStatsAnalyzer(database, years_back=args.years_back)
        html_generator = UserStatsHTMLGenerator()

        print(f"📊 Analizando usuarios...")
        all_user_stats = {}

        # Configurar directorio JSON si se solicita
        if args.save_json:
            current_year = datetime.now().year
            from_year = current_year - args.years_back
            period = f"{from_year}-{current_year}"
            output_dir = os.path.dirname(args.output) or 'docs'
            data_dir = f"{output_dir}/data/usuarios/{period}"
            os.makedirs(data_dir, exist_ok=True)
            print(f"💾 JSONs adicionales en: {data_dir}")

        for user in users:
            print(f"  • {user}...")
            user_stats = analyzer.analyze_user(user, users)

            if 'individual' in user_stats and 'discoveries' in user_stats['individual']:
                del user_stats['individual']['discoveries']

            all_user_stats[user] = user_stats

            # Guardar JSON si se solicita
            if args.save_json:
                json_file = f"{data_dir}/{user}_stats.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(user_stats, f, indent=2, ensure_ascii=False)
                size_kb = os.path.getsize(json_file) / 1024
                print(f"    ✓ JSON: {size_kb:.1f} KB")

        database.close()

        # Paso 3: Generar HTML (COMPLETO, estructura original)
        print("🎨 Generando HTML completo...")
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Paso 4: Agregar novedades
        if discoveries_available:
            print("✨ Integrando novedades...")
            html_content = modify_html_for_discoveries(html_content, users, args.years_back)

        # Paso 5: Guardar
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Resumen
        html_size = os.path.getsize(args.output) / 1024 / 1024
        print(f"\n✅ Generado: {args.output}")
        print(f"📊 Tamaño HTML: {html_size:.2f} MB")

        if args.save_json:
            json_size = sum(os.path.getsize(f"{data_dir}/{u}_stats.json")
                          for u in users if os.path.exists(f"{data_dir}/{u}_stats.json"))
            json_size_mb = json_size / 1024 / 1024
            print(f"📂 Tamaño JSONs: {json_size_mb:.2f} MB")
            print(f"💡 Total: {html_size + json_size_mb:.2f} MB")

        print(f"\n✨ Características:")
        print(f"  • Estructura HTML original completa")
        print(f"  • Todos los gráficos y pestañas")
        print(f"  • Estética original mantenida")
        if args.save_json:
            print(f"  • JSONs adicionales para análisis")
        if discoveries_available:
            print(f"  • Pestaña de novedades incluida")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
