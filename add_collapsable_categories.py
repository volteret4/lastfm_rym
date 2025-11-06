#!/usr/bin/env python3
"""
Add Category Filters to Existing HTML Stats
Añade filtros de categoría desplegables a html_mensual.py y html_anual.py
"""

import sys

def update_html_mensual():
    """Actualiza html_mensual.py para añadir categorías desplegables"""

    print("📝 Actualizando html_mensual.py...")

    try:
        with open('html_mensual.py', 'r', encoding='utf-8') as f:
            content = f.read()

        # Buscar y reemplazar secciones específicas

        # 1. Actualizar estilos de controls
        old_controls_css = """        .controls {
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
        }

        .control-group {
            display: flex;
            gap: 15px;
            align-items: center;
        }"""

        new_controls_css = """        .controls {
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }

        .control-group {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .category-filters {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .category-filter {
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }

        .category-filter:hover {
            border-color: #cba6f7;
            background: #45475a;
        }

        .category-filter.active {
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }"""

        content = content.replace(old_controls_css, new_controls_css)

        # 2. Actualizar estilos de category
        old_category_css = """        .category {
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }"""

        new_category_css = """        .category {
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
            display: none;
        }

        .category.visible {
            display: block;
        }"""

        content = content.replace(old_category_css, new_category_css)

        # 3. Actualizar media query
        old_media = """        @media (max-width: 768px) {
            .categories {
                grid-template-columns: 1fr;
            }
        }"""

        new_media = """        @media (max-width: 768px) {
            .categories {
                grid-template-columns: 1fr;
            }

            .controls {
                flex-direction: column;
                align-items: stretch;
            }

            .category-filters {
                justify-content: center;
            }
        }"""

        content = content.replace(old_media, new_media)

        # 4. Actualizar HTML de controls
        old_controls_html = """        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Destacar usuario:</label>
                <select id="userSelect">
                    <option value="">Ninguno</option>
                </select>
            </div>
        </div>"""

        new_controls_html = """        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Destacar usuario:</label>
                <select id="userSelect">
                    <option value="">Ninguno</option>
                </select>
            </div>

            <div class="control-group">
                <label>Mostrar categorías:</label>
                <div class="category-filters">
                    <button class="category-filter active" data-category="artists">Artistas</button>
                    <button class="category-filter" data-category="tracks">Canciones</button>
                    <button class="category-filter" data-category="albums">Álbumes</button>
                    <button class="category-filter" data-category="genres">Géneros</button>
                    <button class="category-filter" data-category="labels">Sellos</button>
                </div>
            </div>
        </div>"""

        content = content.replace(old_controls_html, new_controls_html)

        # 5. Actualizar JavaScript
        old_js_start = """        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        });

        document.getElementById('dateRange').textContent = `${stats.from_date} → ${stats.to_date}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles;
        document.getElementById('generatedAt').textContent = stats.generated_at;

        function renderStats() {"""

        new_js_start = """        let activeCategories = new Set(['artists']); // Por defecto mostrar artistas

        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        });

        document.getElementById('dateRange').textContent = `${stats.from_date} → ${stats.to_date}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles;
        document.getElementById('generatedAt').textContent = stats.generated_at;

        // Manejar filtros de categorías
        const categoryFilters = document.querySelectorAll('.category-filter');
        categoryFilters.forEach(filter => {
            filter.addEventListener('click', () => {
                const category = filter.dataset.category;

                if (activeCategories.has(category)) {
                    activeCategories.delete(category);
                    filter.classList.remove('active');
                } else {
                    activeCategories.add(category);
                    filter.classList.add('active');
                }

                renderStats();
            });
        });

        function renderStats() {"""

        content = content.replace(old_js_start, new_js_start)

        # 6. Actualizar creación de categoryDiv
        old_category_div = """                hasData = true;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category';

                const title = document.createElement('h3');"""

        new_category_div = """                hasData = true;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category';
                categoryDiv.dataset.category = categoryKey;

                // Mostrar u ocultar según filtros activos
                if (activeCategories.has(categoryKey)) {
                    categoryDiv.classList.add('visible');
                }

                const title = document.createElement('h3');"""

        content = content.replace(old_category_div, new_category_div)

        # 7. Actualizar mensaje de no data
        old_no_data = """            if (!hasData) {
                const noData = document.createElement('div');
                noData.className = 'no-data';
                noData.textContent = 'No hay coincidencias para este período';
                container.appendChild(noData);
            }"""

        new_no_data = """            if (!hasData || activeCategories.size === 0) {
                const noData = document.createElement('div');
                noData.className = 'no-data';
                noData.textContent = activeCategories.size === 0
                    ? 'Selecciona al menos una categoría para ver las estadísticas'
                    : 'No hay coincidencias para este período';
                container.appendChild(noData);
            }"""

        content = content.replace(old_no_data, new_no_data)

        # Guardar archivo actualizado
        with open('html_mensual.py', 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ html_mensual.py actualizado correctamente")
        return True

    except Exception as e:
        print(f"❌ Error actualizando html_mensual.py: {e}")
        return False


def update_html_anual():
    """Actualiza html_anual.py para añadir categorías desplegables"""

    print("\n📝 Actualizando html_anual.py...")

    try:
        with open('html_anual.py', 'r', encoding='utf-8') as f:
            content = f.read()

        # Aplicar los mismos cambios que a html_mensual.py

        # 1. Estilos de controls
        old_controls_css = """        .controls {
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
        }

        .control-group {
            display: flex;
            gap: 15px;
            align-items: center;
        }"""

        new_controls_css = """        .controls {
            padding: 20px 30px;
            background: #1e1e2e;
            border-bottom: 1px solid #313244;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            align-items: center;
        }

        .control-group {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .category-filters {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        .category-filter {
            padding: 8px 16px;
            background: #313244;
            color: #cdd6f4;
            border: 2px solid #45475a;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-size: 0.9em;
            font-weight: 600;
        }

        .category-filter:hover {
            border-color: #cba6f7;
            background: #45475a;
        }

        .category-filter.active {
            background: #cba6f7;
            color: #1e1e2e;
            border-color: #cba6f7;
        }"""

        content = content.replace(old_controls_css, new_controls_css)

        # 2. Estilos de category
        old_category_css = """        .category {
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
        }"""

        new_category_css = """        .category {
            background: #1e1e2e;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #313244;
            display: none;
        }

        .category.visible {
            display: block;
        }"""

        content = content.replace(old_category_css, new_category_css)

        # 3. Media query
        old_media = """        @media (max-width: 768px) {
            .categories {
                grid-template-columns: 1fr;
            }
        }"""

        new_media = """        @media (max-width: 768px) {
            .categories {
                grid-template-columns: 1fr;
            }

            .controls {
                flex-direction: column;
                align-items: stretch;
            }

            .category-filters {
                justify-content: center;
            }
        }"""

        content = content.replace(old_media, new_media)

        # 4. HTML de controls
        old_controls_html = """        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Destacar usuario:</label>
                <select id="userSelect">
                    <option value="">Ninguno</option>
                </select>
            </div>
        </div>"""

        new_controls_html = """        <div class="controls">
            <div class="control-group">
                <label for="userSelect">Destacar usuario:</label>
                <select id="userSelect">
                    <option value="">Ninguno</option>
                </select>
            </div>

            <div class="control-group">
                <label>Mostrar categorías:</label>
                <div class="category-filters">
                    <button class="category-filter active" data-category="artists">Artistas</button>
                    <button class="category-filter" data-category="tracks">Canciones</button>
                    <button class="category-filter" data-category="albums">Álbumes</button>
                    <button class="category-filter" data-category="genres">Géneros</button>
                    <button class="category-filter" data-category="labels">Sellos</button>
                </div>
            </div>
        </div>"""

        content = content.replace(old_controls_html, new_controls_html)

        # 5. JavaScript
        old_js_start = """        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        });

        document.getElementById('dateRange').textContent = `${stats.from_date} → ${stats.to_date}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles;
        document.getElementById('generatedAt').textContent = stats.generated_at;

        function renderStats() {"""

        new_js_start = """        let activeCategories = new Set(['artists']); // Por defecto mostrar artistas

        const userSelect = document.getElementById('userSelect');
        users.forEach(user => {
            const option = document.createElement('option');
            option.value = user;
            option.textContent = user;
            userSelect.appendChild(option);
        });

        document.getElementById('dateRange').textContent = `${stats.from_date} → ${stats.to_date}`;
        document.getElementById('totalScrobbles').textContent = stats.total_scrobbles;
        document.getElementById('generatedAt').textContent = stats.generated_at;

        // Manejar filtros de categorías
        const categoryFilters = document.querySelectorAll('.category-filter');
        categoryFilters.forEach(filter => {
            filter.addEventListener('click', () => {
                const category = filter.dataset.category;

                if (activeCategories.has(category)) {
                    activeCategories.delete(category);
                    filter.classList.remove('active');
                } else {
                    activeCategories.add(category);
                    filter.classList.add('active');
                }

                renderStats();
            });
        });

        function renderStats() {"""

        content = content.replace(old_js_start, new_js_start)

        # 6. Creación de categoryDiv
        old_category_div = """                hasData = true;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category';

                const title = document.createElement('h3');"""

        new_category_div = """                hasData = true;
                const categoryDiv = document.createElement('div');
                categoryDiv.className = 'category';
                categoryDiv.dataset.category = categoryKey;

                // Mostrar u ocultar según filtros activos
                if (activeCategories.has(categoryKey)) {
                    categoryDiv.classList.add('visible');
                }

                const title = document.createElement('h3');"""

        content = content.replace(old_category_div, new_category_div)

        # 7. Mensaje de no data
        old_no_data = """            if (!hasData) {
                const noData = document.createElement('div');
                noData.className = 'no-data';
                noData.textContent = 'No hay coincidencias para este período';
                container.appendChild(noData);
            }"""

        new_no_data = """            if (!hasData || activeCategories.size === 0) {
                const noData = document.createElement('div');
                noData.className = 'no-data';
                noData.textContent = activeCategories.size === 0
                    ? 'Selecciona al menos una categoría para ver las estadísticas'
                    : 'No hay coincidencias para este período';
                container.appendChild(noData);
            }"""

        content = content.replace(old_no_data, new_no_data)

        # Guardar archivo actualizado
        with open('html_anual.py', 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ html_anual.py actualizado correctamente")
        return True

    except Exception as e:
        print(f"❌ Error actualizando html_anual.py: {e}")
        return False


def main():
    print("=" * 60)
    print("🔧 AÑADIENDO CATEGORÍAS DESPLEGABLES A LOS SCRIPTS")
    print("=" * 60)
    print()
    print("Este script modificará:")
    print("  - html_mensual.py")
    print("  - html_anual.py")
    print()
    print("Para añadir botones de filtrado por categorías")
    print()

    # Confirmar
    response = input("¿Continuar? (s/N): ")
    if response.lower() != 's':
        print("Operación cancelada")
        sys.exit(0)

    print()

    success_mensual = update_html_mensual()
    success_anual = update_html_anual()

    print()
    print("=" * 60)

    if success_mensual and success_anual:
        print("✅ ACTUALIZACIÓN COMPLETADA")
        print()
        print("Ahora puedes generar estadísticas con categorías desplegables:")
        print("  python3 html_mensual.py")
        print("  python3 html_anual.py")
        print("  python3 html_semanal.py")
    else:
        print("⚠️  ACTUALIZACIÓN PARCIAL")
        print("Revisa los errores anteriores")

    print("=" * 60)


if __name__ == '__main__':
    main()
