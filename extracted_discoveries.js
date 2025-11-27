// 🆕 Funciones para manejo de novedades
        async function loadDiscoveriesData(username) {
            console.log(`Cargando datos de novedades para ${username}...`);

            const loadingElement = document.getElementById('discoveriesLoading');
            const gridElement = document.getElementById('discoveriesGrid');

            if (loadingElement) loadingElement.style.display = 'block';
            if (gridElement) gridElement.style.display = 'none';

            try {
                if (discoveriesData[username]) {
                    console.log('Usando datos del cache');
                    renderDiscoveriesCharts(discoveriesData[username]);
                    return;
                }

                const currentYear = new Date().getFullYear();
                const fromYear = currentYear - yearsBackConfig;
                const period = `${fromYear}-${currentYear}`;
                const dataUrl = `data/usuarios/${period}/${username}.json`;

                console.log(`Cargando desde: ${dataUrl}`);

                const response = await fetch(dataUrl);
                if (!response.ok) throw new Error(`Error HTTP: ${response.status} - ${dataUrl}`);

                const userData = await response.json();
                console.log('Datos cargados:', userData);

                discoveriesData[username] = userData;
                renderDiscoveriesCharts(userData);

            } catch (error) {
                console.error('Error cargando novedades:', error);
                showDiscoveriesError(error.message);
            }
        }