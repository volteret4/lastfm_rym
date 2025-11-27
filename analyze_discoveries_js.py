#!/usr/bin/env python3
"""
Analizador específico de JavaScript de novedades
Examina el código JavaScript en el HTML para encontrar problemas específicos
"""

import os
import re
import sys
import json
from typing import Dict, List, Tuple

def extract_javascript_from_html(html_file_path: str) -> str:
    """Extrae todo el JavaScript del archivo HTML"""
    if not os.path.exists(html_file_path):
        print(f"❌ Archivo no encontrado: {html_file_path}")
        return ""

    with open(html_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extraer todo el contenido entre <script> tags
    script_pattern = r'<script[^>]*>(.*?)</script>'
    scripts = re.findall(script_pattern, content, re.DOTALL)

    # Unir todos los scripts
    full_js = '\n'.join(scripts)
    return full_js

def analyze_discoveries_functions(js_content: str) -> Dict[str, bool]:
    """Analiza las funciones específicas de novedades"""
    print("🔍 Analizando funciones de novedades...")

    functions_to_check = {
        'loadDiscoveriesData': r'async\s+function\s+loadDiscoveriesData\s*\(',
        'renderDiscoveriesCharts': r'function\s+renderDiscoveriesCharts\s*\(',
        'renderDiscoveryChart': r'function\s+renderDiscoveryChart\s*\(',
        'showDiscoveryPopup': r'function\s+showDiscoveryPopup\s*\(',
        'showDiscoveriesError': r'function\s+showDiscoveriesError\s*\(',
        'showNoDataForChart': r'function\s+showNoDataForChart\s*\('
    }

    results = {}
    for func_name, pattern in functions_to_check.items():
        found = bool(re.search(pattern, js_content))
        results[func_name] = found
        status = "✅" if found else "❌"
        print(f"  {status} {func_name}: {found}")

    return results

def analyze_setupNavigation_discoveries(js_content: str) -> bool:
    """Analiza si setupNavigation maneja correctamente el view 'discoveries'"""
    print("\n🔧 Analizando setupNavigation para discoveries...")

    # Buscar la función setupNavigation
    setup_pattern = r'function\s+setupNavigation\s*\(\)\s*\{(.*?)\}'
    setup_match = re.search(setup_pattern, js_content, re.DOTALL)

    if not setup_match:
        print("  ❌ Función setupNavigation no encontrada")
        return False

    setup_content = setup_match.group(1)

    # Verificar que maneja el view 'discoveries'
    discoveries_check_patterns = [
        r'view\s*===\s*[\'"]discoveries[\'"]',
        r'if\s*\(\s*view\s*===\s*[\'"]discoveries[\'"]',
        r'loadDiscoveriesData\s*\(',
    ]

    discoveries_handled = any(
        re.search(pattern, setup_content)
        for pattern in discoveries_check_patterns
    )

    if discoveries_handled:
        print("  ✅ setupNavigation maneja discoveries correctamente")

        # Verificar la lógica específica
        load_call_pattern = r'loadDiscoveriesData\s*\(\s*currentUser\s*\)'
        load_call_found = bool(re.search(load_call_pattern, setup_content))

        if load_call_found:
            print("  ✅ Llama a loadDiscoveriesData con currentUser")
        else:
            print("  ⚠️ No se encontró la llamada correcta a loadDiscoveriesData")
            return False
    else:
        print("  ❌ setupNavigation NO maneja discoveries")
        return False

    return True

def analyze_canvas_setup(js_content: str) -> Dict[str, bool]:
    """Analiza la configuración de los canvas de novedades"""
    print("\n🎨 Analizando configuración de canvas...")

    canvas_ids = [
        'discoveriesArtistsChart',
        'discoveriesAlbumsChart',
        'discoveriesTracksChart',
        'discoveriesLabelsChart'
    ]

    results = {}
    for canvas_id in canvas_ids:
        # Buscar referencias al canvas
        patterns = [
            f'getElementById\([\'\"]{canvas_id}[\'\"]\)',
            f'charts\[[\'\"]{canvas_id}[\'\"]\]',
            f'new Chart\s*\([^,]*{canvas_id}'
        ]

        found = any(re.search(pattern, js_content) for pattern in patterns)
        results[canvas_id] = found

        status = "✅" if found else "❌"
        print(f"  {status} {canvas_id}: {found}")

    return results

def analyze_data_loading_logic(js_content: str) -> Dict[str, bool]:
    """Analiza la lógica de carga de datos"""
    print("\n📡 Analizando lógica de carga de datos...")

    checks = {
        'fetch_call': r'fetch\s*\(\s*dataUrl\s*\)',
        'response_json': r'response\.json\s*\(\s*\)',
        'cache_check': r'discoveriesData\s*\[\s*username\s*\]',
        'error_handling': r'catch\s*\(\s*error\s*\)',
        'period_calculation': r'fromYear\s*-\s*currentYear',
        'url_construction': r'data/usuarios/.*\.json'
    }

    results = {}
    for check_name, pattern in checks.items():
        found = bool(re.search(pattern, js_content))
        results[check_name] = found

        status = "✅" if found else "❌"
        print(f"  {status} {check_name}: {found}")

    return results

def analyze_chart_rendering_logic(js_content: str) -> Dict[str, bool]:
    """Analiza la lógica de renderizado de gráficos"""
    print("\n📊 Analizando lógica de renderizado...")

    checks = {
        'chart_destruction': r'charts\[.*\]\.destroy\s*\(\s*\)',
        'chart_creation': r'new Chart\s*\(',
        'data_processing': r'userData\.discoveries',
        'chart_config': r'type:\s*[\'"]line[\'"]',
        'responsive_config': r'responsive:\s*true',
        'click_handler': r'onClick:\s*function'
    }

    results = {}
    for check_name, pattern in checks.items():
        found = bool(re.search(pattern, js_content))
        results[check_name] = found

        status = "✅" if found else "❌"
        print(f"  {status} {check_name}: {found}")

    return results

def find_potential_javascript_errors(js_content: str) -> List[str]:
    """Busca errores potenciales en el JavaScript"""
    print("\n🐛 Buscando errores potenciales...")

    errors = []

    # 1. Variables no definidas
    undefined_vars = [
        'discoveriesData',
        'yearsBackConfig',
        'currentUser',
        'charts'
    ]

    for var in undefined_vars:
        # Buscar uso sin declaración
        usage_pattern = f'{var}\\['
        declaration_patterns = [
            f'let\\s+{var}',
            f'const\\s+{var}',
            f'var\\s+{var}',
            f'{var}\\s*='
        ]

        used = bool(re.search(usage_pattern, js_content))
        declared = any(re.search(pattern, js_content) for pattern in declaration_patterns)

        if used and not declared:
            errors.append(f"Variable '{var}' usada pero no declarada")

    # 2. Llaves desbalanceadas en funciones específicas
    discovery_functions = [
        'loadDiscoveriesData',
        'renderDiscoveriesCharts',
        'renderDiscoveryChart'
    ]

    for func_name in discovery_functions:
        func_pattern = f'function\\s+{func_name}\\s*\\([^\\)]*\\)\\s*\\{{(.*?)\\n\\s*\\}}'
        func_match = re.search(func_pattern, js_content, re.DOTALL)

        if func_match:
            func_body = func_match.group(1)
            open_braces = func_body.count('{')
            close_braces = func_body.count('}')

            if open_braces != close_braces:
                errors.append(f"Llaves desbalanceadas en función '{func_name}': {open_braces} abre vs {close_braces} cierra")

    # 3. Sintaxis de async/await
    async_pattern = r'await\s+(?!.*async)'
    invalid_awaits = re.findall(async_pattern, js_content)
    if invalid_awaits:
        errors.append(f"Posible uso incorrecto de 'await' sin función 'async'")

    # 4. Referencias a elementos DOM que podrían no existir
    dom_refs = [
        'discoveriesLoading',
        'discoveriesGrid',
        'discoveriesArtistsChart',
        'discoveriesAlbumsChart',
        'discoveriesTracksChart',
        'discoveriesLabelsChart'
    ]

    for dom_id in dom_refs:
        getElementById_pattern = f'getElementById\\([\'\"]{dom_id}[\'\"]\)'
        if re.search(getElementById_pattern, js_content):
            # Verificar si hay verificación de null
            null_check_pattern = f'if\\s*\\(.*{dom_id}.*\\)'
            if not re.search(null_check_pattern, js_content):
                errors.append(f"getElementById('{dom_id}') sin verificación de null")

    for error in errors:
        print(f"  ⚠️ {error}")

    if not errors:
        print("  ✅ No se detectaron errores obvios")

    return errors

def extract_discoveries_javascript_block(js_content: str) -> str:
    """Extrae específicamente el bloque de JavaScript de novedades"""
    # Buscar el comentario que indica el inicio del bloque de discoveries
    start_pattern = r'//.*[Ff]unciones para manejo de novedades'
    start_match = re.search(start_pattern, js_content)

    if not start_match:
        # Buscar por función loadDiscoveriesData
        start_pattern = r'async function loadDiscoveriesData'
        start_match = re.search(start_pattern, js_content)

    if start_match:
        start_pos = start_match.start()
        # Buscar el final (puede ser cierre de script o próxima función principal)
        end_patterns = [
            r'\n\s*</script>',
            r'\n\s*function\s+(?!.*discoveries|.*popup|.*error)',
            r'\n\s*}\s*$'
        ]

        end_pos = len(js_content)
        for pattern in end_patterns:
            end_match = re.search(pattern, js_content[start_pos:])
            if end_match:
                end_pos = start_pos + end_match.start()
                break

        discoveries_block = js_content[start_pos:end_pos]
        return discoveries_block

    return ""

def create_fixed_javascript_block():
    """Crea un bloque de JavaScript de novedades corregido"""
    fixed_js = '''
        // ✅ Funciones para manejo de novedades - VERSIÓN CORREGIDA
        async function loadDiscoveriesData(username) {
            console.log(`🔄 Cargando datos de novedades para ${username}...`);

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            // Verificar elementos DOM
            if (!loadingElement || !gridElement) {
                console.error('❌ Elementos DOM de novedades no encontrados');
                return;
            }

            loadingElement.style.display = 'block';
            gridElement.style.display = 'none';

            try {
                // Verificar cache
                if (discoveriesData && discoveriesData[username]) {
                    console.log('📦 Usando datos del cache');
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }

                // Calcular URL
                const currentYear = new Date().getFullYear();
                const fromYear = currentYear - (yearsBackConfig || 5);
                const period = `${fromYear}-${currentYear}`;
                const dataUrl = `data/usuarios/${period}/${username}.json`;

                console.log(`🌐 Cargando desde: ${dataUrl}`);

                // Cargar datos
                const response = await fetch(dataUrl);
                if (!response.ok) {
                    throw new Error(`Error HTTP: ${response.status} - ${dataUrl}`);
                }

                const userData = await response.json();
                console.log('✅ Datos cargados:', userData);

                // Verificar estructura de datos
                if (!userData.discoveries) {
                    throw new Error('Estructura de datos incorrecta: falta discoveries');
                }

                // Guardar en cache
                if (!discoveriesData) {
                    window.discoveriesData = {};
                }
                window.discoveriesData[username] = userData;

                renderDiscoveriesCharts(userData);

            } catch (error) {
                console.error('❌ Error cargando novedades:', error);
                showDiscoveriesError(error.message);
            }
        }

        function renderDiscoveriesCharts(userData) {
            console.log('📊 Renderizando gráficos de novedades...');

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'none';
            if (gridElement) gridElement.style.display = 'grid';

            if (!userData || !userData.discoveries) {
                console.error('❌ Datos de userData inválidos');
                showDiscoveriesError('Datos de novedades inválidos');
                return;
            }

            const discoveryTypes = [
                {type: 'artists', canvasId: 'discoveriesArtistsChart', title: 'Nuevos Artistas'},
                {type: 'albums', canvasId: 'discoveriesAlbumsChart', title: 'Nuevos Álbumes'},
                {type: 'tracks', canvasId: 'discoveriesTracksChart', title: 'Nuevas Canciones'},
                {type: 'labels', canvasId: 'discoveriesLabelsChart', title: 'Nuevos Sellos'}
            ];

            discoveryTypes.forEach(config => {
                try {
                    const typeData = userData.discoveries[config.type];
                    if (typeData && Object.keys(typeData).length > 0) {
                        console.log(`📈 Renderizando ${config.type}:`, typeData);
                        renderDiscoveryChart(config.canvasId, typeData, config.title);
                    } else {
                        console.log(`⚠️ Sin datos para ${config.type}`);
                        showNoDataForChart(config.canvasId);
                    }
                } catch (error) {
                    console.error(`❌ Error renderizando ${config.type}:`, error);
                    showNoDataForChart(config.canvasId);
                }
            });
        }

        function renderDiscoveryChart(canvasId, typeData, title) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) {
                console.error(`❌ Canvas ${canvasId} no encontrado`);
                return;
            }

            console.log(`📊 Renderizando gráfico ${canvasId} con datos:`, typeData);

            const years = [];
            const counts = [];
            const details = {};

            // Procesar datos por año
            Object.keys(typeData).sort((a, b) => parseInt(a) - parseInt(b)).forEach(year => {
                const yearInt = parseInt(year);
                if (!isNaN(yearInt) && typeData[year]) {
                    years.push(yearInt);
                    counts.push(typeData[year].count || 0);
                    details[yearInt] = typeData[year].items || [];
                }
            });

            if (years.length === 0 || counts.every(c => c === 0)) {
                console.log(`⚠️ Sin datos válidos para ${canvasId}`);
                showNoDataForChart(canvasId);
                return;
            }

            console.log(`📊 Años: ${years}, Conteos: ${counts}`);

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
                        fill: true,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#cba6f7',
                        pointBorderColor: '#1e1e2e',
                        pointBorderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {color: '#cdd6f4', padding: 15}
                        },
                        tooltip: {
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1
                        }
                    },
                    scales: {
                        x: {
                            title: {display: true, text: 'Año', color: '#cdd6f4'},
                            ticks: {color: '#a6adc8'},
                            grid: {color: '#313244'}
                        },
                        y: {
                            title: {display: true, text: 'Novedades', color: '#cdd6f4'},
                            ticks: {color: '#a6adc8', precision: 0},
                            grid: {color: '#313244'},
                            beginAtZero: true
                        }
                    },
                    onClick: function(event, elements) {
                        if (elements.length > 0) {
                            const pointIndex = elements[0].index;
                            const year = this.data.labels[pointIndex];
                            const count = this.data.datasets[0].data[pointIndex];

                            console.log(`👆 Click en año ${year}, count: ${count}`);

                            if (count > 0 && details[year] && details[year].length > 0) {
                                showDiscoveryPopup(year, details[year], title, count);
                            }
                        }
                    }
                }
            };

            // Destruir gráfico existente si existe
            if (window.charts && window.charts[canvasId]) {
                console.log(`🗑️ Destruyendo gráfico existente ${canvasId}`);
                window.charts[canvasId].destroy();
                delete window.charts[canvasId];
            }

            // Crear gráfico
            console.log(`🆕 Creando nuevo gráfico ${canvasId}`);
            try {
                if (!window.charts) {
                    window.charts = {};
                }
                window.charts[canvasId] = new Chart(canvas, config);
                console.log(`✅ Gráfico ${canvasId} creado exitosamente`);
            } catch (error) {
                console.error(`❌ Error creando gráfico ${canvasId}:`, error);
                showNoDataForChart(canvasId);
            }
        }

        function showDiscoveriesError(errorMessage) {
            console.error('❌ Error en novedades:', errorMessage);

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'none';

            if (gridElement) {
                gridElement.innerHTML = `<div class="no-data" style="grid-column: 1/-1; text-align: center; padding: 40px;">
                    <h4 style="color: #f38ba8; margin-bottom: 15px;">❌ Error cargando novedades</h4>
                    <p style="color: #cdd6f4; margin-bottom: 10px;">No se pudieron cargar los datos de descubrimientos.</p>
                    <p style="font-size: 0.9em; color: #a6adc8; margin-bottom: 10px;">${errorMessage}</p>
                    <p style="font-size: 0.8em; color: #6c7086;">
                        Verifica que los archivos JSON estén disponibles y la estructura sea correcta.
                    </p>
                </div>`;
                gridElement.style.display = 'grid';
            }
        }

        function showNoDataForChart(canvasId) {
            const canvas = document.getElementById(canvasId);
            if (canvas) {
                canvas.style.display = 'none';
                const wrapper = canvas.parentElement;
                if (wrapper) {
                    wrapper.innerHTML = '<div class="no-data" style="height: 200px; display: flex; align-items: center; justify-content: center; color: #a6adc8; font-style: italic;">Sin datos de descubrimientos</div>';
                }
            }
        }

        function showDiscoveryPopup(year, items, title, count) {
            console.log(`📝 Mostrando popup para ${title} - ${year}:`, items);

            const popupTitle = `${title} - ${year} (${count} nuevos)`;
            let content = '';

            items.slice(0, 10).forEach(item => {
                content += `<div class="popup-item">
                    <span class="name">${item.name}</span>
                    <span class="count">${item.date}</span>
                </div>`;
            });

            if (count > items.length) {
                content += `<div style="text-align: center; padding: 10px; color: #a6adc8; font-style: italic;">
                    ... y ${count - items.length} más
                </div>`;
            }

            const popupTitleElement = document.getElementById('popupTitle');
            const popupContentElement = document.getElementById('popupContent');
            const popupOverlayElement = document.getElementById('popupOverlay');
            const popupElement = document.getElementById('popup');

            if (popupTitleElement) popupTitleElement.textContent = popupTitle;
            if (popupContentElement) popupContentElement.innerHTML = content;
            if (popupOverlayElement) popupOverlayElement.style.display = 'block';
            if (popupElement) popupElement.style.display = 'block';
        }
    '''
    return fixed_js

def main():
    """Función principal"""
    print("🔧 Analizador de JavaScript de Novedades")
    print("=" * 50)

    # Configuración
    html_file = "docs/usuarios_2024-2025.html"
    if len(sys.argv) >= 2:
        html_file = sys.argv[1]

    print(f"📄 Analizando archivo: {html_file}")

    # Extraer JavaScript
    js_content = extract_javascript_from_html(html_file)
    if not js_content:
        print("❌ No se pudo extraer JavaScript del archivo")
        return

    print(f"📝 JavaScript extraído: {len(js_content)} caracteres")

    # Análisis detallado
    functions_ok = analyze_discoveries_functions(js_content)
    setup_ok = analyze_setupNavigation_discoveries(js_content)
    canvas_ok = analyze_canvas_setup(js_content)
    loading_ok = analyze_data_loading_logic(js_content)
    rendering_ok = analyze_chart_rendering_logic(js_content)
    errors = find_potential_javascript_errors(js_content)

    # Extraer bloque específico de discoveries
    discoveries_block = extract_discoveries_javascript_block(js_content)
    if discoveries_block:
        print(f"\n📦 Bloque de novedades extraído: {len(discoveries_block)} caracteres")

        # Guardar el bloque extraído para inspección
        extracted_file = 'extracted_discoveries.js'
        with open(extracted_file, 'w', encoding='utf-8') as f:
            f.write(discoveries_block)
        print(f"💾 Bloque guardado en: {extracted_file}")

    # Crear versión corregida
    fixed_js = create_fixed_javascript_block()
    fixed_file = 'fixed_discoveries.js'
    with open(fixed_file, 'w', encoding='utf-8') as f:
        f.write(fixed_js)

    # Resumen final
    print(f"\n📊 RESUMEN DEL ANÁLISIS")
    print("=" * 30)

    all_functions_found = all(functions_ok.values())
    all_canvas_found = all(canvas_ok.values())
    all_loading_found = all(loading_ok.values())
    all_rendering_found = all(rendering_ok.values())

    issues = []
    if not all_functions_found:
        missing_funcs = [f for f, found in functions_ok.items() if not found]
        issues.append(f"Funciones faltantes: {missing_funcs}")

    if not setup_ok:
        issues.append("setupNavigation no maneja discoveries correctamente")

    if not all_canvas_found:
        missing_canvas = [c for c, found in canvas_ok.items() if not found]
        issues.append(f"Canvas faltantes: {missing_canvas}")

    if not all_loading_found:
        missing_loading = [l for l, found in loading_ok.items() if not found]
        issues.append(f"Lógica de carga incompleta: {missing_loading}")

    if not all_rendering_found:
        missing_rendering = [r for r, found in rendering_ok.items() if not found]
        issues.append(f"Lógica de renderizado incompleta: {missing_rendering}")

    if errors:
        issues.extend(errors)

    if not issues:
        print("✅ Análisis completo sin problemas detectados")
        print("💡 Si los gráficos aún no funcionan, verifica:")
        print("  • Consola del navegador por errores JavaScript")
        print("  • Pestaña Network por fallos de carga de JSON")
        print("  • Estructura de los archivos JSON")
    else:
        print("⚠️ Problemas detectados:")
        for issue in issues:
            print(f"  • {issue}")

    print(f"\n📁 Archivos generados:")
    print(f"  • {fixed_file} - Versión corregida del JavaScript")
    if discoveries_block:
        print(f"  • {extracted_file} - Bloque original extraído")

    print(f"\n💡 Para solucionar:")
    print("1. Revisa los problemas listados arriba")
    print("2. Compara el código original con la versión corregida")
    print("3. Reemplaza el JavaScript de novedades con la versión corregida")
    print("4. Verifica que las variables globales estén inicializadas")

if __name__ == '__main__':
    main()
