#!/usr/bin/env python3
"""
HTML generator module for Last.fm statistics
Módulo generador de HTML para estadísticas de Last.fm
"""

import json
from typing import Dict, List


class HTMLGenerator:
    @staticmethod
    def create_html(stats: Dict, users: List[str], period_type: str = "semanal") -> str:
        """
        Crea el HTML para las estadísticas con categorías desplegables

        Args:
            stats: Diccionario con las estadísticas
            users: Lista de usuarios
            period_type: Tipo de período ('semanal', 'mensual', 'anual')

        Returns:
            String con el contenido HTML completo
        """
        users_json = json.dumps(users, ensure_ascii=False)
        stats_json = json.dumps(stats, indent=2, ensure_ascii=False)

        # Determinar qué categorías incluir
        categories = ['artists', 'tracks', 'albums', 'genres', 'labels', 'years']
        if 'novelties' in stats:
            categories.append('novelties')

        # Crear lista de filtros para JavaScript
        category_filters_html = ""
        for category in categories:
            label = {
                'artists': 'Artistas',
                'tracks': 'Canciones',
                'albums': 'Álbumes',
                'genres': 'Géneros',
                'labels': 'Sellos',
                'years': 'Años',
                'novelties': 'Novedades'
            }.get(category, category.title())

            # Activar "artistas" por defecto, o "novelties" si no hay artistas
            active_class = ''
            if category == 'artists':
                active_class = 'active'

            category_filters_html += f'<button class="category-filter {active_class}" data-category="{category}">{label}</button>'

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Last.fm Stats - {stats.get('period_label', 'Estadísticas')}</title>
    <link rel="icon" type="image/png" href="images/music.png">

    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #cdd6f4;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: #181825;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: #1e1e2e;
            padding: 20px 30px;
            border-bottom: 2px solid #cba6f7;
            display: flex;
            justify-content: space-between;
            align-items: center;
            min-height: 80px;
        }}

        .header-content {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex-grow: 1;
        }}

        h1 {{
            font-size: 1.8em;
            color: #cba6f7;
            margin: 0;
            text-align: center;
        }}

        .nav-buttons {{
            display: flex;
            gap: 15px;
            margin-top: 10px;
        }}

        .nav-button {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
            text-decoration: none;
            display: inline-block;
        }}

        .nav-button:hover {{
            border-color: #cba6f7;
            background: #45475a;
            color: #cdd6f4;
        }}

        .nav-button.current {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .user-button {{
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #181825;
            color: #1e1e2e;
            border: none;
            cursor: pointer;
            font-size: 1.2em;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s;
            flex-shrink: 0;
        }}

        .user-button:hover {{
            background: #b4a3e8;
            transform: scale(1.1);
        }}

        .user-modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 1000;
            backdrop-filter: blur(5px);
        }}

        .user-modal-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border-radius: 12px;
            padding: 30px;
            width: 90%;
            max-width: 400px;
            border: 2px solid #cba6f7;
        }}

        .user-modal-header {{
            color: #cba6f7;
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 20px;
            text-align: center;
        }}

        .user-modal-close {{
            position: absolute;
            top: 15px;
            right: 20px;
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.5em;
            cursor: pointer;
            padding: 0;
        }}

        .user-modal-close:hover {{
            color: #cba6f7;
        }}

        .user-options {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .user-option {{
            padding: 12px 20px;
            background: #313244;
            border: 2px solid #45475a;
            border-radius: 8px;
            color: #cdd6f4;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
        }}

        .user-option:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .user-option.selected {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .controls {{
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
            justify-content: center;
        }}

        .control-group {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
        }}

        .control-group label {{
            color: #cba6f7;
            font-weight: 600;
        }}

        .category-filters {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .category-filter {{
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }}

        .category-filter:hover {{
            border-color: #cba6f7;
            background: #45475a;
        }}

        .category-filter.active {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .period-header {{
            background: #1e1e2e;
            padding: 25px 30px;
            border-bottom: 2px solid #cba6f7;
        }}

        .period-header h2 {{
            color: #cba6f7;
            font-size: 1.5em;
            margin-bottom: 8px;
        }}

        .period-info {{
            color: #a6adc8;
            font-size: 0.9em;
        }}

        .stats-container {{
            padding: 30px;
        }}

        .categories {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }}

        .category {{
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
            display: none;
        }}

        .category.visible {{
            display: block;
        }}

        .category h3 {{
            color: #cba6f7;
            font-size: 1.2em;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #cba6f7;
        }}

        .item {{
            padding: 12px;
            margin-bottom: 10px;
            background: #181825;
            border-radius: 8px;
            border-left: 3px solid #45475a;
            transition: all 0.3s;
            cursor: pointer;
        }}

        .item:hover {{
            transform: translateX(5px);
            border-left-color: #cba6f7;
        }}

        .item.highlighted {{
            border-left-color: #cba6f7;
            background: #1a1826;
        }}

        .item-name {{
            font-weight: 600;
            color: #cdd6f4;
            font-size: 1em;
        }}

        .item-meta {{
            margin-top: 8px;
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}

        .badge {{
            background: #45475a;
            color: #cdd6f4;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: 600;
        }}

        .user-badge {{
            background: #313244;
            color: #a6adc8;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75em;
            border: 1px solid #45475a;
        }}

        .user-badge.highlighted-user {{
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }}

        .expandable {{
            position: relative;
        }}

        .expandable::after {{
            content: '▼';
            position: absolute;
            right: 12px;
            top: 12px;
            color: #6c7086;
            font-size: 0.8em;
        }}

        .expandable.expanded::after {{
            content: '▲';
        }}

        .details {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            padding: 0 15px;
            margin-top: 10px;
        }}

        .details.expanded {{
            max-height: 400px;
            overflow-y: auto;
            border-top: 1px solid #313244;
            padding-top: 15px;
        }}

        .detail-section {{
            margin-bottom: 15px;
        }}

        .detail-title {{
            color: #f9e2af;
            font-size: 0.9em;
            font-weight: 600;
            margin-bottom: 8px;
        }}

        .detail-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
        }}

        .detail-item {{
            background: #181825;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            color: #a6adc8;
        }}

        .novelty-section {{
            margin-bottom: 25px;
        }}

        .novelty-section h4 {{
            color: #a6e3a1;
            font-size: 1.05em;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 1px solid #45475a;
        }}

        .novelty-subsection {{
            margin-bottom: 20px;
        }}

        .novelty-subsection h5 {{
            color: #f9e2af;
            font-size: 0.95em;
            margin-bottom: 10px;
        }}

        .novelty-empty {{
            color: #6c7086;
            font-style: italic;
            text-align: center;
            padding: 20px;
        }}

        .artists-popup {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #1e1e2e;
            border: 2px solid #cba6f7;
            border-radius: 12px;
            padding: 20px;
            max-width: 500px;
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }}

        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 999;
        }}

        .popup-header {{
            color: #cba6f7;
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 15px;
            border-bottom: 1px solid #313244;
            padding-bottom: 10px;
        }}

        .popup-close {{
            float: right;
            background: none;
            border: none;
            color: #cdd6f4;
            font-size: 1.2em;
            cursor: pointer;
            padding: 0;
            margin-top: -5px;
        }}

        .popup-close:hover {{
            color: #cba6f7;
        }}

        .artist-list {{
            list-style: none;
            padding: 0;
        }}

        .artist-list li {{
            padding: 8px 12px;
            background: #181825;
            margin-bottom: 5px;
            border-radius: 6px;
            border-left: 3px solid #45475a;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #6c7086;
            font-style: italic;
        }}

        .last-update {{
            text-align: center;
            padding: 20px;
            color: #6c7086;
            font-size: 0.85em;
            border-top: 1px solid #313244;
        }}

        @media (max-width: 768px) {{
            .categories {{
                grid-template-columns: 1fr;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .category-filters {{
                justify-content: center;
            }}

            .artists-popup {{
                max-width: 90%;
                max-height: 80%;
            }}

            header {{
                flex-direction: column;
                gap: 15px;
            }}

            .nav-buttons {{
                order: -1;
            }}

            .user-button {{
                order: 1;
                align-self: flex-end;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-content">
                <h1>📊 RYM Hispano Estadísticas</h1>
                <div class="nav-buttons">
                    <a href="esta-semana.html" class="nav-button">TEMPORALES</a>
                    <a href="index.html#grupo" class="nav-button">GRUPO</a>
                    <a href="index.html#about" class="nav-button">ACERCA DE</a>
                </div>
            </div>
            <button class="user-button" id="userButton">👤</button>
        </header>

        <!-- Modal de selección de usuario -->
        <div class="user-modal" id="userModal">
            <div class="user-modal-content">
                <button class="user-modal-close" id="userModalClose">×</button>
                <div class="user-modal-header">Seleccionar Usuario</div>
                <div class="user-options" id="userOptions">
                    <!-- Se llenarán dinámicamente -->
                </div>
            </div>
        </div>

        <div class="controls">
            <div class="control-group">

                <div class="category-filters">
                    {category_filters_html}
                </div>
            </div>
        </div>

        <div class="period-header">
            <h2>{stats.get('period_label', 'Estadísticas')}</h2>
            <p class="period-info">
                <span id="dateRange"></span> |
                <span id="totalScrobbles"></span> scrobbles totales
            </p>
        </div>

        <div class="stats-container">
            <div class="categories" id="categoriesContainer">
                <!-- Se llenará dinámicamente -->
            </div>
        </div>

        <div class="last-update">
            Generado: <span id="generatedAt"></span>
        </div>
    </div>

    <script>
        // Usuarios reales del entorno LASTFM_USERS
        const availableUsers = {users_json};
        const stats = {stats_json};
        const hasNovelties = stats.novelties !== undefined;

        // Función para obtener novedades de usuario desde datos precalculados
        function getUserNovelties(user) {{
            if (!stats.novelties || !stats.novelties.nuevos_para_usuarios) {{
                return {{ artists: [], albums: [], tracks: [] }};
            }}

            return stats.novelties.nuevos_para_usuarios[user] || {{ artists: [], albums: [], tracks: [] }};
        }}

        // Funcionalidad del botón de usuario
        function initializeUserSelector() {{
            const userButton = document.getElementById('userButton');
            const userModal = document.getElementById('userModal');
            const userModalClose = document.getElementById('userModalClose');
            const userOptions = document.getElementById('userOptions');

            // Cargar usuario guardado desde localStorage
            let selectedUser = localStorage.getItem('lastfm_selected_user') || '';

            // Llenar opciones de usuarios
            availableUsers.forEach(user => {{
                const option = document.createElement('div');
                option.className = 'user-option';
                option.dataset.user = user;
                option.textContent = user;
                userOptions.appendChild(option);
            }});

            // Marcar opción seleccionada
            updateSelectedUserOption(selectedUser);

            // Event listeners
            userButton.addEventListener('click', () => {{
                userModal.style.display = 'block';
            }});

            userModalClose.addEventListener('click', () => {{
                userModal.style.display = 'none';
            }});

            userModal.addEventListener('click', (e) => {{
                if (e.target === userModal) {{
                    userModal.style.display = 'none';
                }}
            }});

            userOptions.addEventListener('click', (e) => {{
                if (e.target.classList.contains('user-option')) {{
                    const user = e.target.dataset.user;
                    selectedUser = user;

                    // Guardar en localStorage
                    if (user) {{
                        localStorage.setItem('lastfm_selected_user', user);
                    }} else {{
                        localStorage.removeItem('lastfm_selected_user');
                    }}

                    updateSelectedUserOption(user);
                    userModal.style.display = 'none';
                    renderStats(); // Re-renderizar con nuevo usuario
                }}
            }});

            return selectedUser;
        }}

        function updateSelectedUserOption(selectedUser) {{
            const userOptions = document.getElementById('userOptions');
            userOptions.querySelectorAll('.user-option').forEach(option => {{
                option.classList.remove('selected');
                if (option.dataset.user === selectedUser) {{
                    option.classList.add('selected');
                }}
            }});
        }}

        // Inicializar categorías activas
        let activeCategories = new Set(['artists']); // Por defecto mostrar artistas
        let selectedUser = '';

        document.getElementById('dateRange').textContent = `${{stats.from_date || ''}} → ${{stats.to_date || ''}}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles || 0;
        document.getElementById('generatedAt').textContent = stats.generated_at || '';

        // Manejar filtros de categorías
        const categoryFilters = document.querySelectorAll('.category-filter');
        categoryFilters.forEach(filter => {{
            filter.addEventListener('click', () => {{
                const category = filter.dataset.category;

                if (activeCategories.has(category)) {{
                    activeCategories.delete(category);
                    filter.classList.remove('active');
                }} else {{
                    activeCategories.add(category);
                    filter.classList.add('active');
                }}

                renderStats();
            }});
        }});

        function showArtistsPopup(itemName, category, user) {{
            const item = stats[category].find(item => item.name === itemName);
            if (!item || !item.user_artists || !item.user_artists[user]) return;

            const artists = item.user_artists[user];

            // Crear overlay
            const overlay = document.createElement('div');
            overlay.className = 'popup-overlay';

            // Crear popup
            const popup = document.createElement('div');
            popup.className = 'artists-popup';

            const header = document.createElement('div');
            header.className = 'popup-header';

            const closeBtn = document.createElement('button');
            closeBtn.className = 'popup-close';
            closeBtn.innerHTML = '×';
            closeBtn.onclick = () => {{
                document.body.removeChild(overlay);
                document.body.removeChild(popup);
            }};

            header.innerHTML = `Artistas de ${{user}} en "${{itemName}}"`;
            header.appendChild(closeBtn);

            const artistList = document.createElement('ul');
            artistList.className = 'artist-list';

            artists.forEach(artist => {{
                const li = document.createElement('li');
                li.textContent = artist;
                artistList.appendChild(li);
            }});

            popup.appendChild(header);
            popup.appendChild(artistList);

            // Cerrar al hacer click en overlay
            overlay.onclick = () => {{
                document.body.removeChild(overlay);
                document.body.removeChild(popup);
            }};

            document.body.appendChild(overlay);
            document.body.appendChild(popup);
        }}

        function createNoveltyItem(item, selectedUser) {{
            const itemDiv = document.createElement('div');
            itemDiv.className = 'item';

            if (selectedUser && item.users.includes(selectedUser)) {{
                itemDiv.classList.add('highlighted');
            }}

            const itemName = document.createElement('div');
            itemName.className = 'item-name';
            itemName.textContent = item.name;
            itemDiv.appendChild(itemName);

            const itemMeta = document.createElement('div');
            itemMeta.className = 'item-meta';

            // Conteo de plays si existe
            if (item.count) {{
                const countBadge = document.createElement('span');
                countBadge.className = 'badge';
                countBadge.textContent = `${{item.count}} plays`;
                itemMeta.appendChild(countBadge);
            }}

            // Fecha de primer scrobble
            const date = new Date(item.first_date * 1000);
            const dateBadge = document.createElement('span');
            dateBadge.className = 'badge';
            dateBadge.textContent = `Primera vez: ${{date.toLocaleDateString('es-ES')}}`;
            itemMeta.appendChild(dateBadge);

            // Usuarios que lo han escuchado
            item.users.forEach(user => {{
                const userBadge = document.createElement('span');
                userBadge.className = 'user-badge';
                if (user === selectedUser) {{
                    userBadge.classList.add('highlighted-user');
                }}
                userBadge.textContent = user;
                itemMeta.appendChild(userBadge);
            }});

            itemDiv.appendChild(itemMeta);
            return itemDiv;
        }}

        function createUserNoveltyItem(item, selectedUser) {{
            const itemDiv = document.createElement('div');
            itemDiv.className = 'item';
            itemDiv.classList.add('highlighted'); // Siempre resaltado para el usuario

            const itemName = document.createElement('div');
            itemName.className = 'item-name';
            itemName.textContent = item.name;
            itemDiv.appendChild(itemName);

            const itemMeta = document.createElement('div');
            itemMeta.className = 'item-meta';

            // Total de scrobbles del usuario para este elemento
            if (item.total_count) {{
                const totalBadge = document.createElement('span');
                totalBadge.className = 'badge';
                totalBadge.style.background = '#cba6f7';
                totalBadge.style.color = '#1e1e2e';
                totalBadge.textContent = `${{item.total_count}} total plays`;
                itemMeta.appendChild(totalBadge);
            }}

            // Scrobbles en este período
            if (item.period_count) {{
                const periodBadge = document.createElement('span');
                periodBadge.className = 'badge';
                periodBadge.textContent = `${{item.period_count}} plays período`;
                itemMeta.appendChild(periodBadge);
            }}

            // Fecha de primera vez del usuario (si está disponible)
            if (item.first_date || item.user_first_date) {{
                const date = new Date((item.first_date || item.user_first_date) * 1000);
                const dateBadge = document.createElement('span');
                dateBadge.className = 'badge';
                dateBadge.style.background = '#a6e3a1';
                dateBadge.style.color = '#1e1e2e';
                dateBadge.textContent = `Primera vez: ${{date.toLocaleDateString('es-ES')}}`;
                itemMeta.appendChild(dateBadge);
            }}

            // Usuarios que también lo escucharon (coincidencias)
            if (item.coincident_users && item.coincident_users.length > 0) {{
                item.coincident_users.forEach(user => {{
                    const userBadge = document.createElement('span');
                    userBadge.className = 'user-badge';
                    userBadge.textContent = user;
                    itemMeta.appendChild(userBadge);
                }});
            }}

            // Información de coincidencias
            if (item.num_coincidences) {{
                const coincidencesBadge = document.createElement('span');
                coincidencesBadge.className = 'badge';
                coincidencesBadge.style.background = '#f38ba8';
                coincidencesBadge.style.color = '#1e1e2e';
                coincidencesBadge.textContent = `${{item.num_coincidences}} coincidencias`;
                itemMeta.appendChild(coincidencesBadge);
            }}

            itemDiv.appendChild(itemMeta);
            return itemDiv;
        }}

        function renderStats() {{
            const container = document.getElementById('categoriesContainer');
            container.innerHTML = '';

            const categoryTitles = {{
                artists: 'Artistas Más Escuchados',
                tracks: 'Canciones Más Escuchadas',
                albums: 'Álbumes Más Escuchados',
                genres: 'Géneros Más Escuchados',
                labels: 'Sellos Más Escuchados',
                years: 'Años Más Escuchados',
                novelties: 'Novedades'
            }};

            let hasData = false;

            ['artists', 'tracks', 'albums', 'genres', 'labels', 'years', 'novelties'].forEach(categoryKey => {{
                if (!activeCategories.has(categoryKey)) return;

                // Manejo especial para novedades
                if (categoryKey === 'novelties') {{
                    if (!hasNovelties || !stats.novelties) return;

                    hasData = true;
                    const categoryDiv = document.createElement('div');
                    categoryDiv.className = 'category visible';
                    categoryDiv.dataset.category = categoryKey;

                    const title = document.createElement('h3');
                    title.textContent = categoryTitles[categoryKey];
                    categoryDiv.appendChild(title);

                    // NUEVOS PARA TODOS
                    const nuevosSection = document.createElement('div');
                    nuevosSection.className = 'novelty-section';

                    const nuevosTitle = document.createElement('h4');
                    nuevosTitle.textContent = '🆕 Nuevos para todos';
                    nuevosSection.appendChild(nuevosTitle);

                    ['artists', 'albums', 'tracks'].forEach(type => {{
                        const subsection = document.createElement('div');
                        subsection.className = 'novelty-subsection';

                        const subsectionTitle = document.createElement('h5');
                        subsectionTitle.textContent = type === 'artists' ? 'Artistas' :
                                                     type === 'albums' ? 'Álbumes' : 'Canciones';
                        subsection.appendChild(subsectionTitle);

                        const items = stats.novelties.nuevos[type];
                        if (items && items.length > 0) {{
                            items.forEach(item => {{
                                const itemDiv = createNoveltyItem(item, selectedUser);
                                subsection.appendChild(itemDiv);
                            }});
                        }} else {{
                            const emptyDiv = document.createElement('div');
                            emptyDiv.className = 'novelty-empty';
                            emptyDiv.textContent = 'No hay elementos nuevos';
                            subsection.appendChild(emptyDiv);
                        }}

                        nuevosSection.appendChild(subsection);
                    }});

                    categoryDiv.appendChild(nuevosSection);

                    // NUEVOS COMPARTIDOS
                    const compartidosSection = document.createElement('div');
                    compartidosSection.className = 'novelty-section';

                    const compartidosTitle = document.createElement('h4');
                    compartidosTitle.textContent = '👥 Nuevos compartidos (50%+ del grupo)';
                    compartidosSection.appendChild(compartidosTitle);

                    ['artists', 'albums', 'tracks'].forEach(type => {{
                        const subsection = document.createElement('div');
                        subsection.className = 'novelty-subsection';

                        const subsectionTitle = document.createElement('h5');
                        subsectionTitle.textContent = type === 'artists' ? 'Artistas' :
                                                     type === 'albums' ? 'Álbumes' : 'Canciones';
                        subsection.appendChild(subsectionTitle);

                        const items = stats.novelties.nuevos_compartidos[type];
                        if (items && items.length > 0) {{
                            items.forEach(item => {{
                                const itemDiv = createNoveltyItem(item, selectedUser);
                                subsection.appendChild(itemDiv);
                            }});
                        }} else {{
                            const emptyDiv = document.createElement('div');
                            emptyDiv.className = 'novelty-empty';
                            emptyDiv.textContent = 'No hay elementos nuevos compartidos';
                            subsection.appendChild(emptyDiv);
                        }}

                        compartidosSection.appendChild(subsection);
                    }});

                    // NUEVOS PARA USUARIO SELECCIONADO
                    if (selectedUser) {{
                        const usuarioSection = document.createElement('div');
                        usuarioSection.className = 'novelty-section';

                        const usuarioTitle = document.createElement('h4');
                        usuarioTitle.textContent = `👤 Nuevos para ${{selectedUser}} (ya conocidos por el grupo)`;
                        usuarioSection.appendChild(usuarioTitle);

                        // Calcular novedades para el usuario
                        const userNovelties = getUserNovelties(selectedUser);

                        ['artists', 'albums', 'tracks'].forEach(type => {{
                            const subsection = document.createElement('div');
                            subsection.className = 'novelty-subsection';

                            const subsectionTitle = document.createElement('h5');
                            subsectionTitle.textContent = type === 'artists' ? 'Artistas' :
                                                         type === 'albums' ? 'Álbumes' : 'Canciones';
                            subsection.appendChild(subsectionTitle);

                            const items = userNovelties[type];
                            if (items && items.length > 0) {{
                                items.forEach(item => {{
                                    const itemDiv = createUserNoveltyItem(item, selectedUser);
                                    subsection.appendChild(itemDiv);
                                }});
                            }} else {{
                                const emptyDiv = document.createElement('div');
                                emptyDiv.className = 'novelty-empty';
                                const typeText = type === 'artists' ? 'artistas' :
                                               type === 'albums' ? 'álbumes' : 'canciones';
                                emptyDiv.textContent = items ?
                                    `No hay ${{typeText}} nuevos para ${{selectedUser}} con coincidencias en el período` :
                                    'Calculando novedades del usuario...';
                                subsection.appendChild(emptyDiv);
                            }}

                            usuarioSection.appendChild(subsection);
                        }});

                        categoryDiv.appendChild(usuarioSection);
                    }} else {{
                        const usuarioSection = document.createElement('div');
                        usuarioSection.className = 'novelty-section';

                        const usuarioTitle = document.createElement('h4');
                        usuarioTitle.textContent = '👤 Nuevos para usuario específico';
                        usuarioSection.appendChild(usuarioTitle);

                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'novelty-empty';
                        infoDiv.textContent = 'Selecciona un usuario para ver sus novedades personales';
                        usuarioSection.appendChild(infoDiv);

                        categoryDiv.appendChild(usuarioSection);
                    }}
                    container.appendChild(categoryDiv);
                    return;
                }}

                if (!stats[categoryKey] || stats[categoryKey].length === 0) return;

                hasData = true;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category visible';
                categoryDiv.dataset.category = categoryKey;

                const title = document.createElement('h3');
                title.textContent = categoryTitles[categoryKey];
                categoryDiv.appendChild(title);

                stats[categoryKey].forEach(item => {{
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'item';

                    if (selectedUser && item.users.includes(selectedUser)) {{
                        itemDiv.classList.add('highlighted');
                    }}

                    // Hacer clickeable si es género, año o sello y hay usuario seleccionado
                    const isClickableForUser = ['genres', 'labels', 'years'].includes(categoryKey) &&
                                       selectedUser &&
                                       item.users.includes(selectedUser) &&
                                       item.user_artists &&
                                       item.user_artists[selectedUser];

                    // Hacer expandible si tiene información detallada
                    const isExpandable = ['genres', 'labels', 'years'].includes(categoryKey) &&
                                         ((item.top_artists && item.top_artists.length > 0) ||
                                          (item.top_albums && item.top_albums.length > 0));

                    const itemName = document.createElement('div');
                    itemName.className = 'item-name';
                    itemName.textContent = item.name;

                    if (isExpandable) {{
                        itemDiv.classList.add('expandable');
                    }}

                    itemDiv.appendChild(itemName);

                    const itemMeta = document.createElement('div');
                    itemMeta.className = 'item-meta';

                    const countBadge = document.createElement('span');
                    countBadge.className = 'badge';
                    countBadge.textContent = `${{item.count}} plays`;
                    itemMeta.appendChild(countBadge);

                    item.users.sort((a, b) => (item.user_counts[b] || 0) - (item.user_counts[a] || 0));

                    item.users.forEach(user => {{
                        const userBadge = document.createElement('span');
                        userBadge.className = 'user-badge';
                        if (user === selectedUser) {{
                            userBadge.classList.add('highlighted-user');
                        }}

                        const userScrobbles = item.user_counts[user] || 0;
                        userBadge.textContent = `${{user}} (${{userScrobbles}})`;

                        if (isClickableForUser && user === selectedUser) {{
                            userBadge.style.cursor = 'pointer';
                            userBadge.addEventListener('click', (e) => {{
                                e.stopPropagation();
                                showArtistsPopup(item.name, categoryKey, user);
                            }});
                        }}

                        itemMeta.appendChild(userBadge);
                    }});

                    itemDiv.appendChild(itemMeta);

                    // Detalles expandibles
                    if (isExpandable) {{
                        const detailsDiv = document.createElement('div');
                        detailsDiv.className = 'details';

                        if (item.top_artists && item.top_artists.length > 0) {{
                            const artistSection = document.createElement('div');
                            artistSection.className = 'detail-section';

                            const artistTitle = document.createElement('div');
                            artistTitle.className = 'detail-title';
                            artistTitle.textContent = 'Top Artistas:';
                            artistSection.appendChild(artistTitle);

                            const artistList = document.createElement('div');
                            artistList.className = 'detail-list';

                            item.top_artists.slice(0, 10).forEach(artist => {{
                                const artistItem = document.createElement('span');
                                artistItem.className = 'detail-item';
                                artistItem.textContent = artist;
                                artistList.appendChild(artistItem);
                            }});

                            artistSection.appendChild(artistList);
                            detailsDiv.appendChild(artistSection);
                        }}

                        if (item.top_albums && item.top_albums.length > 0) {{
                            const albumSection = document.createElement('div');
                            albumSection.className = 'detail-section';

                            const albumTitle = document.createElement('div');
                            albumTitle.className = 'detail-title';
                            albumTitle.textContent = 'Top Álbumes:';
                            albumSection.appendChild(albumTitle);

                            const albumList = document.createElement('div');
                            albumList.className = 'detail-list';

                            item.top_albums.slice(0, 10).forEach(album => {{
                                const albumItem = document.createElement('span');
                                albumItem.className = 'detail-item';
                                albumItem.textContent = album;
                                albumList.appendChild(albumItem);
                            }});

                            albumSection.appendChild(albumList);
                            detailsDiv.appendChild(albumSection);
                        }}

                        itemDiv.appendChild(detailsDiv);

                        itemDiv.addEventListener('click', (e) => {{
                            if (e.target.classList.contains('user-badge') && e.target.style.cursor === 'pointer') {{
                                return;
                            }}

                            itemDiv.classList.toggle('expanded');
                            detailsDiv.classList.toggle('expanded');
                        }});
                    }}

                    categoryDiv.appendChild(itemDiv);
                }});

                container.appendChild(categoryDiv);
            }});

            if (!hasData) {{
                const noDataDiv = document.createElement('div');
                noDataDiv.className = 'no-data';
                noDataDiv.textContent = 'No hay datos para mostrar con los filtros seleccionados.';
                container.appendChild(noDataDiv);
            }}
        }}

        // Inicialización
        document.addEventListener('DOMContentLoaded', function() {{
            selectedUser = initializeUserSelector();
            renderStats();
        }});
    </script>
</body>
</html>"""
