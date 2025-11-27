#!/usr/bin/env python3
"""
Script de depuración para el problema de los gráficos de novedades
Analiza el HTML generado y los datos JSON para encontrar el problema
"""

import os
import re
import json
import sys
from pathlib import Path

def analyze_html_discoveries_integration(html_file_path):
    """Analiza la integración de novedades en el HTML"""
    print("🔍 Analizando integración de novedades en HTML...")

    if not os.path.exists(html_file_path):
        print(f"❌ Archivo HTML no encontrado: {html_file_path}")
        return False

    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Verificar elementos clave
    checks = {
        "Pestaña de novedades": 'data-view="discoveries"',
        "Tab de contenido": 'id="discoveriesTab"',
        "Función de carga": 'loadDiscoveriesData',
        "Función de renderizado": 'renderDiscoveriesCharts',
        "Canvas de artistas": 'discoveriesArtistsChart',
        "Canvas de álbumes": 'discoveriesAlbumsChart',
        "Canvas de canciones": 'discoveriesTracksChart',
        "Canvas de sellos": 'discoveriesLabelsChart',
        "Función de popup": 'showDiscoveryPopup',
        "Manejo de errores": 'showDiscoveriesError',
        "Variables globales": 'discoveriesData = {}',
        "Configuración de años": 'yearsBackConfig'
    }

    results = {}
    for check_name, pattern in checks.items():
        found = pattern in html_content
        results[check_name] = found
        status = "✅" if found else "❌"
        print(f"  {status} {check_name}: {found}")

    # Buscar posibles errores en el JavaScript
    print("\n🔧 Analizando JavaScript de novedades...")

    # Verificar si setupNavigation maneja discoveries correctamente
    setup_pattern = r'if \(view === [\'"]discoveries[\'\"]\)'
    setup_found = bool(re.search(setup_pattern, html_content))
    print(f"  {'✅' if setup_found else '❌'} setupNavigation maneja discoveries: {setup_found}")

    # Verificar estructura de la pestaña
    tab_structure_pattern = r'<div[^>]*id=[\'"]discoveriesTab[\'"][^>]*class=[\'"]tab-content[\'"][^>]*>'
    tab_structure_found = bool(re.search(tab_structure_pattern, html_content))
    print(f"  {'✅' if tab_structure_found else '❌'} Estructura correcta del tab: {tab_structure_found}")

    # Buscar errores comunes
    print("\n🐛 Buscando errores comunes...")

    # Canvas duplicados
    canvas_ids = ['discoveriesArtistsChart', 'discoveriesAlbumsChart', 'discoveriesTracksChart', 'discoveriesLabelsChart']
    for canvas_id in canvas_ids:
        pattern = f'id=[\'\"]{canvas_id}[\'\"]\s'
        matches = len(re.findall(pattern, html_content))
        if matches > 1:
            print(f"  ⚠️ Canvas duplicado detectado: {canvas_id} ({matches} veces)")
        elif matches == 0:
            print(f"  ❌ Canvas faltante: {canvas_id}")
        else:
            print(f"  ✅ Canvas correcto: {canvas_id}")

    # Verificar sintaxis JavaScript básica
    js_errors = []

    # Buscar funciones mal cerradas
    function_pattern = r'function\s+\w+\s*\([^)]*\)\s*\{'
    functions = re.findall(function_pattern, html_content)

    # Buscar llaves desbalanceadas en funciones de discoveries
    discoveries_js_start = html_content.find('async function loadDiscoveriesData')
    discoveries_js_end = html_content.find('</script>', discoveries_js_start)

    if discoveries_js_start != -1 and discoveries_js_end != -1:
        discoveries_js = html_content[discoveries_js_start:discoveries_js_end]
        open_braces = discoveries_js.count('{')
        close_braces = discoveries_js.count('}')

        if open_braces != close_braces:
            js_errors.append(f"Llaves desbalanceadas en JS de discoveries: {open_braces} {{ vs {close_braces} }}")
            print(f"  ❌ Llaves desbalanceadas: {open_braces} abre vs {close_braces} cierra")
        else:
            print(f"  ✅ Llaves balanceadas en JS de discoveries")

    return all(results.values()) and len(js_errors) == 0

