#!/usr/bin/env python3
"""
DiscoveriesHTMLModifier - Versión CORREGIDA que integra correctamente el sistema de novedades
Soluciona el problema de que no aparecen los gráficos
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
            <!-- ✨ PESTAÑA DE NOVEDADES COMPLETAMENTE FUNCIONAL ✨ -->
            <div id="discoveriesTab" class="tab-content">
                <div class="evolution-section">
                    <h3>✨ Descubrimientos Musicales</h3>
                    <p style="text-align: center; color: #a6adc8; margin-bottom: 30px; font-style: italic;">
                        Elementos que aparecen por primera vez en el período seleccionado comparado con todos los años anteriores
                    </p>

                    <!-- Gráfico de resumen de líneas -->
                    <div class="discoveries-summary-chart" style="background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #f38ba8; margin-bottom: 30px;">
                        <h4 style="color: #f38ba8; font-size: 1.2em; margin-bottom: 15px; text-align: center;">📊 Resumen Anual de Novedades</h4>
                        <div style="position: relative; height: 400px;">
                            <canvas id="discoveriesSummaryChart"></canvas>
                        </div>
                    </div>

                    <!-- Gráficos scatter individuales por tipo -->
                    <div class="discoveries-grid" id="discoveriesGrid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(600px, 1fr)); gap: 25px;">
                        <div class="discoveries-chart" style="background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #313244; margin-bottom: 20px;">
                            <h4 style="color: #cba6f7; font-size: 1.1em; margin-bottom: 15px; text-align: center;">🎨 Top 5 Artistas Nuevos por Año</h4>
                            <div style="position: relative; height: 400px;">
                                <canvas id="discoveriesArtistsChart"></canvas>
                            </div>
                        </div>

                        <div class="discoveries-chart" style="background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #313244; margin-bottom: 20px;">
                            <h4 style="color: #cba6f7; font-size: 1.1em; margin-bottom: 15px; text-align: center;">💿 Top 5 Álbumes Nuevos por Año</h4>
                            <div style="position: relative; height: 400px;">
                                <canvas id="discoveriesAlbumsChart"></canvas>
                            </div>
                        </div>

                        <div class="discoveries-chart" style="background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #313244; margin-bottom: 20px;">
                            <h4 style="color: #cba6f7; font-size: 1.1em; margin-bottom: 15px; text-align: center;">🎵 Top 5 Canciones Nuevas por Año</h4>
                            <div style="position: relative; height: 400px;">
                                <canvas id="discoveriesTracksChart"></canvas>
                            </div>
                        </div>

                        <div class="discoveries-chart" style="background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #313244; margin-bottom: 20px;">
                            <h4 style="color: #cba6f7; font-size: 1.1em; margin-bottom: 15px; text-align: center;">🏷️ Top 5 Sellos Nuevos por Año</h4>
                            <div style="position: relative; height: 400px;">
                                <canvas id="discoveriesLabelsChart"></canvas>
                            </div>
                        </div>

                        <div class="discoveries-chart" style="background: #1e1e2e; border-radius: 12px; padding: 20px; border: 2px solid #313244; margin-bottom: 20px;">
                            <h4 style="color: #cba6f7; font-size: 1.1em; margin-bottom: 15px; text-align: center;">🎶 Top 5 Géneros Nuevos por Año</h4>
                            <div style="position: relative; height: 400px;">
                                <canvas id="discoveriesGenresChart"></canvas>
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
        """Agrega las funciones JavaScript necesarias para las novedades"""
        if 'renderDiscoveriesCharts' in html_content:
            return html_content  # Ya existe

        js_discoveries = '''
        // ✨ FUNCIONES DE NOVEDADES - COMPLETAMENTE FUNCIONALES ✨

        function renderDiscoveriesCharts(userStats) {
            console.log('✨ Renderizando gráficos de novedades...');

            // Destruir charts existentes relacionados con novedades
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
                console.error('❌ No hay datos de novedades disponibles');
                showDiscoveriesError('No hay datos de novedades disponibles para este usuario');
                return;
            }

            const discoveriesData = userStats.discoveries;
            console.log('🔍 Datos de novedades encontrados:', Object.keys(discoveriesData));

            try {
                // 1. Gráfico de resumen de líneas (todas las categorías juntas)
                renderDiscoveriesSummaryChart(discoveriesData.summary);

                // 2. Gráficos scatter individuales para cada tipo
                renderDiscoveriesScatterChart('artists', discoveriesData.details.artists, '🎨 Artistas');
                renderDiscoveriesScatterChart('albums', discoveriesData.details.albums, '💿 Álbumes');
                renderDiscoveriesScatterChart('tracks', discoveriesData.details.tracks, '🎵 Canciones');
                renderDiscoveriesScatterChart('labels', discoveriesData.details.labels, '🏷️ Sellos');
                renderDiscoveriesScatterChart('genres', discoveriesData.details.genres, '🎶 Géneros');

                console.log('✅ Gráficos de novedades renderizados correctamente');
            } catch (error) {
                console.error('❌ Error renderizando novedades:', error);
                showDiscoveriesError('Error procesando datos de novedades: ' + error.message);
            }
        }

        function renderDiscoveriesSummaryChart(summaryData) {
            const canvas = document.getElementById('discoveriesSummaryChart');
            if (!canvas) {
                console.error('❌ Canvas de resumen no encontrado');
                return;
            }

            if (!summaryData || Object.keys(summaryData).length === 0) {
                console.log('⚠️ Sin datos de resumen');
                return;
            }

            console.log('📊 Renderizando gráfico de resumen...', summaryData);

            const datasets = [];
            const discoveryTypes = ['artists', 'albums', 'tracks', 'labels', 'genres'];
            const typeLabels = {
                'artists': '🎨 Artistas',
                'albums': '💿 Álbumes',
                'tracks': '🎵 Canciones',
                'labels': '🏷️ Sellos',
                'genres': '🎶 Géneros'
            };

            discoveryTypes.forEach((type, index) => {
                const typeData = summaryData[type];
                if (typeData && typeData.yearly_counts) {
                    const data = typeData.years.map(year => typeData.yearly_counts[year] || 0);

                    datasets.push({
                        label: typeLabels[type],
                        data: data,
                        borderColor: colors[index % colors.length],
                        backgroundColor: colors[index % colors.length] + '20',
                        tension: 0.4,
                        fill: false,
                        pointRadius: 4,
                        pointHoverRadius: 8
                    });
                }
            });

            if (datasets.length === 0) {
                console.log('⚠️ Sin datasets para gráfico de resumen');
                showNoDataForDiscoveriesChart('discoveriesSummaryChart');
                return;
            }

            const years = summaryData.artists?.years || summaryData[Object.keys(summaryData)[0]]?.years || [];

            const config = {
                type: 'line',
                data: {
                    labels: years,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#cdd6f4',
                                padding: 15,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1e1e2e',
                            titleColor: '#cba6f7',
                            bodyColor: '#cdd6f4',
                            borderColor: '#cba6f7',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed.y + ' novedades';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Año',
                                color: '#cdd6f4'
                            },
                            ticks: {
                                color: '#a6adc8'
                            },
                            grid: {
                                color: '#313244'
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Número de Novedades',
                                color: '#cdd6f4'
                            },
                            ticks: {
                                color: '#a6adc8',
                                precision: 0
                            },
                            grid: {
                                color: '#313244'
                            },
                            beginAtZero: true
                        }
                    }
                }
            };

            charts['discoveriesSummaryChart'] = new Chart(canvas, config);
        }

        function renderDiscoveriesScatterChart(type, typeData, label) {
            const canvasId = `discoveries${type.charAt(0).toUpperCase() + type.slice(1)}Chart`;
            const canvas = document.getElementById(canvasId);

            if (!canvas) {
                console.error(`❌ Canvas ${canvasId} no encontrado`);
                return;
            }

            if (!typeData || !typeData.top_by_year || Object.keys(typeData.top_by_year).length === 0) {
                console.log(`⚠️ Sin datos para ${type}`);
                showNoDataForDiscoveriesChart(canvasId);
                return;
            }

            console.log(`🔍 Renderizando scatter ${type}...`, typeData);

            const datasets = [];
            const years = typeData.years || [];

            // Recopilar todos los elementos únicos y crear datasets
            const allItems = new Set();
            Object.values(typeData.top_by_year).forEach(yearItems => {
                yearItems.forEach(item => allItems.add(item.name));
            });

            // Limitar a top 5 elementos con más scrobbles totales
            const itemTotals = {};
            allItems.forEach(item => {
                itemTotals[item] = 0;
                Object.values(typeData.top_by_year).forEach(yearItems => {
                    const itemData = yearItems.find(i => i.name === item);
                    if (itemData) itemTotals[item] += itemData.period_plays;
                });
            });

            const topItems = Object.entries(itemTotals)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([name, _]) => name);

            topItems.forEach((itemName, index) => {
                const points = [];

                years.forEach(year => {
                    const yearItems = typeData.top_by_year[year] || [];
                    const itemData = yearItems.find(i => i.name === itemName);

                    if (itemData && itemData.period_plays > 0) {
                        points.push({
                            x: year,
                            y: itemData.period_plays,
                            itemName: itemName,
                            firstYear: itemData.first_year,
                            itemType: itemData.type
                        });
                    }
                });

                if (points.length > 0) {
                    datasets.push({
                        label: itemName.length > 30 ? itemName.substring(0, 30) + '...' : itemName,
                        data: points,
                        backgroundColor: colors[index % colors.length],
                        borderColor: colors[index % colors.length],
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        showLine: false
                    });
                }
            });

            if (datasets.length === 0) {
                console.log(`⚠️ Sin datasets para ${type}`);
                showNoDataForDiscoveriesChart(canvasId);
                return;
            }

            const config = {
                type: 'scatter',
                data: { datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            type: 'linear',
                            position: 'bottom',
                            title: {
                                display: true,
                                text: 'Año',
                                color: '#a6adc8'
                            },
                            ticks: {
                                color: '#a6adc8',
                                stepSize: 1
                            },
                            grid: {
                                color: '#313244'
                            },
                            min: Math.min(...years) - 0.5,
                            max: Math.max(...years) + 0.5
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Scrobbles',
                                color: '#a6adc8'
                            },
                            ticks: {
                                color: '#a6adc8'
                            },
                            grid: {
                                color: '#313244'
                            },
                            beginAtZero: true
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: {
                                color: '#cdd6f4',
                                padding: 12,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                font: {
                                    size: 10
                                },
                                boxHeight: 8,
                                boxWidth: 8,
                                maxWidth: 150
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
                                    const point = context[0].raw;
                                    return point.itemName;
                                },
                                label: function(context) {
                                    const point = context.raw;
                                    return [
                                        `Año: ${point.x}`,
                                        `Scrobbles: ${point.y}`,
                                        `Primera vez: ${point.firstYear}`
                                    ];
                                }
                            }
                        }
                    },
                    interaction: {
                        mode: 'point'
                    },
                    onClick: function(event, elements) {
                        if (elements.length > 0) {
                            const element = elements[0];
                            const point = this.data.datasets[element.datasetIndex].data[element.index];
                            showDiscoveryPopup(point.itemName, point.x, point.y, point.firstYear, label);
                        }
                    }
                }
            };

            charts[canvasId] = new Chart(canvas, config);
        }

        function showDiscoveriesError(message) {
            const gridElement = document.getElementById('discoveriesGrid');
            if (gridElement) {
                gridElement.innerHTML = `
                    <div style="grid-column: 1/-1; text-align: center; padding: 40px;">
                        <h4 style="color: #f38ba8; margin-bottom: 15px;">❌ Error en Novedades</h4>
                        <p style="color: #cdd6f4; margin-bottom: 10px;">${message}</p>
                        <p style="font-size: 0.8em; color: #6c7086;">
                            Las novedades comparan el período seleccionado con años anteriores para encontrar elementos nuevos
                        </p>
                    </div>
                `;
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

        function showDiscoveryPopup(itemName, year, scrobbles, firstYear, category) {
            const popupTitle = `${category} - ${year}`;
            const content = `
                <div class="popup-item">
                    <span class="name">Elemento: ${itemName}</span>
                </div>
                <div class="popup-item">
                    <span class="name">Año: ${year}</span>
                    <span class="count">${scrobbles} scrobbles</span>
                </div>
                <div class="popup-item">
                    <span class="name">Primera aparición: ${firstYear}</span>
                </div>
                <div class="popup-item">
                    <span class="name">Categoría: ${category}</span>
                </div>
            `;

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

        # Buscar donde insertar el JavaScript (antes del cierre del script principal)
        insert_patterns = [
            r'(        // ✓ FIX: Función para grÃ¡ficos de lÃ­neas individuales)',
            r'(        function _format_number\(number\) \{)',
            r'(    </script>\s*</body>\s*</html>)',
            r'(</script>)'
        ]

        for pattern in insert_patterns:
            if re.search(pattern, html_content, re.DOTALL):
                html_content = re.sub(pattern, js_discoveries + r'\n\1', html_content, count=1, flags=re.DOTALL)
                break

        return html_content

    @staticmethod
    def add_discoveries_navigation_logic(html_content: str) -> str:
        """Agrega la lógica de navegación para la pestaña de novedades"""
        if 'renderDiscoveriesCharts(allStats[currentUser]);' in html_content:
            return html_content  # Ya existe

        # Buscar el patrón de navegación de pestañas y agregar el caso de novedades
        navigation_patterns = [
            r"(} else if \(view === 'evolution'\) \{\s*renderEvolutionCharts\(userStats\);)",
            r"(} else if \(currentView === 'evolution'\) \{\s*renderEvolutionCharts\(allStats\[currentUser\]\);)"
        ]

        for pattern in navigation_patterns:
            if re.search(pattern, html_content):
                replacement = r"\1 } else if (view === 'discoveries' || currentView === 'discoveries') { renderDiscoveriesCharts(userStats || allStats[currentUser]);"
                html_content = re.sub(pattern, replacement, html_content)
                break

        # También buscar en la función selectUser
        select_user_pattern = r"(} else if \(currentView === 'evolution'\) \{\s*renderEvolutionCharts\(userStats\);)"
        if re.search(select_user_pattern, html_content):
            replacement = r"\1 } else if (currentView === 'discoveries') { renderDiscoveriesCharts(userStats);"
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
