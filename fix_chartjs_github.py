#!/usr/bin/env python3
"""
Script para reemplazar Chart.js con una versión que funciona correctamente en GitHub Pages
Soluciona el problema de gráficos que no se muestran por CDN inestable
"""

import re
import sys
import os

def fix_chartjs_for_github_pages(html_path):
    """Reemplaza Chart.js con versión estable que funciona en GitHub Pages"""
    print(f"🔧 Corrigiendo Chart.js en: {html_path}")
    
    if not os.path.exists(html_path):
        print(f"❌ Archivo no encontrado: {html_path}")
        return False
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Backup
    backup_path = html_path.replace('.html', '_before_chartjs_fix.html')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"📦 Backup creado: {backup_path}")
    
    changes_made = False
    
    # 1. REEMPLAZAR Chart.js CDN con versión específica que funciona
    old_chartjs_patterns = [
        r'<script src="https://cdn\.jsdelivr\.net/npm/chart\.js"></script>',
        r'<script src="https://cdn\.jsdelivr\.net/npm/chart\.js@\d+\.\d+\.\d+/dist/chart\.min\.js"></script>',
        r'<script src="https://cdnjs\.cloudflare\.com/ajax/libs/Chart\.js/[^"]+"></script>'
    ]
    
    # Versión estable que funciona bien en GitHub Pages
    new_chartjs = '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js" integrity="sha512-ElRFoEQdI5Ht6kZvyzXhYG9NqjtkmlkfYk0wr6wHxU9JEHakS7UJZNeml5ALk+8IKlU6jDgMabC3vkumRokgJA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>'
    
    for pattern in old_chartjs_patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, new_chartjs, content)
            print("✅ Chart.js CDN reemplazado con versión estable")
            changes_made = True
            break
    
    # 2. AÑADIR verificación de Chart.js y fallback
    chartjs_verification = '''
        // 🔧 Verificación y carga de Chart.js con fallback
        function verifyChartJs() {
            console.log('🔍 Verificando Chart.js...');
            console.log('Chart disponible:', typeof Chart);
            
            if (typeof Chart === 'undefined') {
                console.log('❌ Chart.js no cargado, intentando fallback...');
                loadChartJsFallback();
                return false;
            } else {
                console.log('✅ Chart.js cargado correctamente, versión:', Chart.version);
                return true;
            }
        }
        
        function loadChartJsFallback() {
            const fallbackUrls = [
                'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js',
                'https://unpkg.com/chart.js@3.9.1/dist/chart.min.js',
                'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js'
            ];
            
            let currentIndex = 0;
            
            function tryNext() {
                if (currentIndex >= fallbackUrls.length) {
                    console.error('❌ No se pudo cargar Chart.js desde ningún CDN');
                    showChartJsError();
                    return;
                }
                
                const script = document.createElement('script');
                script.src = fallbackUrls[currentIndex];
                
                script.onload = function() {
                    console.log('✅ Chart.js cargado desde fallback:', fallbackUrls[currentIndex]);
                    // Reintentar renderización si ya se intentó
                    if (currentUser && currentView === 'discoveries') {
                        setTimeout(() => loadDiscoveriesData(currentUser), 500);
                    }
                };
                
                script.onerror = function() {
                    console.log('❌ Fallback fallido:', fallbackUrls[currentIndex]);
                    currentIndex++;
                    tryNext();
                };
                
                document.head.appendChild(script);
            }
            
            tryNext();
        }
        
        function showChartJsError() {
            const gridElement = document.getElementById('discoveriesGrid');
            if (gridElement) {
                gridElement.innerHTML = `<div class="no-data" style="grid-column: 1/-1; text-align: center; padding: 40px;">
                    <h4 style="color: #f38ba8; margin-bottom: 15px;">📊 Error de Gráficos</h4>
                    <p style="color: #cdd6f4; margin-bottom: 10px;">Chart.js no se pudo cargar.</p>
                    <p style="font-size: 0.9em; color: #a6adc8;">Esto puede suceder por problemas de CDN en GitHub Pages.</p>
                    <button onclick="location.reload()" style="margin-top: 15px; padding: 8px 16px; background: #cba6f7; color: #1e1e2e; border: none; border-radius: 6px; cursor: pointer;">🔄 Recargar Página</button>
                </div>`;
                gridElement.style.display = 'grid';
            }
        }
'''
    
    # 3. MODIFICAR la función renderDiscoveryChart para verificar Chart.js
    chart_creation_pattern = r'(try \{\s*console\.log\(`Creando nuevo gráfico \$\{canvasId\}`\);\s*const ctx = canvas\.getContext\(\'2d\'\);\s*charts\[canvasId\] = new Chart\(ctx,)'
    
    chart_creation_replacement = r'''try {
                console.log(`Creando nuevo gráfico ${canvasId}`);
                
                // Verificar que Chart.js está disponible
                if (typeof Chart === 'undefined') {
                    console.error(`❌ Chart.js no disponible para ${canvasId}`);
                    showNoDataForChart(canvasId);
                    return;
                }
                
                const ctx = canvas.getContext('2d');
                if (!ctx) {
                    console.error(`❌ No se pudo obtener contexto 2D para ${canvasId}`);
                    showNoDataForChart(canvasId);
                    return;
                }
                
                console.log(`📊 Creando Chart para ${canvasId}...`);
                charts[canvasId] = new Chart(ctx,'''
    
    if re.search(chart_creation_pattern, content):
        content = re.sub(chart_creation_pattern, chart_creation_replacement, content, flags=re.DOTALL)
        print("✅ Verificación de Chart.js añadida a renderización")
        changes_made = True
    
    # 4. AÑADIR event listener para verificar Chart.js al cargar
    initialization_code = '''
        // 🚀 Inicialización mejorada con verificación de Chart.js
        document.addEventListener('DOMContentLoaded', function() {
            console.log('📄 DOM cargado, verificando dependencias...');
            
            // Verificar Chart.js después de un breve delay
            setTimeout(verifyChartJs, 500);
            
            // Verificación adicional después de más tiempo
            setTimeout(() => {
                if (typeof Chart === 'undefined') {
                    console.log('⚠️ Chart.js sigue sin cargar después de 2s');
                    loadChartJsFallback();
                }
            }, 2000);
        });
        
        // También verificar cuando se cambie a la pestaña de novedades
        function switchToDiscoveries() {
            if (typeof Chart === 'undefined') {
                console.log('⚠️ Intentando cargar novedades sin Chart.js');
                if (!verifyChartJs()) {
                    setTimeout(() => {
                        if (currentUser) {
                            loadDiscoveriesData(currentUser);
                        }
                    }, 1000);
                    return;
                }
            }
        }
'''
    
    # Insertar el código de verificación antes del cierre del script
    if '</script>' in content and 'verifyChartJs' not in content:
        content = content.replace('</script>', chartjs_verification + initialization_code + '\n        </script>')
        print("✅ Sistema de verificación de Chart.js añadido")
        changes_made = True
    
    # 5. MODIFICAR setupNavigation para usar la verificación
    navigation_pattern = r'(if \(view === \'discoveries\'\) \{\s*loadDiscoveriesData\(currentUser\);\s*\})'
    
    navigation_replacement = '''if (view === 'discoveries') {
                            switchToDiscoveries();
                            if (typeof Chart !== 'undefined') {
                                loadDiscoveriesData(currentUser);
                            } else {
                                console.log('⏳ Esperando a que Chart.js se cargue...');
                            }
                        }'''
    
    if re.search(navigation_pattern, content):
        content = re.sub(navigation_pattern, navigation_replacement, content)
        print("✅ Navegación mejorada con verificación de Chart.js")
        changes_made = True
    
    # Guardar cambios
    if changes_made:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Correcciones de Chart.js aplicadas a: {html_path}")
        
        print("\n📋 CAMBIOS APLICADOS:")
        print("  ✅ CDN de Chart.js reemplazado con versión estable")
        print("  ✅ Sistema de fallback para CDN añadido")
        print("  ✅ Verificación de Chart.js antes de crear gráficos")
        print("  ✅ Manejo de errores mejorado")
        print("  ✅ Reintentos automáticos")
        
        print(f"\n🎯 PRÓXIMOS PASOS:")
        print(f"1. Sube el archivo corregido a GitHub")
        print(f"2. Espera unos minutos para que se actualice GitHub Pages")
        print(f"3. Abre la página y ve a '✨ Novedades'")
        print(f"4. Abre la consola y verifica los mensajes de Chart.js")
        print(f"5. Los gráficos deberían aparecer ahora")
        
    else:
        print("ℹ️  No se necesitaron correcciones de Chart.js")
    
    return changes_made