def analyze_json_data_structure(data_dir):
    """Analiza la estructura de los archivos JSON de novedades"""
    print(f"\n📄 Analizando archivos JSON en {data_dir}...")

    if not os.path.exists(data_dir):
        print(f"❌ Directorio de datos no encontrado: {data_dir}")
        return False

    json_files = list(Path(data_dir).glob("*.json"))
    if not json_files:
        print(f"❌ No se encontraron archivos JSON en {data_dir}")
        return False

    print(f"📁 Encontrados {len(json_files)} archivos JSON")

    # Analizar estructura de un archivo de ejemplo
    sample_file = json_files[0]
    print(f"\n🔍 Analizando estructura de: {sample_file.name}")

    try:
        with open(sample_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Verificar estructura esperada
        required_keys = ['user', 'period', 'discoveries', 'totals', 'yearly_totals']
        for key in required_keys:
            if key in data:
                print(f"  ✅ {key}: presente")
            else:
                print(f"  ❌ {key}: faltante")

        # Verificar estructura de discoveries
        if 'discoveries' in data:
            discoveries = data['discoveries']
            discovery_types = ['artists', 'albums', 'tracks', 'labels']

            print(f"\n  📊 Análisis de discoveries:")
            for dtype in discovery_types:
                if dtype in discoveries:
                    type_data = discoveries[dtype]
                    years_with_data = []
                    total_items = 0

                    for year, year_data in type_data.items():
                        if isinstance(year_data, dict) and 'count' in year_data:
                            count = year_data['count']
                            if count > 0:
                                years_with_data.append(year)
                                total_items += count

                    print(f"    ✅ {dtype}: {len(years_with_data)} años con datos, {total_items} elementos totales")

                    # Verificar estructura de items
                    if years_with_data:
                        sample_year = years_with_data[0]
                        sample_year_data = type_data[sample_year]
                        if 'items' in sample_year_data and sample_year_data['items']:
                            sample_item = sample_year_data['items'][0]
                            expected_item_keys = ['name', 'timestamp', 'date']
                            item_structure_ok = all(key in sample_item for key in expected_item_keys)
                            print(f"      {'✅' if item_structure_ok else '❌'} Estructura de items: {list(sample_item.keys())}")
                        else:
                            print(f"      ⚠️ No hay items de ejemplo en {dtype} para {sample_year}")
                else:
                    print(f"    ❌ {dtype}: faltante")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def generate_test_html():
    """Genera un HTML de prueba mínimo para testear los gráficos de novedades"""
    print("\n🧪 Generando HTML de prueba para novedades...")

    test_html = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Test Novedades</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        .canvas-container { width: 400px; height: 300px; margin: 20px; }
        canvas { border: 1px solid #ccc; }
        .error { color: red; }
        .success { color: green; }
    </style>
</head>
<body>
    <h1>Test de Gráficos de Novedades</h1>

    <div id="status">Cargando...</div>

    <div class="canvas-container">
        <h3>Nuevos Artistas</h3>
        <canvas id="testArtistsChart"></canvas>
    </div>

    <div class="canvas-container">
        <h3>Nuevos Álbumes</h3>
        <canvas id="testAlbumsChart"></canvas>
    </div>

    <script>
        console.log('🚀 Iniciando test de novedades...');

        // Datos de prueba
        const testData = {
            user: "test_user",
            period: "2020-2025",
            discoveries: {
                artists: {
                    "2023": { count: 15, items: [{name: "Artista Test", date: "2023-03-15"}] },
                    "2024": { count: 20, items: [{name: "Artista Test 2", date: "2024-05-20"}] }
                },
                albums: {
                    "2023": { count: 25, items: [{name: "Album Test", date: "2023-07-10"}] },
                    "2024": { count: 30, items: [{name: "Album Test 2", date: "2024-09-15"}] }
                }
            }
        };

        let charts = {};

        function renderTestChart(canvasId, typeData, title) {
            console.log(`📊 Renderizando ${canvasId} con datos:`, typeData);

            const canvas = document.getElementById(canvasId);
            if (!canvas) {
                console.error(`❌ Canvas ${canvasId} no encontrado`);
                return;
            }

            const years = [];
            const counts = [];

            Object.keys(typeData).sort().forEach(year => {
                const yearInt = parseInt(year);
                if (!isNaN(yearInt) && typeData[year]) {
                    years.push(yearInt);
                    counts.push(typeData[year].count || 0);
                }
            });

            if (years.length === 0 || counts.every(c => c === 0)) {
                console.log(`⚠️ Sin datos válidos para ${canvasId}`);
                canvas.parentElement.innerHTML += '<p class="error">Sin datos</p>';
                return;
            }

            console.log(`📈 Años: ${years}, Conteos: ${counts}`);

            const config = {
                type: 'line',
                data: {
                    labels: years,
                    datasets: [{
                        label: title,
                        data: counts,
                        borderColor: '#cba6f7',
                        backgroundColor: '#cba6f730',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            };

            try {
                if (charts[canvasId]) {
                    charts[canvasId].destroy();
                }
                charts[canvasId] = new Chart(canvas, config);
                console.log(`✅ Gráfico ${canvasId} creado exitosamente`);
                return true;
            } catch (error) {
                console.error(`❌ Error creando gráfico ${canvasId}:`, error);
                canvas.parentElement.innerHTML += `<p class="error">Error: ${error.message}</p>`;
                return false;
            }
        }

        // Test principal
        function runTest() {
            console.log('🔧 Ejecutando test de renderizado...');

            const statusDiv = document.getElementById('status');

            try {
                const results = [];

                // Test artistas
                const artistsResult = renderTestChart('testArtistsChart', testData.discoveries.artists, 'Nuevos Artistas');
                results.push({type: 'artists', success: artistsResult});

                // Test álbumes
                const albumsResult = renderTestChart('testAlbumsChart', testData.discoveries.albums, 'Nuevos Álbumes');
                results.push({type: 'albums', success: albumsResult});

                // Mostrar resultados
                const successful = results.filter(r => r.success).length;
                const total = results.length;

                if (successful === total) {
                    statusDiv.innerHTML = `<span class="success">✅ Test exitoso: ${successful}/${total} gráficos funcionan</span>`;
                } else {
                    statusDiv.innerHTML = `<span class="error">⚠️ Test parcial: ${successful}/${total} gráficos funcionan</span>`;
                }

                console.log('📊 Resultados del test:', results);

            } catch (error) {
                console.error('❌ Error en test principal:', error);
                statusDiv.innerHTML = `<span class="error">❌ Error en test: ${error.message}</span>`;
            }
        }

        // Ejecutar cuando esté listo
        document.addEventListener('DOMContentLoaded', runTest);
    </script>
</body>
</html>'''

    test_file = 'test_discoveries.html'
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_html)

    print(f"✅ HTML de prueba generado: {test_file}")
    return test_file

def diagnose_discoveries_problem(html_file_path, json_data_dir):
    """Función principal de diagnóstico"""
    print("🔍 DIAGNÓSTICO DE NOVEDADES - INICIANDO ANÁLISIS")
    print("=" * 60)

    issues_found = []

    # 1. Analizar HTML
    html_ok = analyze_html_discoveries_integration(html_file_path)
    if not html_ok:
        issues_found.append("Problemas en integración HTML")

    # 2. Analizar JSON
    json_ok = analyze_json_data_structure(json_data_dir)
    if not json_ok:
        issues_found.append("Problemas en estructura de datos JSON")

    # 3. Generar test
    test_file = generate_test_html()

    # 4. Reporte final
    print(f"\n📋 REPORTE DE DIAGNÓSTICO")
    print("=" * 30)

    if not issues_found:
        print("✅ No se detectaron problemas obvios")
        print("💡 Sugerencias para debug adicional:")
        print("  1. Abre las herramientas de desarrollo del navegador (F12)")
        print("  2. Ve a la pestaña 'Console' para ver errores JavaScript")
        print("  3. Ve a la pestaña 'Network' para verificar que los JSON se cargan")
        print(f"  4. Prueba el archivo de test: {test_file}")
    else:
        print("❌ Problemas detectados:")
        for issue in issues_found:
            print(f"  • {issue}")

    print(f"\n🧪 Archivo de test generado: {test_file}")
    print("📄 Abre este archivo en tu navegador para hacer un test básico")

    return len(issues_found) == 0

def main():
    """Función principal"""
    print("🔧 Script de Depuración para Gráficos de Novedades")
    print("=" * 50)

    # Configuración predeterminada (ajustar según tu estructura)
    html_file = "docs/usuarios_2024-2025.html"  # Ajustar nombre
    json_dir = "docs/data/usuarios/2020-2025"  # Ajustar directorio

    # Permitir argumentos de línea de comandos
    if len(sys.argv) >= 2:
        html_file = sys.argv[1]
    if len(sys.argv) >= 3:
        json_dir = sys.argv[2]

    print(f"📄 Archivo HTML: {html_file}")
    print(f"📁 Directorio JSON: {json_dir}")

    # Ejecutar diagnóstico
    success = diagnose_discoveries_problem(html_file, json_dir)

    if success:
        print("\n🎉 Diagnóstico completado sin problemas mayores")
    else:
        print("\n⚠️ Se encontraron problemas que requieren atención")

    print("\n💡 Pasos siguientes:")
    print("1. Revisa los problemas detectados arriba")
    print("2. Abre el HTML en tu navegador con herramientas de desarrollo (F12)")
    print("3. Verifica la consola JavaScript por errores")
    print("4. Verifica la pestaña Network por fallos de carga de JSON")
    print("5. Usa el archivo de test para confirmar que Chart.js funciona")

if __name__ == '__main__':
    main()
