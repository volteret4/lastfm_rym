
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
    