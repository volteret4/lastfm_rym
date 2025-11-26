#!/usr/bin/env python3
"""
Diagnóstico específico para datos de novedades vacíos
Verifica la estructura de los archivos JSON y el flujo de datos
"""

import json
import os
import sys

def check_json_structure(json_path):
    """Verifica la estructura del archivo JSON de novedades"""
    print(f"🔍 Analizando: {json_path}")

    if not os.path.exists(json_path):
        print(f"❌ Archivo no encontrado: {json_path}")
        return False

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"✅ JSON válido, tamaño: {os.path.getsize(json_path)} bytes")

        # Verificar estructura principal
        required_keys = ['user', 'period', 'discoveries', 'totals', 'yearly_totals']
        for key in required_keys:
            if key in data:
                print(f"✅ {key}: presente")
            else:
                print(f"❌ {key}: faltante")

        # Verificar discoveries
        if 'discoveries' in data:
            discovery_types = ['artists', 'albums', 'tracks', 'labels']
            for dtype in discovery_types:
                if dtype in data['discoveries']:
                    type_data = data['discoveries'][dtype]
                    if isinstance(type_data, dict):
                        years = list(type_data.keys())
                        print(f"✅ {dtype}: {len(years)} años - {years}")

                        # Verificar estructura de años
                        for year in years[:2]:  # Solo los primeros 2 años
                            year_data = type_data[year]
                            if isinstance(year_data, dict):
                                count = year_data.get('count', 0)
                                items = year_data.get('items', [])
                                has_more = year_data.get('has_more', False)
                                print(f"    {year}: count={count}, items={len(items)}, has_more={has_more}")

                                # Mostrar algunos items de ejemplo
                                if items and len(items) > 0:
                                    print(f"      Ejemplos: {[item.get('name', 'N/A')[:30] for item in items[:3]]}")
                            else:
                                print(f"    {year}: estructura incorrecta - {type(year_data)}")
                    else:
                        print(f"❌ {dtype}: estructura incorrecta - {type(type_data)}")
                else:
                    print(f"❌ {dtype}: faltante")

        # Verificar totales
        if 'totals' in data:
            print(f"📊 Totales: {data['totals']}")

        if 'yearly_totals' in data:
            print(f"📊 Totales por año: {data['yearly_totals']}")

        return True

    except json.JSONDecodeError as e:
        print(f"❌ Error de JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def create_debug_html():
    """Crea una página HTML simple para probar la carga de JSON"""
    html_content = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Novedades</title>
    <style>
        body { font-family: monospace; background: #1e1e2e; color: #cdd6f4; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .test-section { background: #181825; padding: 20px; margin: 20px 0; border-radius: 8px; }
        button { background: #cba6f7; color: #1e1e2e; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }
        button:hover { background: #b4a3e8; }
        #output { background: #313244; padding: 15px; border-radius: 6px; white-space: pre-wrap; max-height: 400px; overflow-y: auto; }
        .error { color: #f38ba8; }
        .success { color: #a6e3a1; }
        .info { color: #89dceb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Test de Carga de Novedades</h1>

        <div class="test-section">
            <h3>Test 1: Verificar Usuario</h3>
            <input type="text" id="username" placeholder="nombre_usuario" value="paqueradejere" style="padding: 8px; border-radius: 4px; border: none; margin-right: 10px;">
            <button onclick="testUser()">Probar Usuario</button>
        </div>

        <div class="test-section">
            <h3>Test 2: Cargar JSON Directo</h3>
            <input type="text" id="jsonPath" placeholder="data/usuarios/2024-2025/usuario.json" value="data/usuarios/2024-2025/paqueradejere.json" style="width: 300px; padding: 8px; border-radius: 4px; border: none; margin-right: 10px;">
            <button onclick="testDirectLoad()">Cargar JSON</button>
        </div>

        <div class="test-section">
            <h3>Test 3: Verificar Estructura</h3>
            <button onclick="analyzeStructure()">Analizar Estructura</button>
        </div>

        <div class="test-section">
            <h3>Resultados</h3>
            <div id="output"></div>
        </div>
    </div>

    <script>
        let loadedData = null;

        function log(message, type = 'info') {
            const output = document.getElementById('output');
            const timestamp = new Date().toLocaleTimeString();
            const className = type === 'error' ? 'error' : type === 'success' ? 'success' : 'info';
            output.innerHTML += `<span class="${className}">[${timestamp}] ${message}</span>\\n`;
            output.scrollTop = output.scrollHeight;
        }

        async function testUser() {
            const username = document.getElementById('username').value;
            log(`🧪 Probando usuario: ${username}`);

            const currentYear = new Date().getFullYear();
            const fromYear = currentYear - 1; // Ajustar según tu configuración
            const period = `${fromYear}-${currentYear}`;
            const dataUrl = `data/usuarios/${period}/${username}.json`;

            try {
                log(`📡 Cargando desde: ${dataUrl}`);

                const response = await fetch(dataUrl);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const userData = await response.json();
                loadedData = userData;

                log(`✅ Datos cargados exitosamente`, 'success');
                log(`📊 Usuario: ${userData.user}`);
                log(`📊 Período: ${userData.period}`);
                log(`📊 Claves principales: ${Object.keys(userData).join(', ')}`);

                if (userData.discoveries) {
                    const types = Object.keys(userData.discoveries);
                    log(`🎵 Tipos de descubrimientos: ${types.join(', ')}`);

                    types.forEach(type => {
                        const typeData = userData.discoveries[type];
                        const years = Object.keys(typeData);
                        const totalItems = years.reduce((sum, year) => sum + (typeData[year]?.count || 0), 0);
                        log(`  ${type}: ${years.length} años, ${totalItems} items total`);
                    });
                } else {
                    log(`❌ No hay datos de discoveries`, 'error');
                }

            } catch (error) {
                log(`❌ Error: ${error.message}`, 'error');
                console.error('Error completo:', error);
            }
        }

        async function testDirectLoad() {
            const jsonPath = document.getElementById('jsonPath').value;
            log(`🔗 Carga directa: ${jsonPath}`);

            try {
                const response = await fetch(jsonPath);

                log(`📡 Status: ${response.status} ${response.statusText}`);
                log(`📡 Headers: ${JSON.stringify(Object.fromEntries(response.headers.entries()))}`);

                if (!response.ok) {
                    const text = await response.text();
                    log(`❌ Respuesta: ${text.substring(0, 200)}...`, 'error');
                    return;
                }

                const data = await response.json();
                loadedData = data;

                log(`✅ JSON parseado correctamente`, 'success');
                log(`📋 Estructura: ${JSON.stringify(data, null, 2).substring(0, 500)}...`);

            } catch (error) {
                log(`❌ Error: ${error.message}`, 'error');
            }
        }

        function analyzeStructure() {
            if (!loadedData) {
                log(`❌ No hay datos cargados. Ejecuta primero un test de carga.`, 'error');
                return;
            }

            log(`🔬 Analizando estructura de datos...`);

            // Verificar discoveries
            if (loadedData.discoveries) {
                Object.keys(loadedData.discoveries).forEach(type => {
                    const typeData = loadedData.discoveries[type];
                    log(`\\n📋 Análisis de ${type}:`);
                    log(`  Tipo: ${typeof typeData}`);
                    log(`  Es objeto: ${typeof typeData === 'object' && !Array.isArray(typeData)}`);

                    if (typeof typeData === 'object') {
                        const years = Object.keys(typeData);
                        log(`  Años encontrados: ${years.join(', ')}`);

                        years.forEach(year => {
                            const yearData = typeData[year];
                            log(`    ${year}:`);
                            log(`      Tipo: ${typeof yearData}`);
                            log(`      Claves: ${Object.keys(yearData || {}).join(', ')}`);
                            log(`      Count: ${yearData?.count || 'N/A'}`);
                            log(`      Items: ${yearData?.items?.length || 'N/A'}`);

                            if (yearData?.items && yearData.items.length > 0) {
                                const sample = yearData.items[0];
                                log(`      Ejemplo item: ${JSON.stringify(sample)}`);
                            }
                        });
                    }
                });
            } else {
                log(`❌ No se encontró el objeto 'discoveries'`, 'error');
            }

            // Test simulado de renderización
            log(`\\n🎨 Simulando renderización...`);
            simulateRender();
        }

        function simulateRender() {
            if (!loadedData || !loadedData.discoveries) {
                log(`❌ No hay datos para renderizar`, 'error');
                return;
            }

            const discoveryTypes = [
                {type: 'artists', title: 'Nuevos Artistas'},
                {type: 'albums', title: 'Nuevos Álbumes'},
                {type: 'tracks', title: 'Nuevas Canciones'},
                {type: 'labels', title: 'Nuevos Sellos'}
            ];

            discoveryTypes.forEach(config => {
                const typeData = loadedData.discoveries[config.type];
                log(`\\n🎯 Renderizando ${config.type}:`);

                if (typeData && Object.keys(typeData).length > 0) {
                    const years = [];
                    const counts = [];

                    Object.keys(typeData).sort((a, b) => parseInt(a) - parseInt(b)).forEach(year => {
                        const yearInt = parseInt(year);
                        if (!isNaN(yearInt) && typeData[year]) {
                            years.push(yearInt);
                            counts.push(typeData[year].count || 0);
                        }
                    });

                    if (years.length > 0) {
                        log(`  ✅ Datos válidos: años ${years.join(', ')}, conteos ${counts.join(', ')}`, 'success');
                        log(`  📊 Total a renderizar: ${counts.reduce((a, b) => a + b, 0)} items`);
                    } else {
                        log(`  ❌ No se encontraron años válidos`, 'error');
                    }
                } else {
                    log(`  ❌ Sin datos de tipo`, 'error');
                }
            });
        }

        // Auto-test al cargar
        window.addEventListener('load', () => {
            log(`🚀 Test de novedades iniciado`);
            log(`🔗 URL actual: ${window.location.href}`);
            log(`📁 Base URL: ${window.location.origin}${window.location.pathname.replace(/[^/]*$/, '')}`);
        });
    </script>
</body>
</html>'''

    with open('test_novedades.html', 'w', encoding='utf-8') as f:
        f.write(html_content)

    print("📄 Página de test creada: test_novedades.html")

def analyze_github_structure(base_path):
    """Analiza la estructura de archivos en el proyecto"""
    print(f"\n📁 Analizando estructura en: {base_path}")

    # Buscar archivos HTML
    html_files = []
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.endswith('.html') and 'usuarios_' in file:
                html_files.append(os.path.join(root, file))

    print(f"📄 Archivos HTML encontrados: {len(html_files)}")
    for html_file in html_files:
        print(f"  - {html_file}")

    # Buscar directorio de datos
    data_dirs = []
    for root, dirs, files in os.walk(base_path):
        if 'data' in dirs or 'usuarios' in ' '.join(dirs):
            data_path = os.path.join(root, 'data')
            if os.path.exists(data_path):
                data_dirs.append(data_path)

    print(f"\n📁 Directorios de datos encontrados: {len(data_dirs)}")
    for data_dir in data_dirs:
        print(f"  - {data_dir}")

        # Analizar contenido del directorio de datos
        if os.path.exists(data_dir):
            usuarios_path = os.path.join(data_dir, 'usuarios')
            if os.path.exists(usuarios_path):
                print(f"    📁 {usuarios_path}")

                for period_dir in os.listdir(usuarios_path):
                    period_path = os.path.join(usuarios_path, period_dir)
                    if os.path.isdir(period_path):
                        json_files = [f for f in os.listdir(period_path) if f.endswith('.json')]
                        print(f"      📁 {period_dir}: {len(json_files)} archivos JSON")

                        # Analizar algunos archivos JSON
                        for json_file in json_files[:3]:
                            json_path = os.path.join(period_path, json_file)
                            print(f"        🔍 Analizando {json_file}...")
                            check_json_structure(json_path)

def main():
    print("🔍 DIAGNÓSTICO DE NOVEDADES VACÍAS")
    print("=" * 50)

    # Si se proporciona una ruta, analizarla
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if path.endswith('.json'):
            # Analizar archivo JSON específico
            check_json_structure(path)
        elif os.path.isdir(path):
            # Analizar directorio del proyecto
            analyze_github_structure(path)
        else:
            print(f"❌ Ruta no válida: {path}")
    else:
        # Modo interactivo
        print("📋 OPCIONES:")
        print("1. Analizar archivo JSON específico")
        print("2. Analizar directorio del proyecto")
        print("3. Crear página de test")

        choice = input("\nSelecciona una opción (1-3): ").strip()

        if choice == '1':
            json_path = input("Ruta del archivo JSON: ").strip()
            check_json_structure(json_path)
        elif choice == '2':
            project_path = input("Ruta del proyecto: ").strip()
            analyze_github_structure(project_path)
        elif choice == '3':
            create_debug_html()
        else:
            print("❌ Opción no válida")

    # Siempre crear la página de test
    create_debug_html()

    print("\n🎯 PRÓXIMOS PASOS:")
    print("1. Abre test_novedades.html en el navegador")
    print("2. Ejecuta los tests para verificar la carga de datos")
    print("3. Revisa los logs en la consola del navegador")
    print("4. Comparte los resultados del test")

if __name__ == '__main__':
    main()
