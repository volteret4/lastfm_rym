#!/usr/bin/env python3
"""
Script principal optimizado para generar estadísticas de usuarios con novedades
Genera archivos JSON separados para novedades y HTML ligero que carga datos dinámicamente
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

# Agregar directorio del proyecto al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from tools.users.user_stats_discoveries import DiscoveriesDataGenerator
    from tools.users.user_stats_html_generator_optimized import UserStatsHTMLGeneratorOptimized


    from tools.users.user_stats_analyzer import UserStatsAnalyzer
    from tools.users.user_stats_database_extended import UserStatsDatabaseExtended
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    print("Asegúrate de que todos los archivos estén disponibles")
    sys.exit(1)


def generate_optimized_stats(users: list, years_back: int = 5):
    """Genera estadísticas optimizadas con archivos JSON separados"""

    current_year = datetime.now().year
    from_year = current_year - years_back
    to_year = current_year
    period = f"{from_year}-{to_year}"

    print(f"🎵 Generando estadísticas optimizadas para {len(users)} usuarios")
    print(f"📅 Periodo: {period}")

    # Paso 1: Generar archivos JSON de novedades
    print("\n📊 Paso 1: Generando archivos JSON de novedades...")
    discoveries_generator = DiscoveriesDataGenerator()
    discoveries_dir = discoveries_generator.generate_all_users_data(users, years_back)
    discoveries_generator.close()

    if not discoveries_dir:
        print("❌ Error generando archivos JSON de novedades")
        return False

    # Paso 2: Generar estadísticas básicas (sin novedades)
    print("\n📈 Paso 2: Generando estadísticas básicas...")
    try:
        database = UserStatsDatabaseExtended()
        analyzer = UserStatsAnalyzer(database, years_back=years_back)

        all_user_stats = {}
        for user in users:
            print(f"  • Analizando {user}...")

            # Generar estadísticas básicas (el analizador incluye novedades automáticamente)
            user_stats = analyzer.analyze_user(user, users)

            # Remover datos de novedades para optimizar el JSON principal
            if 'individual' in user_stats and 'discoveries' in user_stats['individual']:
                del user_stats['individual']['discoveries']
                print(f"    ✂️  Datos de novedades removidos (se cargan desde JSON)")

            all_user_stats[user] = user_stats

        database.close()

    except Exception as e:
        print(f"❌ Error generando estadísticas básicas: {e}")
        return False

    # Paso 3: Generar HTML optimizado
    print("\n🎨 Paso 3: Generando HTML optimizado...")
    try:
        html_generator = UserStatsHTMLGeneratorOptimized()
        html_content = html_generator.generate_html(all_user_stats, users, years_back)

        # Guardar HTML
        output_file = f'docs/usuarios_optimizado_{period}.html'
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Calcular tamaños de archivo
        html_size = os.path.getsize(output_file) / 1024 / 1024  # MB

        # Calcular tamaño total de archivos JSON
        json_size = 0
        if os.path.exists(discoveries_dir):
            for json_file in Path(discoveries_dir).glob("*.json"):
                json_size += os.path.getsize(json_file)
        json_size = json_size / 1024 / 1024  # MB

        print(f"✅ HTML generado: {output_file}")
        print(f"📊 Tamaño HTML: {html_size:.2f} MB")
        print(f"📁 Tamaño archivos JSON: {json_size:.2f} MB")
        print(f"💡 Total: {html_size + json_size:.2f} MB (vs ~90MB anterior)")

        return output_file

    except Exception as e:
        print(f"❌ Error generando HTML: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_structure(output_file: str, discoveries_dir: str):
    """Verifica la estructura de archivos generados"""
    print(f"\n🔍 Verificando estructura de archivos...")

    # Verificar HTML
    if os.path.exists(output_file):
        print(f"  ✅ HTML: {output_file}")

        # Verificar contenido del HTML
        with open(output_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        required_elements = [
            'discoveriesTab',
            'loadDiscoveriesData',
            'renderDiscoveriesCharts',
            'data/usuarios/'
        ]

        missing = [elem for elem in required_elements if elem not in html_content]
        if missing:
            print(f"    ⚠️  Elementos faltantes en HTML: {missing}")
        else:
            print(f"    ✅ Todos los elementos de novedades presentes")
    else:
        print(f"  ❌ HTML no encontrado: {output_file}")

    # Verificar archivos JSON
    if os.path.exists(discoveries_dir):
        json_files = list(Path(discoveries_dir).glob("*.json"))
        print(f"  ✅ Directorio JSON: {discoveries_dir}")
        print(f"  📁 Archivos JSON: {len(json_files)}")

        for json_file in json_files:
            size = os.path.getsize(json_file) / 1024  # KB
            print(f"    • {json_file.name}: {size:.1f} KB")
    else:
        print(f"  ❌ Directorio JSON no encontrado: {discoveries_dir}")


def main():
    """Función principal"""
    print("🚀 Generador Optimizado de Estadísticas con Novedades")
    print("=" * 60)

    # Obtener usuarios
    users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
    if not users:
        print("❌ Variable LASTFM_USERS no configurada")
        print("Ejemplo: export LASTFM_USERS='usuario1,usuario2,usuario3'")
        sys.exit(1)

    print(f"👥 Usuarios: {users}")

    # Generar estadísticas optimizadas
    result = generate_optimized_stats(users, years_back=5)

    if result:
        # Verificar estructura
        current_year = datetime.now().year
        period = f"{current_year - 5}-{current_year}"
        discoveries_dir = f"docs/data/usuarios/{period}"

        verify_structure(result, discoveries_dir)

        print(f"\n🎉 ¡Generación completa!")
        print(f"\n📋 Archivos generados:")
        print(f"  🌐 HTML principal: {result}")
        print(f"  📁 Datos JSON: {discoveries_dir}")

        print(f"\n💡 Ventajas de esta arquitectura:")
        print(f"  ✅ HTML mucho más pequeño (~2-5MB vs ~90MB)")
        print(f"  ✅ Carga rápida inicial")
        print(f"  ✅ Datos de novedades se cargan solo cuando se necesitan")
        print(f"  ✅ Archivos JSON reutilizables")
        print(f"  ✅ Escalable para muchos usuarios")

        print(f"\n🔧 Uso:")
        print(f"  1. Abre {result}")
        print(f"  2. Selecciona un usuario")
        print(f"  3. Ve a la pestaña '✨ Novedades'")
        print(f"  4. Los datos se cargan dinámicamente")

    else:
        print(f"\n💥 Error en la generación")
        sys.exit(1)


if __name__ == '__main__':
    main()
