#!/usr/bin/env python3
"""
Script para ARREGLAR un HTML existente y agregarle funcionalidad de novedades
Uso: python fix_html_discoveries.py archivo.html
"""

import sys
import os
import re
from pathlib import Path

def fix_html_for_discoveries(html_content: str) -> str:
    """Arregla el HTML para usar el nuevo sistema de novedades integrado"""

    print("🔧 Arreglando HTML para usar el nuevo sistema de novedades...")

    # 1. Reemplazar la función loadDiscoveriesData que carga JSONs externos
    old_load_function = r'async function loadDiscoveriesData\(username\) \{.*?\}\s*\}'
    new_load_function = '''function loadDiscoveriesData(username) {
            console.log(`✨ Cargando datos de novedades integrados para ${username}...`);

            const userStats = allStats[username];
            if (userStats && userStats.discoveries) {
                console.log('📊 Usando datos integrados de novedades');
                renderDiscoveriesChartsNew(userStats);
            } else {
                console.error('❌ No hay datos de novedades integrados para', username);
                console.log('📋 Datos disponibles:', Object.keys(userStats || {}));
                showDiscoveriesErrorNew('No hay datos de novedades disponibles. Este usuario necesita ser reprocesado con el nuevo sistema.');
            }
        }'''

    html_content = re.sub(old_load_function, new_load_function, html_content, flags=re.DOTALL)
    print("  ✅ Función loadDiscoveriesData actualizada")

    # 2. Agregar las funciones nuevas si no existen
    if 'renderDiscoveriesChartsNew' not in html_content:
        js_nuevo = '''
        // ✨ FUNCIONES DE NOVEDADES INTEGRADAS - SISTEMA NUEVO ✨

        function renderDiscoveriesChartsNew(userStats) {
            console.log('✨ Renderizando gráficos de novedades (integrado)...', userStats);

            // Destruir charts existentes
            const discoveriesChartIds = [
                'discoveriesSummaryChart', 'discoveriesArtistsChart', 'discoveriesAlbumsChart',
                'discoveriesTracksChart', 'discoveriesLabelsChart', 'discoveriesGenresChart'
            ];

            discoveriesChartIds.forEach(chartId => {
                if (charts[chartId]) {
                    charts[chartId].destroy();
                    delete charts[chartId];
                }
            });

            if (!userStats || !userStats.discoveries) {
                console.error('❌ No hay datos de novedades en userStats');
                console.log('📋 Estructura:', Object.keys(userStats || {}));
                showDiscoveriesErrorNew('No hay datos de novedades. Usuario debe ser reprocesado con el sistema nuevo.');
                return;
            }

            const discoveriesData = userStats.discoveries;
            console.log('🔍 Datos encontrados:', discoveriesData);

            try {
                // 1. Gráfico resumen
                if (discoveriesData.summary) {
                    renderDiscoveriesSummaryChartNew(discoveriesData.summary);
                }

                // 2. Gráficos scatter
                if (discoveriesData.details) {
                    renderDiscoveriesScatterChartNew('artists', discoveriesData.details.artists, '🎨 Artistas');
                    renderDiscoveriesScatterChartNew('albums', discoveriesData.details.albums, '💿 Álbumes');
                    renderDiscoveriesScatterChartNew('tracks', discoveriesData.details.tracks, '🎵 Canciones');
                    renderDiscoveriesScatterChartNew('labels', discoveriesData.details.labels, '🏷️ Sellos');
                    renderDiscoveriesScatterChartNew('genres', discoveriesData.details.genres, '🎶 Géneros');
                }

                console.log('✅ Gráficos renderizados');
            } catch (error) {
                console.error('❌ Error:', error);
                showDiscoveriesErrorNew('Error: ' + error.message);
            }
        }

        function renderDiscoveriesSummaryChartNew(summaryData) {
            const canvas = document.getElementById('discoveriesSummaryChart');
            if (!canvas) return;

            console.log('📊 Resumen:', summaryData);

            const datasets = [];
            const types = ['artists', 'albums', 'tracks', 'labels', 'genres'];
            const labels = {'artists': '🎨 Artistas', 'albums': '💿 Álbumes', 'tracks': '🎵 Canciones', 'labels': '🏷️ Sellos', 'genres': '🎶 Géneros'};

            let years = [];

            types.forEach((type, i) => {
                const data = summaryData[type];
                if (data && data.yearly_counts) {
                    if (years.length === 0) {
                        years = data.years || Object.keys(data.yearly_counts).map(Number).sort();
                    }

                    datasets.push({
                        label: labels[type],
                        data: years.map(year => data.yearly_counts[year] || 0),
                        borderColor: colors[i % colors.length],
                        backgroundColor: colors[i % colors.length] + '20',
                        tension: 0.4,
                        fill: false
                    });
                }
            });

            if (datasets.length === 0) {
                showNoDataForDiscoveriesChartNew('discoveriesSummaryChart');
                return;
            }

            charts['discoveriesSummaryChart'] = new Chart(canvas, {
                type: 'line',
                data: { labels: years, datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom', labels: { color: '#cdd6f4', padding: 15, usePointStyle: true }},
                        tooltip: { backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4', borderColor: '#cba6f7', borderWidth: 1 }
                    },
                    scales: {
                        x: { title: { display: true, text: 'Año', color: '#cdd6f4' }, ticks: { color: '#a6adc8' }, grid: { color: '#313244' }},
                        y: { title: { display: true, text: 'Novedades', color: '#cdd6f4' }, ticks: { color: '#a6adc8' }, grid: { color: '#313244' }, beginAtZero: true }
                    }
                }
            });
        }

        function renderDiscoveriesScatterChartNew(type, typeData, label) {
            const canvasId = `discoveries${type.charAt(0).toUpperCase() + type.slice(1)}Chart`;
            const canvas = document.getElementById(canvasId);

            if (!canvas || !typeData || !typeData.top_by_year) {
                console.log(`⚠️ Sin datos para ${type}`);
                showNoDataForDiscoveriesChartNew(canvasId);
                return;
            }

            const datasets = [];
            const years = typeData.years || Object.keys(typeData.top_by_year).map(Number).sort();

            // Obtener top 5
            const allItems = new Set();
            Object.values(typeData.top_by_year).forEach(yearItems => {
                yearItems.forEach(item => allItems.add(item.name));
            });

            const itemTotals = {};
            allItems.forEach(item => {
                itemTotals[item] = 0;
                Object.values(typeData.top_by_year).forEach(yearItems => {
                    const itemData = yearItems.find(i => i.name === item);
                    if (itemData) itemTotals[item] += itemData.period_plays;
                });
            });

            const topItems = Object.entries(itemTotals).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([name]) => name);

            topItems.forEach((itemName, i) => {
                const points = years.map(year => {
                    const yearItems = typeData.top_by_year[year] || [];
                    const itemData = yearItems.find(item => item.name === itemName);
                    return itemData && itemData.period_plays > 0 ? {
                        x: year, y: itemData.period_plays, itemName, firstYear: itemData.first_year, itemType: itemData.type
                    } : null;
                }).filter(Boolean);

                if (points.length > 0) {
                    datasets.push({
                        label: itemName.length > 25 ? itemName.substring(0, 25) + '...' : itemName,
                        data: points,
                        backgroundColor: colors[i % colors.length],
                        borderColor: colors[i % colors.length],
                        pointRadius: 6,
                        showLine: false
                    });
                }
            });

            if (datasets.length === 0) {
                showNoDataForDiscoveriesChartNew(canvasId);
                return;
            }

            charts[canvasId] = new Chart(canvas, {
                type: 'scatter',
                data: { datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: { type: 'linear', title: { display: true, text: 'Año', color: '#a6adc8' }, ticks: { color: '#a6adc8', stepSize: 1 }, grid: { color: '#313244' }, min: Math.min(...years) - 0.5, max: Math.max(...years) + 0.5 },
                        y: { title: { display: true, text: 'Scrobbles', color: '#a6adc8' }, ticks: { color: '#a6adc8' }, grid: { color: '#313244' }, beginAtZero: true }
                    },
                    plugins: {
                        legend: { display: true, position: 'bottom', labels: { color: '#cdd6f4', padding: 12, usePointStyle: true, font: { size: 9 }, maxWidth: 120 }},
                        tooltip: { backgroundColor: '#1e1e2e', titleColor: '#cba6f7', bodyColor: '#cdd6f4', borderColor: '#cba6f7', borderWidth: 1 }
                    }
                }
            });
        }

        function showDiscoveriesErrorNew(message) {
            const grid = document.getElementById('discoveriesGrid');
            if (grid) {
                grid.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 40px;"><h4 style="color: #f38ba8;">❌ ${message}</h4><p style="color: #a6adc8;">Regenera el HTML con el sistema corregido.</p></div>`;
            }
        }

        function showNoDataForDiscoveriesChartNew(canvasId) {
            const canvas = document.getElementById(canvasId);
            if (canvas && canvas.parentElement) {
                canvas.style.display = 'none';
                canvas.parentElement.innerHTML = '<div style="height: 200px; display: flex; align-items: center; justify-content: center; color: #a6adc8; font-style: italic;">Sin novedades</div>';
            }
        }
        '''

        # Insertar antes del último </script>
        script_pattern = r'(\s*</script>\s*</body>\s*</html>)'
        html_content = re.sub(script_pattern, js_nuevo + r'\n\1', html_content, flags=re.DOTALL)
        print("  ✅ Funciones nuevas agregadas")

    # 3. Actualizar la navegación para usar la función correcta
    nav_pattern = r'(if \(view === \'discoveries\'\) \{\s*loadDiscoveriesData\(currentUser\);)'
    if re.search(nav_pattern, html_content):
        replacement = r'if (view === \'discoveries\') { if (allStats[currentUser]) { renderDiscoveriesChartsNew(allStats[currentUser]); } else { loadDiscoveriesData(currentUser); } }'
        html_content = re.sub(nav_pattern, replacement, html_content)
        print("  ✅ Navegación actualizada")

    # 4. Actualizar selectUser también
    select_pattern = r'(} else if \(currentView === \'evolution\'\) \{\s*renderEvolutionCharts\(userStats\);\s*})'
    if re.search(select_pattern, html_content):
        replacement = r'\1 else if (currentView === \'discoveries\') { renderDiscoveriesChartsNew(userStats); }'
        html_content = re.sub(select_pattern, replacement, html_content)
        print("  ✅ selectUser actualizado")

    print("🎉 HTML arreglado para usar datos integrados")
    return html_content


