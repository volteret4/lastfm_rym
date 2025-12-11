#!/usr/bin/env python3
"""
DiscoveriesHTMLModifier - Versión CORREGIDA que integra correctamente el sistema de novedades
SOLUCIONADO: Funciones JavaScript simplificadas que usan datos ya incluidos en el HTML
"""

import re
from typing import Dict, List


class DiscoveriesHTMLModifier:
    """Clase para modificar HTML existente y agregar funcionalidad completa de novedades"""

    @staticmethod
    def add_discoveries_tab_navigation(html_content: str) -> str:
        """Agrega la pestaña de novedades a la navegación existente"""
        if 'data-view="discoveries"' in html_content:
            return html_content  # Ya existe

        # Buscar después de la pestaña de evolución
        evolution_pattern = r'(<div class="nav-tab"[^>]*data-view="evolution"[^>]*>.*?</div>)'
        matches = re.search(evolution_pattern, html_content, re.DOTALL)

        if matches:
            evolution_tab = matches.group(1)
            discoveries_tab = '                <div class="nav-tab" data-view="discoveries">✨ Novedades</div>'
            html_content = html_content.replace(evolution_tab, evolution_tab + '\n' + discoveries_tab, 1)

        return html_content

    @staticmethod
    def add_discoveries_tab_content(html_content: str) -> str:
        """Agrega el contenido HTML de la pestaña de novedades"""
        if 'id="discoveriesTab"' in html_content:
            return html_content  # Ya existe

        discoveries_content = '''
            <div id="discoveriesTab" class="tab-content">
                <div class="evolution-section">
                    <h3>✨ Descubrimientos Musicales</h3>

                    <div class="discoveries-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px;">
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

        # Buscar antes del popup o antes del cierre de content
        insert_patterns = [
            r'(<!-- Popup para mostrar detalles -->)',
            r'(        </div>\s*<!-- Popup)',
            r'(    </div>\s*<script>)',
            r'(</body>\s*</html>)'
        ]

        for pattern in insert_patterns:
            if re.search(pattern, html_content):
                html_content = re.sub(pattern, discoveries_content + r'\n\1', html_content, count=1)
                break

        return html_content

    @staticmethod
    def add_discoveries_javascript_functions(html_content: str) -> str:
        """Agrega las funciones JavaScript corregidas para las novedades"""

        # PASO 1: Eliminar completamente la función loadDiscoveriesData existente si existe
        old_function_patterns = [
            r'async function loadDiscoveriesData\([^)]*\)[^}]*\{[^}]*(?:\{[^}]*\}[^}]*)*\}',
            r'function loadDiscoveriesData\([^)]*\)[^}]*\{[^}]*(?:\{[^}]*\}[^}]*)*\}',
            r'// .*Funciones para manejo de novedades[\s\S]*?function loadDiscoveriesData[\s\S]*?\}\s*\}',
        ]

        for pattern in old_function_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.DOTALL)

        # PASO 2: Limpiar funciones relacionadas duplicadas y código roto
        cleanup_patterns = [
            r'console\.log`[^`]*\);',  # Arreglar console.log con template literals rotos
            r'throw new Error`[^`]*\);',  # Arreglar throw new Error con template literals rotos
            r'loadingElement\.style\.display = \'block\';[\s\S]*?showDiscoveriesError\([^)]*\);\s*\}',
            r'// âœ¨ Funciones para manejo de novedades[\s\S]*?const loadingElement = document\.getElementById\([^)]*\);[\s\S]*?\}\s*\}',
            r'const loadingElement = document\.getElementById\([^)]*\);[\s\S]*?console\.error\([^)]*\);[\s\S]*?return;[\s\S]*?\}',
            r'...`\);[\s\S]*?const loadingElement[\s\S]*?return;[\s\S]*?\}',
        ]

        for pattern in cleanup_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.DOTALL)

        # PASO 3: Insertar las funciones corregidas
        js_discoveries = '''
        // ✨ FUNCIONES DE NOVEDADES - CORREGIDAS Y COMPLETAS ✨

        function loadDiscoveriesData(username) {
            console.log('Cargando datos de novedades para ' + username + '...');

            try {
                // CORREGIDO: Usar datos ya cargados en allStats en vez de hacer fetch
                if (allStats && allStats[username] && allStats[username].discoveries) {
                    console.log('Usando datos de novedades desde allStats');
                    renderDiscoveriesCharts(allStats[username]);
                    return;
                }

                // Fallback si no hay datos de novedades
                console.warn('No se encontraron datos de novedades para', username);
                showDiscoveriesError('No hay datos de novedades disponibles para este usuario');

            } catch (error) {
                console.error('Error cargando novedades:', error);
                showDiscoveriesError(error.message);
            }
        }

        function renderDiscoveriesCharts(userStats) {
            console.log('✨ Renderizando gráficos de novedades...');

            if (!userStats || !userStats.discoveries) {
                console.error('❌ No hay datos de novedades disponibles');
                showDiscoveriesError('No hay datos de novedades disponibles para este usuario');
                return;
            }

            const discoveriesData = userStats.discoveries;
            console.log('🔍 Datos de novedades encontrados:', Object.keys(discoveriesData));

            try {
                const discoveryTypes = [
                    {type: 'artists', canvasId: 'discoveriesArtistsChart', title: 'Top 10 Artistas Nuevos'},
                    {type: 'albums', canvasId: 'discoveriesAlbumsChart', title: 'Top 10 Álbumes Nuevos'},
                    {type: 'tracks', canvasId: 'discoveriesTracksChart', title: 'Top 10 Canciones Nuevas'},
                    {type: 'labels', canvasId: 'discoveriesLabelsChart', title: 'Top 10 Sellos Nuevos'}
                ];

                discoveryTypes.forEach(function(config) {
                    if (discoveriesData.details && discoveriesData.details[config.type]) {
                        renderDiscoveryScatterChart(config.canvasId, discoveriesData.details[config.type], config.title);
                    } else {
                        showNoDataForDiscoveriesChart(config.canvasId);
                    }
                });

                console.log('✅ Gráficos de novedades renderizados correctamente');
            } catch (error) {
                console.error('❌ Error renderizando novedades:', error);
                showDiscoveriesError('Error procesando datos de novedades: ' + error.message);
            }
        }

        function renderDiscoveryScatterChart(canvasId, typeData, title) {
            const canvas = document.getElementById(canvasId);
            if (!canvas) {
                console.error('❌ Canvas ' + canvasId + ' no encontrado');
                return;
            }

            if (!typeData || !typeData.top_by_year) {
                console.log('⚠️ Sin datos para ' + canvasId);
                showNoDataForDiscoveriesChart(canvasId);
                return;
            }

            console.log('🔄 Renderizando scatter ' + canvasId + '...', typeData);

            // Destruir chart existente si existe
            if (charts && charts[canvasId]) {
                charts[canvasId].destroy();
                delete charts[canvasId];
            }

            const years = typeData.years || [];
            const datasets = [];

            // Recopilar todos los elementos únicos de todos los años
            const allItems = new Set();
            years.forEach(function(year) {
                const yearItems = typeData.top_by_year[year] || [];
                yearItems.forEach(function(item) {
                    allItems.add(item.name);
                });
            });

            // Calcular totales para obtener los top 10 globales
            const itemTotals = {};
            Array.from(allItems).forEach(function(item) {
                itemTotals[item] = 0;
                years.forEach(function(year) {
                    const yearItems = typeData.top_by_year[year] || [];
                    const itemData = yearItems.find(function(i) { return i.name === item; });
                    if (itemData) {
                        itemTotals[item] += itemData.period_plays;
                    }
                });
            });

            // Obtener top 10 elementos por scrobbles totales
            const topItems = Object.entries(itemTotals)
                .sort(function(a, b) { return b[1] - a[1]; })
                .slice(0, 10)
                .map(function(entry) { return entry[0]; });

            console.log('Top 10 elementos para ' + canvasId + ':', topItems);

            // Crear datasets para cada elemento
            topItems.forEach(function(itemName, index) {
                const points = [];

                years.forEach(function(year) {
                    const yearItems = typeData.top_by_year[year] || [];
                    const itemData = yearItems.find(function(i) { return i.name === itemName; });

                    if (itemData && itemData.period_plays > 0) {
                        points.push({
                            x: year,
                            y: itemData.period_plays,
                            itemName: itemName,
                            firstYear: itemData.first_year
                        });
                    }
                });

                if (points.length > 0) {
                    const color = colors[index % colors.length];
                    datasets.push({
                        label: itemName.length > 25 ? itemName.substring(0, 25) + '...' : itemName,
                        data: points,
                        borderColor: color,
                        backgroundColor: color,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        showLine: true,
                        tension: 0.2
                    });
                }
            });

            if (datasets.length === 0) {
                console.log('⚠️ Sin datasets para ' + canvasId);
                showNoDataForDiscoveriesChart(canvasId);
                return;
            }

            const config = {
                type: 'scatter',
                data: { datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#cdd6f4',
                                padding: 10,
                                usePointStyle: true,
                                font: { size: 10 },
                                boxHeight: 8,
                                boxWidth: 8
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1,
                            callbacks: {
                                title: function(context) {
                                    return context[0].raw.itemName;
                                },
                                label: function(context) {
                                    const point = context.raw;
                                    return [
                                        'Año: ' + point.x,
                                        'Scrobbles: ' + point.y,
                                        'Primera vez: ' + point.firstYear
                                    ];
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'linear',
                            position: 'bottom',
                            title: { display: true, text: 'Año', color: '#cdd6f4' },
                            ticks: {
                                color: '#a6adc8',
                                stepSize: 1,
                                callback: function(value) { return Math.round(value); }
                            },
                            grid: { color: '#313244' },
                            min: Math.min.apply(Math, years) - 0.5,
                            max: Math.max.apply(Math, years) + 0.5
                        },
                        y: {
                            title: { display: true, text: 'Scrobbles', color: '#cdd6f4' },
                            ticks: { color: '#a6adc8' },
                            grid: { color: '#313244' },
                            beginAtZero: true
                        }
                    },
                    interaction: {
                        mode: 'point'
                    }
                }
            };

            if (!charts) {
                charts = {};
            }
            charts[canvasId] = new Chart(canvas, config);
            console.log('✅ Gráfico scatter ' + canvasId + ' creado exitosamente');
        }

        function showDiscoveriesError(message) {
            const gridElement = document.querySelector('.discoveries-grid');
            if (gridElement) {
                gridElement.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 40px;">' +
                    '<h4 style="color: #f38ba8; margin-bottom: 15px;">⚠ Error en Novedades</h4>' +
                    '<p style="color: #cdd6f4; margin-bottom: 10px;">' + message + '</p>' +
                    '<p style="font-size: 0.8em; color: #6c7086;">' +
                    'Las novedades comparan el período seleccionado con años anteriores' +
                    '</p>' +
                '</div>';
            }
        }

        function showNoDataForDiscoveriesChart(canvasId) {
            const canvas = document.getElementById(canvasId);
            if (canvas) {
                canvas.style.display = 'none';
                const wrapper = canvas.parentElement;
                if (wrapper) {
                    wrapper.innerHTML = '<div style="height: 200px; display: flex; align-items: center; justify-content: center; color: #a6adc8; font-style: italic; background: #313244; border-radius: 8px;">Sin novedades para mostrar</div>';
                }
            }
        }
        '''

        # Buscar donde insertar el JavaScript (antes del cierre del script principal)
        insert_patterns = [
            r'(    </script>\s*</body>\s*</html>)',
            r'(</script>\s*</body>)',
            r'(    </script>)',
            r'(</script>)'
        ]

        inserted = False
        for pattern in insert_patterns:
            if re.search(pattern, html_content, re.DOTALL):
                html_content = re.sub(pattern, js_discoveries + r'\n\1', html_content, count=1, flags=re.DOTALL)
                inserted = True
                break

        if not inserted:
            # Fallback: insertar antes del cierre de body
            html_content = re.sub(r'(</body>)', '<script>' + js_discoveries + '</script>\n\\1', html_content)

        return html_content

    @staticmethod
    def add_discoveries_navigation_logic(html_content: str) -> str:
        """Agrega la lógica de navegación para la pestaña de novedades"""
        if 'loadDiscoveriesData(currentUser);' in html_content:
            return html_content  # Ya existe

        # Buscar el patrón de navegación de pestañas y agregar el caso de novedades
        navigation_patterns = [
            r"(} else if \(view === 'evolution'\) \{\s*renderEvolutionCharts\(userStats\);)",
            r"(} else if \(currentView === 'evolution'\) \{\s*renderEvolutionCharts\(allStats\[currentUser\]\);)"
        ]

        for pattern in navigation_patterns:
            if re.search(pattern, html_content):
                replacement = r"\1 } else if (view === 'discoveries' || currentView === 'discoveries') { loadDiscoveriesData(currentUser);"
                html_content = re.sub(pattern, replacement, html_content)
                break

        # También buscar en la función selectUser
        select_user_pattern = r"(} else if \(currentView === 'evolution'\) \{\s*renderEvolutionCharts\(userStats\);)"
        if re.search(select_user_pattern, html_content):
            replacement = r"\1 } else if (currentView === 'discoveries') { loadDiscoveriesData(username);"
            html_content = re.sub(select_user_pattern, replacement, html_content)

        return html_content

    @classmethod
    def apply_all_modifications(cls, html_content: str) -> str:
        """Aplica todas las modificaciones de novedades al HTML de una vez"""
        print("🔧 Aplicando modificaciones de novedades...")

        # 1. Agregar navegación de pestaña
        html_content = cls.add_discoveries_tab_navigation(html_content)
        print("  ✅ Pestaña de navegación agregada")

        # 2. Agregar contenido HTML
        html_content = cls.add_discoveries_tab_content(html_content)
        print("  ✅ Contenido HTML agregado")

        # 3. Agregar JavaScript
        html_content = cls.add_discoveries_javascript_functions(html_content)
        print("  ✅ Funciones JavaScript agregadas")

        # 4. Agregar lógica de navegación
        html_content = cls.add_discoveries_navigation_logic(html_content)
        print("  ✅ Lógica de navegación agregada")

        print("🎉 Modificaciones de novedades aplicadas completamente")
        return html_content


# Función de conveniencia para uso directo
def add_discoveries_to_html(html_content: str) -> str:
    """Función de conveniencia para agregar novedades a HTML existente"""
    return DiscoveriesHTMLModifier.apply_all_modifications(html_content)


if __name__ == '__main__':
    print("🔧 DiscoveriesHTMLModifier - Clase para agregar novedades al HTML")
    print("📖 Uso:")
    print("   from discoveries_html_modifier import DiscoveriesHTMLModifier")
    print("   html_modified = DiscoveriesHTMLModifier.apply_all_modifications(html_content)")
    print("   # o")
    print("   from discoveries_html_modifier import add_discoveries_to_html")
    print("   html_modified = add_discoveries_to_html(html_content)")