def create_simple_test_page():
    """Crea una página de test simple para verificar Chart.js"""
    test_html = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Chart.js GitHub Pages</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js" integrity="sha512-ElRFoEQdI5Ht6kZvyzXhYG9NqjtkmlkfYk0wr6wHxU9JEHakS7UJZNeml5ALk+8IKlU6jDgMabC3vkumRokgJA==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    <style>
        body { font-family: monospace; background: #1e1e2e; color: #cdd6f4; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .chart-container { background: #181825; padding: 20px; margin: 20px 0; border-radius: 8px; height: 400px; }
        button { background: #cba6f7; color: #1e1e2e; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin: 10px; }
        #log { background: #313244; padding: 15px; border-radius: 6px; white-space: pre-wrap; max-height: 200px; overflow-y: auto; font-size: 12px; }
        .success { color: #a6e3a1; }
        .error { color: #f38ba8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Test Chart.js para GitHub Pages</h1>
        
        <div>
            <button onclick="testChartJs()">Probar Chart.js</button>
            <button onclick="createTestChart()">Crear Gráfico de Test</button>
            <button onclick="clearLog()">Limpiar Log</button>
        </div>
        
        <div id="log"></div>
        
        <div class="chart-container">
            <canvas id="testChart"></canvas>
        </div>
    </div>

    <script>
        function log(message, type = 'info') {
            const logElement = document.getElementById('log');
            const timestamp = new Date().toLocaleTimeString();
            const className = type === 'error' ? 'error' : type === 'success' ? 'success' : '';
            logElement.innerHTML += `<span class="${className}">[${timestamp}] ${message}</span>\\n`;
            logElement.scrollTop = logElement.scrollHeight;
        }
        
        function clearLog() {
            document.getElementById('log').innerHTML = '';
        }
        
        function testChartJs() {
            log('🔍 Testing Chart.js...');
            log(`Chart disponible: ${typeof Chart !== 'undefined'}`);
            
            if (typeof Chart !== 'undefined') {
                log(`✅ Chart.js version: ${Chart.version || 'desconocida'}`, 'success');
                log(`Chart.register: ${typeof Chart.register === 'function'}`);
                log(`Chart constructors: ${Object.keys(Chart).join(', ')}`);
            } else {
                log('❌ Chart.js no está disponible', 'error');
                log('📡 URL actual: ' + window.location.href);
                log('📡 Protocolo: ' + window.location.protocol);
            }
        }
        
        let testChartInstance = null;
        
        function createTestChart() {
            log('🎨 Creando gráfico de test...');
            
            if (typeof Chart === 'undefined') {
                log('❌ Chart.js no disponible', 'error');
                return;
            }
            
            const canvas = document.getElementById('testChart');
            if (!canvas) {
                log('❌ Canvas no encontrado', 'error');
                return;
            }
            
            // Destruir gráfico anterior si existe
            if (testChartInstance) {
                testChartInstance.destroy();
                log('🗑️ Gráfico anterior destruido');
            }
            
            try {
                const ctx = canvas.getContext('2d');
                
                testChartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [2024, 2025],
                        datasets: [{
                            label: 'Test Data',
                            data: [625, 223],
                            borderColor: '#cba6f7',
                            backgroundColor: 'rgba(203, 166, 247, 0.3)',
                            tension: 0.4,
                            fill: true,
                            pointRadius: 8
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: '#cdd6f4' } }
                        },
                        scales: {
                            x: { ticks: { color: '#a6adc8' }, grid: { color: '#313244' } },
                            y: { ticks: { color: '#a6adc8' }, grid: { color: '#313244' }, beginAtZero: true }
                        }
                    }
                });
                
                log('✅ Gráfico de test creado exitosamente', 'success');
                
            } catch (error) {
                log(`❌ Error creando gráfico: ${error.message}`, 'error');
                log(`Stack: ${error.stack}`);
            }
        }
        
        // Auto-test al cargar
        window.addEventListener('load', () => {
            setTimeout(() => {
                log('🚀 Página cargada, iniciando test automático...');
                testChartJs();
            }, 500);
        });
    </script>
</body>
</html>'''
    
    test_path = '/mnt/user-data/outputs/test_chartjs_github.html'
    with open(test_path, 'w', encoding='utf-8') as f:
        f.write(test_html)
    
    print(f"📄 Página de test creada: {test_path}")
    print(f"🔗 Sube este archivo a GitHub para probar Chart.js")

def main():
    print("🔧 CORRECTOR DE CHART.JS PARA GITHUB PAGES")
    print("=" * 50)
    
    if len(sys.argv) != 2:
        print("Uso: python fix_chartjs_github.py <archivo_html>")
        print("Ejemplo: python fix_chartjs_github.py docs/usuarios_2024-2025.html")
        sys.exit(1)
    
    html_path = sys.argv[1]
    
    # Aplicar correcciones
    success = fix_chartjs_for_github_pages(html_path)
    
    # Crear página de test
    create_simple_test_page()
    
    print(f"\n🎉 ¡LISTO!")
    print(f"📤 Sube {html_path} a GitHub")
    print(f"📤 También puedes subir test_chartjs_github.html para probar")
    print(f"⏰ Espera 2-3 minutos para que GitHub Pages se actualice")
    print(f"🔍 Los gráficos de novedades deberían funcionar ahora")

if __name__ == '__main__':
    main()