def main():
    if len(sys.argv) != 2:
        print("❌ Uso: python fix_html_discoveries.py archivo.html")
        print("📋 Este script arregla un HTML existente para usar el nuevo sistema de novedades")
        sys.exit(1)

    input_file = sys.argv[1]

    if not os.path.exists(input_file):
        print(f"❌ Archivo no encontrado: {input_file}")
        sys.exit(1)

    print(f"🔧 Arreglando archivo: {input_file}")

    # Leer archivo
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"📖 Archivo leído: {len(html_content)} caracteres")
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        sys.exit(1)

    # Verificar que es un HTML de usuarios
    if 'Last.fm Usuarios - EstadÃ­sticas Individuales' not in html_content:
        print("❌ Este no parece ser un HTML de usuarios de Last.fm")
        sys.exit(1)

    # Verificar que tiene la pestaña discoveries
    if 'data-view="discoveries"' not in html_content:
        print("❌ Este HTML no tiene la pestaña de novedades")
        print("💡 Usa el sistema completo de generación en lugar de este script")
        sys.exit(1)

    # Arreglar el HTML
    html_fixed = fix_html_for_discoveries(html_content)

    # Crear archivo de salida
    input_path = Path(input_file)
    output_file = input_path.parent / f"{input_path.stem}_FIXED{input_path.suffix}"

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_fixed)
        print(f"✅ Archivo arreglado guardado: {output_file}")
        print(f"📊 Tamaño: {os.path.getsize(output_file) / 1024 / 1024:.2f} MB")
    except Exception as e:
        print(f"❌ Error guardando archivo: {e}")
        sys.exit(1)

    print("\n🎯 COMPLETADO")
    print("===============")
    print(f"📁 Archivo original: {input_file}")
    print(f"📁 Archivo arreglado: {output_file}")
    print("\n💡 IMPORTANTE:")
    print("- Este script solo arregla la parte JavaScript del HTML")
    print("- Para que funcione, el HTML debe contener datos de novedades integrados")
    print("- Si sigue sin funcionar, usa el sistema completo de generación")


if __name__ == '__main__':
    main()
