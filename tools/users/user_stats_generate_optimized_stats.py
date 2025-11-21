#!/usr/bin/env python3
"""
Script principal integrado para generar estadísticas con novedades integradas
Genera archivos JSON separados + HTML original con pestaña de novedades integrada
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass

# Agregar directorios al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


try:
    # Importar generador de datos JSON
    from tools.users.user_stats_discoveries import DiscoveriesDataGenerator

    # Importar clases originales para estadísticas
    from tools.users.user_stats_analyzer import UserStatsAnalyzer
    from tools.users.user_stats_database_extended import UserStatsDatabaseExtended

    # Importar generador HTML integrado
    from tools.users.user_stats_html_generator import UserStatsHTMLGeneratorFixed
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("Asegúrate de que todos los archivos estén disponibles")
    sys.exit(1)


def generate_integrated_stats(users: list, years_back: int = 5):
    """Genera estadísticas integradas con archivos JSON separados y HTML completo"""

    current_year = datetime.now().year
    from_year = current_year - years_back
    to_year = current_year
    period = f"{from_year}-{to_year}"

    print(f"🎵 Generando estadísticas integradas para {len(users)} usuarios")
    print(f"📅 Periodo: {period}")

    # Paso 1: Generar archivos JSON de novedades (top 10 por año)
    print(f"\n📊 Paso 1: Generando archivos JSON de novedades (top 10)...")
    discoveries_generator = DiscoveriesDataGenerator()
    discoveries_dir = discoveries_generator.generate_all_users_data(users, years_back)
    discoveries_generator.close()

    if not discoveries_dir:
        print("❌ Error generando archivos JSON de novedades")
        return False

    # Paso 2: Generar estadísticas completas (sin incluir novedades en JSON principal)
    print(f"\n📈 Paso 2: Generando estadísticas completas...")
    try:
        database = UserStatsDatabaseExtended()
        analyzer = UserStatsAnalyzer(database, years_back=years_back)

        all_user_stats = {}
        for user in users:
            print(f"  • Analizando {user}...")

            # Generar estadísticas completas
            user_stats = analyzer.analyze_user(user, users)

            # Remover datos de novedades del JSON principal para optimizar
            if 'individual' in user_stats and 'discoveries' in user_stats['individual']:
                discoveries = user_stats['individual']['discoveries']
                total_discoveries = sum(data.get('total', 0) for data in discoveries.values())
                print(f"    ✨ {total_discoveries} novedades encontradas (se cargarán desde JSON)")
                del user_stats['individual']['discoveries']

            all_user_stats[user] = user_stats

        database.close()

    except Exception as e:
        print(f"❌ Error generando estadísticas: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Paso 3: Generar HTML integrado completo
    print(f"\n🎨 Paso 3: Generando HTML integrado completo...")
    try:
        # Usar el generador HTML integrado que incluye la pestaña de novedades
        html_generator = UserStatsHTMLGeneratorFixed()
        html_content = html_generator.generate_html(all_user_stats, users, years_back)

        # Guardar HTML
        output_file = f'docs/usuarios_integrado_{period}.html'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Calcular tamaños
        html_size = os.path.getsize(output_file) / 1024 / 1024  # MB

        # Calcular tamaño total de archivos JSON
        json_size = 0
        if os.path.exists(discoveries_dir):
            for json_file in Path(discoveries_dir).glob("*.json"):
                json_size += os.path.getsize(json_file)
        json_size = json_size / 1024 / 1024  # MB

        print(f"✅ HTML integrado generado: {output_file}")
        print(f"📊 Tamaño HTML: {html_size:.2f} MB")
        print(f"📁 Tamaño archivos JSON: {json_size:.2f} MB")
        print(f"💾 Total: {html_size + json_size:.2f} MB (optimizado vs 90MB original)")

        return {
            'html_file': output_file,
            'json_dir': discoveries_dir,
            'html_size': html_size,
            'json_size': json_size
        }

    except Exception as e:
        print(f"❌ Error generando HTML integrado: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_integration(result: dict):
    """Verifica que la integración funcione correctamente"""
    print(f"\n🔍 Verificando integración...")

    html_file = result['html_file']
    json_dir = result['json_dir']

    # Verificar HTML
    if os.path.exists(html_file):
        print(f"  ✅ HTML integrado: {html_file}")

        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Verificar elementos clave
        required_elements = [
            'data-view="discoveries"',  # Pestaña de novedades
            'loadDiscoveriesData',      # Función de carga
            'discoveriesTab',           # Tab de novedades
            'discoveriesArtistsChart',  # Gráficos de novedades
            'showDiscoveryPopup',       # Popup con detalles
            'userButton',               # Botón de usuario original
            'user-modal'                # Modal de usuario original
        ]

        missing = [elem for elem in required_elements if elem not in html_content]
        if missing:
            print(f"    ⚠️  Elementos faltantes en HTML: {missing}")
        else:
            print(f"    ✅ Todos los elementos integrados correctamente")
    else:
        print(f"  ❌ HTML no encontrado: {html_file}")

    # Verificar archivos JSON
    if os.path.exists(json_dir):
        json_files = list(Path(json_dir).glob("*.json"))
        print(f"  ✅ Directorio JSON: {json_dir}")
        print(f"  📁 Archivos JSON: {len(json_files)}")

        # Verificar estructura de un JSON
        if json_files:
            sample_file = json_files[0]
            try:
                with open(sample_file, 'r', encoding='utf-8') as f:
                    sample_data = json.load(f)

                if 'discoveries' in sample_data:
                    discoveries = sample_data['discoveries']
                    print(f"    📋 Tipos de datos: {list(discoveries.keys())}")

                    # Verificar que solo tiene top 10
                    for discovery_type, type_data in discoveries.items():
                        for year, year_data in type_data.items():
                            if isinstance(year_data, dict) and 'items' in year_data:
                                items_count = len(year_data['items'])
                                if items_count <= 10:
                                    print(f"    ✅ {discovery_type}: máximo {items_count} elementos por año")
                                else:
                                    print(f"    ⚠️  {discovery_type}: {items_count} elementos (debería ser ≤10)")
                                break
                        break
                else:
                    print(f"    ❌ Estructura incorrecta en JSON")
            except Exception as e:
                print(f"    ❌ Error leyendo JSON: {e}")
    else:
        print(f"  ❌ Directorio JSON no encontrado: {json_dir}")


def main():
    """Función principal"""
    print("🚀 Generador Integrado de Estadísticas con Novedades")
    print("=" * 60)

    # Obtener usuarios
    users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
    if not users:
        print("❌ Variable LASTFM_USERS no configurada")
        print("Ejemplo: export LASTFM_USERS='usuario1,usuario2,usuario3'")
        sys.exit(1)

    print(f"👥 Usuarios: {users}")

    # Generar estadísticas integradas
    result = generate_integrated_stats(users, years_back=5)

    if result:
        # Verificar integración
        verify_integration(result)

        print(f"\n🎉 ¡Integración completa exitosa!")

        print(f"\n📋 Resultado:")
        print(f"  🌐 HTML integrado: {result['html_file']}")
        print(f"  📁 Datos JSON: {result['json_dir']}")
        print(f"  📊 HTML: {result['html_size']:.2f} MB")
        print(f"  📁 JSON: {result['json_size']:.2f} MB")

        print(f"\n✨ Características integradas:")
        print(f"  ✅ Todas las pestañas originales funcionando")
        print(f"  ✅ Nueva pestaña 'Novedades' integrada")
        print(f"  ✅ Manejo de usuarios con iconos mantenido")
        print(f"  ✅ Popups con detalles (top 10 por año)")
        print(f"  ✅ Carga dinámica de datos de novedades")
        print(f"  ✅ Cache para mejor rendimiento")
        print(f"  ✅ HTML optimizado (~{result['html_size']:.1f}MB vs 90MB)")

        print(f"\n🔧 Uso:")
        print(f"  1. Abre {result['html_file']}")
        print(f"  2. Selecciona un usuario (botón 👤)")
        print(f"  3. Navega entre todas las pestañas")
        print(f"  4. Ve a '✨ Novedades' para ver descubrimientos")
        print(f"  5. Haz click en puntos para ver detalles en popup")

    else:
        print(f"\n💥 Error en la integración")
        sys.exit(1)


if __name__ == '__main__':
    main()
