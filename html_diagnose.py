#!/usr/bin/env python3
"""
Script para extraer y analizar los datos JSON del HTML generado
Útil para diagnosticar por qué los gráficos no se muestran
"""

import re
import json
import sys

def extract_and_analyze_html_data(html_file):
    """Extrae y analiza los datos del HTML"""

    print("🔍 ANALIZANDO DATOS EN EL HTML")
    print("="*70)

    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"❌ No se encontró el archivo: {html_file}")
        return
    except Exception as e:
        print(f"❌ Error leyendo el archivo: {e}")
        return

    print(f"✅ Archivo leído: {html_file}")
    print(f"   Tamaño: {len(html_content):,} caracteres")

    # Extraer el objeto allStats
    print("\n📊 Extrayendo datos de JavaScript...")

    # Buscar: const allStats = {...};
    pattern = r'const allStats = (\{.*?\});'
    match = re.search(pattern, html_content, re.DOTALL)

    if not match:
        print("❌ No se encontró 'const allStats' en el HTML")
        print("\n💡 Posibles causas:")
        print("   1. El HTML no se generó correctamente")
        print("   2. La estructura del HTML cambió")
        print("   3. Hay un error en el generador de HTML")
        return

    print("✅ Datos encontrados")

    # Extraer y parsear el JSON
    json_str = match.group(1)

    try:
        stats_data = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"❌ Error parseando JSON: {e}")
        print(f"\n   Primeros 500 caracteres del JSON:")
        print(f"   {json_str[:500]}")
        return

    print("✅ JSON parseado correctamente")

    # Analizar la estructura
    print("\n" + "="*70)
    print("📋 ESTRUCTURA DE DATOS")
    print("="*70)

    users = list(stats_data.keys())
    print(f"\n👥 Usuarios: {len(users)}")
    for user in users:
        print(f"   • {user}")

    # Analizar cada usuario
    for user, user_data in stats_data.items():
        print(f"\n{'='*70}")
        print(f"📊 DATOS DE: {user}")
        print(f"{'='*70}")

        # Claves principales
        print("\n🔑 Claves principales:")
        for key in user_data.keys():
            print(f"   • {key}")

        # 1. Scrobbles
        if 'yearly_scrobbles' in user_data:
            yearly = user_data['yearly_scrobbles']
            total = sum(yearly.values())
            print(f"\n📈 Scrobbles:")
            print(f"   Total: {total:,}")
            for year, count in sorted(yearly.items()):
                print(f"   {year}: {count:,}")

        # 2. Géneros
        if 'genres' in user_data:
            genres_data = user_data['genres']
            print(f"\n🎵 Géneros:")

            for provider in ['lastfm', 'musicbrainz', 'discogs']:
                if provider in genres_data:
                    provider_data = genres_data[provider]
                    print(f"\n   📌 {provider.upper()}:")

                    # Pie chart
                    if 'pie_chart' in provider_data:
                        pie = provider_data['pie_chart']
                        print(f"      Pie Chart:")
                        print(f"         Total plays: {pie.get('total', 0):,}")
                        print(f"         Géneros: {len(pie.get('data', {}))}")

                        # Mostrar top 3
                        if pie.get('data'):
                            top_3 = sorted(pie['data'].items(), key=lambda x: x[1], reverse=True)[:3]
                            for genre, plays in top_3:
                                print(f"            • {genre}: {plays:,}")
                    else:
                        print(f"      ❌ No hay pie_chart")

                    # Scatter charts
                    if 'scatter_charts' in provider_data:
                        scatter = provider_data['scatter_charts']
                        print(f"      Scatter Charts: {len(scatter)} géneros")
                        for genre in list(scatter.keys())[:3]:
                            artists = scatter[genre]
                            print(f"         • {genre}: {len(artists)} artistas")
                    else:
                        print(f"      ❌ No hay scatter_charts")

                    # Album pie chart
                    if 'album_pie_chart' in provider_data:
                        album_pie = provider_data['album_pie_chart']
                        print(f"      Album Pie Chart:")
                        print(f"         Total: {album_pie.get('total', 0):,}")
                        print(f"         Géneros: {len(album_pie.get('data', {}))}")

                    # Album scatter charts
                    if 'album_scatter_charts' in provider_data:
                        album_scatter = provider_data['album_scatter_charts']
                        print(f"      Album Scatter: {len(album_scatter)} géneros")
                else:
                    print(f"\n   ❌ {provider.upper()}: No hay datos")
        else:
            print(f"\n❌ No hay datos de géneros")

        # 3. Sellos
        if 'labels' in user_data:
            labels_data = user_data['labels']
            print(f"\n🏷️  Sellos:")

            if 'pie_chart' in labels_data:
                pie = labels_data['pie_chart']
                print(f"   Pie Chart:")
                print(f"      Total: {pie.get('total', 0):,}")
                print(f"      Sellos: {len(pie.get('data', {}))}")

                if pie.get('data'):
                    top_3 = sorted(pie['data'].items(), key=lambda x: x[1], reverse=True)[:3]
                    for label, plays in top_3:
                        print(f"         • {label}: {plays:,}")
            else:
                print(f"   ❌ No hay pie_chart")

            if 'scatter_charts' in labels_data:
                scatter = labels_data['scatter_charts']
                print(f"   Scatter Charts: {len(scatter)} sellos")
            else:
                print(f"   ❌ No hay scatter_charts")
        else:
            print(f"\n❌ No hay datos de sellos")

        # 4. Coincidencias
        if 'coincidences' in user_data:
            coin = user_data['coincidences']
            print(f"\n🤝 Coincidencias:")
            for key in ['artists', 'albums', 'tracks']:
                if key in coin:
                    data = coin[key]
                    if 'bar_chart' in data:
                        total = sum(data['bar_chart'].values())
                        print(f"   {key.capitalize()}: {total} coincidencias")

        # 5. Evolución
        if 'evolution' in user_data:
            evo = user_data['evolution']
            print(f"\n📈 Evolución:")
            for key in ['genres', 'labels', 'release_years', 'coincidences']:
                if key in evo:
                    print(f"   ✅ {key}")
                else:
                    print(f"   ❌ {key}")

    # Verificar Chart.js
    print(f"\n{'='*70}")
    print("🔧 VERIFICANDO DEPENDENCIAS")
    print(f"{'='*70}")

    if 'cdn.jsdelivr.net/npm/chart.js' in html_content:
        print("✅ Chart.js está incluido en el HTML")
    else:
        print("❌ Chart.js NO está incluido en el HTML")
        print("   → Los gráficos no pueden funcionar sin esta librería")

    # Verificar funciones de renderizado
    render_functions = [
        'renderGenresPieChart',
        'renderGenresScatterChart',
        'renderLabelsPieChart',
        'renderLabelsScatterChart'
    ]

    print(f"\n🔧 Funciones de renderizado:")
    for func in render_functions:
        if func in html_content:
            print(f"   ✅ {func}")
        else:
            print(f"   ❌ {func} - FALTA")

    # Resumen final
    print(f"\n{'='*70}")
    print("📋 RESUMEN")
    print(f"{'='*70}")

    has_genres = False
    has_labels = False

    for user, user_data in stats_data.items():
        if 'genres' in user_data and any(user_data['genres'].get(p) for p in ['lastfm', 'musicbrainz', 'discogs']):
            has_genres = True
        if 'labels' in user_data and user_data['labels']:
            has_labels = True

    if has_genres:
        print("✅ Hay datos de géneros en el JSON")
    else:
        print("❌ NO hay datos de géneros en el JSON")
        print("   → Los gráficos de géneros no pueden mostrarse")
        print("   → Ejecuta diagnose_interactive.py para encontrar el problema")

    if has_labels:
        print("✅ Hay datos de sellos en el JSON")
    else:
        print("⚠️  NO hay datos de sellos en el JSON")
        print("   → Los gráficos de sellos no se mostrarán")

    print(f"\n💡 SIGUIENTE PASO:")
    if has_genres or has_labels:
        print("   Los datos están en el HTML. Si los gráficos no aparecen:")
        print("   1. Abre el HTML en tu navegador")
        print("   2. Presiona F12 para abrir la consola de desarrollador")
        print("   3. Busca errores en rojo")
        print("   4. Reporta esos errores para que pueda corregirlos")
    else:
        print("   El problema está en la generación de datos.")
        print("   Ejecuta: python3 diagnose_interactive.py")

    # Guardar JSON extraído
    output_file = html_file.replace('.html', '_extracted_data.json')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, indent=2, ensure_ascii=False)
        print(f"\n📁 Datos extraídos guardados en: {output_file}")
    except Exception as e:
        print(f"\n⚠️  No se pudieron guardar los datos: {e}")

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 extract_html_data.py <archivo.html>")
        print("\nEjemplo:")
        print("   python3 extract_html_data.py docs/usuarios_2020-2025.html")
        sys.exit(1)

    html_file = sys.argv[1]
    extract_and_analyze_html_data(html_file)

if __name__ == '__main__':
    main()
