#!/usr/bin/env python3
"""
Last.fm User Stats Generator - VersiÃ³n FINAL con opciÃ³n de JSONs separados
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

# Importar generador de datos de novedades
try:
    from tools.users.user_stats_discoveries import DiscoveriesDataGenerator
except ImportError:
    print("âš ï¸  Generador de datos de novedades no encontrado.")
    DiscoveriesDataGenerator = None


def generate_discoveries_data(users, years_back, output_dir):
    """Genera archivos JSON de novedades para cada usuario"""
    if not DiscoveriesDataGenerator:
        print("âš ï¸  Saltando generaciÃ³n de datos de novedades (mÃ³dulo no disponible)")
        return False

    print(f"ðŸ“Š Generando datos de novedades...")

    try:
        generator = DiscoveriesDataGenerator()

        if not generator._check_tables():
            print("    âš ï¸  Tablas de primeras escuchas no encontradas.")
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
                print(f"    âŒ Error generando datos para {user}: {e}")

        generator._generate_index_file(discoveries_dir, users, period)
        generator.close()

        print(f"    âœ… Generados {len(generated_files)} archivos JSON")
        return True

    except Exception as e:
        print(f"    âŒ Error generando datos de novedades: {e}")
        return False


def modify_html_for_discoveries(html_content, users, years_back):
    """Modifica el HTML para agregar funcionalidad de novedades - mantiene estructura original"""
    import re

    current_year = datetime.now().year
    from_year = current_year - years_back
    period = f"{from_year}-{current_year}"

    print("ðŸ”§ Verificando funcionalidad de novedades en HTML...")

    # Verificar si ya tiene la pestaÃ±a de novedades
    if 'data-view="discoveries"' in html_content:
        print("  âœ… PestaÃ±a Novedades ya existe en el HTML")
    else:
        print("  âš ï¸  PestaÃ±a Novedades no encontrada (HTML antiguo)")
        # Solo agregar si no existe
        evolution_pattern = r'(<div class="nav-tab" data-view="evolution">.*?</div>)'
        matches = re.findall(evolution_pattern, html_content, re.DOTALL)
        if matches:
            evolution_tab = matches[0]
            discoveries_tab = '                <div class="nav-tab" data-view="discoveries">âœ¨ Novedades</div>'
            html_content = html_content.replace(evolution_tab, evolution_tab + '\n' + discoveries_tab, 1)
            print("  âœ… PestaÃ±a Novedades agregada")

    # Verificar si ya tiene el contenido del tab
    if 'id="discoveriesTab"' in html_content:
        print("  âœ… Contenido de novedades ya existe en el HTML")
    else:
        print("  âš ï¸  Contenido de novedades no encontrado (HTML antiguo)")
        # Solo agregar si no existe
        discoveries_content = f'''
            <div id="discoveriesTab" class="tab-content">
                <div class="evolution-section">
                    <h3>âœ¨ Descubrimientos Musicales</h3>

                    <div class="loading-spinner" id="discoveriesLoading" style="display: none; text-align: center; padding: 40px;">
                        <p>ðŸ”„ Cargando datos de novedades...</p>
                    </div>

                    <div class="discoveries-grid" id="discoveriesGrid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px;">
                        <div class="evolution-chart">
                            <h4>Nuevos Artistas por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesArtistsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Nuevos Ãlbumes por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesAlbumsChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Nuevas Canciones por AÃ±o</h4>
                            <div class="line-chart-wrapper">
                                <canvas id="discoveriesTracksChart"></canvas>
                            </div>
                        </div>

                        <div class="evolution-chart">
                            <h4>Nuevos Sellos por AÃ±o</h4>
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
        print("  âœ… Contenido de novedades agregado")

    print("ðŸŽ‰ HTML de novedades verificado")
    return html_content


def main():
    """FunciÃ³n principal - genera HTML completo con opciÃ³n de JSONs separados"""
    parser = argparse.ArgumentParser(
        description='Generador de estadÃ­sticas de usuarios Last.fm - HTML completo con JSONs opcionales'
    )
    parser.add_argument(
        '--years-back',
        type=int,
        default=5,
        help='NÃºmero de aÃ±os hacia atrÃ¡s (default: 5)'
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
        help='Guardar JSONs separados ademÃ¡s del HTML (para anÃ¡lisis)'
    )
    parser.add_argument(
        '--json-only',
        action='store_true',
        help='Usar JSONs existentes en vez de regenerar (mÃ¡s rÃ¡pido)'
    )
    parser.add_argument(
        '--db',
        type=str,
        default=None,
        help='Ruta a la base de datos SQLite (default: db/lastfm_cache.db)'
    )

    args = parser.parse_args()

    # Auto-generar nombre
    if args.output is None:
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        args.output = f'docs/usuarios/usuarios_{from_year}-{current_year}.html'

    try:
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            raise ValueError("LASTFM_USERS no configurada")

        print("ðŸŽµ Generador de estadÃ­sticas de usuarios")
        print(f"ðŸ‘¥ Usuarios: {', '.join(users)}")
        print(f"ðŸ“… AÃ±os: {args.years_back}")

        # Configurar directorios
        current_year = datetime.now().year
        from_year = current_year - args.years_back
        period = f"{from_year}-{current_year}"
        output_dir = os.path.dirname(args.output) or 'docs'
        data_dir = f"{output_dir}/data/usuarios/{period}"

        # Paso 1: Novedades
        discoveries_available = False
        if not args.skip_discoveries:
            discoveries_available = generate_discoveries_data(users, args.years_back, output_dir)

        # Paso 2: AnÃ¡lisis o carga de JSONs
        all_user_stats = {}

        if args.json_only:
            # Leer JSONs existentes
            print(f"ðŸ“‚ Leyendo JSONs existentes desde: {data_dir}")

            if not os.path.exists(data_dir):
                raise ValueError(f"âŒ Directorio {data_dir} no existe. Ejecuta sin --json-only primero.")

            for user in users:
                json_file = f"{data_dir}/{user}.json"
                if not os.path.exists(json_file):
                    raise ValueError(f"âŒ JSON no encontrado: {json_file}. Ejecuta sin --json-only primero.")

                print(f"  â€¢ Cargando {user}...")
                with open(json_file, 'r', encoding='utf-8') as f:
                    all_user_stats[user] = json.load(f)

                size_kb = os.path.getsize(json_file) / 1024
                print(f"    âœ“ LeÃ­do: {size_kb:.1f} KB")

        else:
            # Generar anÃ¡lisis normal
            database = UserStatsDatabaseExtended(args.db or 'db/lastfm_cache.db')
            analyzer = UserStatsAnalyzer(database, years_back=args.years_back)

            print(f"ðŸ“Š Analizando usuarios...")

            # Crear directorio JSON si se va a guardar
            if args.save_json:
                os.makedirs(data_dir, exist_ok=True)
                print(f"ðŸ’¾ JSONs adicionales en: {data_dir}")

            for user in users:
                print(f"  • {user}...")
                user_stats = analyzer.analyze_user(user, users)

                # ✓ DEBUG: Verificar datos de novedades
                if 'discoveries' in user_stats:
                    print(f"    ✅ Datos de novedades encontrados para {user}")
                    for disc_type, disc_data in user_stats['discoveries']['summary'].items():
                        total = disc_data.get('total', 0)
                        print(f"      - {disc_type}: {total} novedades")
                else:
                    print(f"    ❌ NO se encontraron datos de novedades para {user}")

                if 'individual' in user_stats and 'discoveries' in user_stats['individual']:
                    del user_stats['individual']['discoveries']

                all_user_stats[user] = user_stats

                # Guardar JSON si se solicita
                if args.save_json:
                    json_file = f"{data_dir}/{user}.json"
                    with open(json_file, 'w', encoding='utf-8') as f:
                        json.dump(user_stats, f, indent=2, ensure_ascii=False)
                    size_kb = os.path.getsize(json_file) / 1024
                    print(f"    âœ“ JSON: {size_kb:.1f} KB")

            database.close()

        # Paso 3: Generar HTML (COMPLETO, estructura original)
        print("ðŸŽ¨ Generando HTML completo...")
        from tools.users.user_stats_html_generator import UserStatsHTMLGenerator
        html_generator = UserStatsHTMLGenerator()
        html_content = html_generator.generate_html(all_user_stats, users, args.years_back)

        # Paso 4: Agregar novedades
        from tools.users.user_stats_html_novelties import add_discoveries_to_html
        html_content = add_discoveries_to_html(html_content)

        # Paso 5: Guardar
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Resumen
        html_size = os.path.getsize(args.output) / 1024 / 1024
        print(f"\nâœ… Generado: {args.output}")
        print(f"ðŸ“Š TamaÃ±o HTML: {html_size:.2f} MB")

        if args.save_json and not args.json_only:
            json_size = sum(os.path.getsize(f"{data_dir}/{u}.json")
                          for u in users if os.path.exists(f"{data_dir}/{u}.json"))
            json_size_mb = json_size / 1024 / 1024
            print(f"ðŸ“‚ TamaÃ±o JSONs: {json_size_mb:.2f} MB")
            print(f"ðŸ’¡ Total: {html_size + json_size_mb:.2f} MB")

        print(f"\nâœ¨ CaracterÃ­sticas:")
        print(f"  â€¢ Estructura HTML original completa")
        print(f"  â€¢ Todos los grÃ¡ficos y pestaÃ±as")
        print(f"  â€¢ EstÃ©tica original mantenida")
        if args.json_only:
            print(f"  â€¢ âš¡ GeneraciÃ³n rÃ¡pida (usando JSONs existentes)")
        if args.save_json:
            print(f"  â€¢ JSONs adicionales para anÃ¡lisis")
        if discoveries_available:
            print(f"  â€¢ PestaÃ±a de novedades incluida")

    except Exception as e:
        print(f"\nâŒ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
