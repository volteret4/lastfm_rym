#!/usr/bin/env python3
"""Script para corregir el problema de inicialización en temp_html_generator.py"""

import re

# Leer el archivo original
with open('temp_html_generator.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("Leyendo archivo...")
print(f"Longitud total: {len(content)} caracteres")

# Paso 1: Encontrar y eliminar las líneas problemáticas (783-803)
# Estas son las líneas que acceden al DOM fuera de DOMContentLoaded

pattern1 = r"(        // Inicializar categorías activas\n        let activeCategories = new Set\(\['artists'\]\); // Por defecto mostrar artistas\n        let selectedUser = '';)\n\n        document\.getElementById\('dateRange'\)\.textContent = [^\n]+\n        document\.getElementById\('totalScrobbles'\)\.textContent = [^\n]+\n        document\.getElementById\('generatedAt'\)\.textContent = [^\n]+\n\n        // Manejar filtros de categorías\n        const categoryFilters = document\.querySelectorAll\('\.category-filter'\);\n        categoryFilters\.forEach\(filter => \{\{\n(?:.*\n){15}        \}\}\);"

replacement1 = r"\1"

content_new, count1 = re.subn(pattern1, replacement1, content, flags=re.DOTALL)

if count1 > 0:
    print(f"✓ Eliminadas {count1} secciones problemáticas")
else:
    print("✗ No se encontró la sección problemática con regex")
    print("  Intentando búsqueda más simple...")

    # Búsqueda más simple línea por línea
    lines = content.split('\n')
    new_lines = []
    skip_until = -1

    for i, line in enumerate(lines):
        if skip_until > i:
            continue

        # Detectar inicio de la sección a eliminar
        if i < len(lines) - 1 and "getElementById('dateRange')" in line:
            print(f"  Encontrada línea problemática en {i+1}")
            # Saltar hasta encontrar el cierre de los event listeners
            skip_until = i + 1
            while skip_until < len(lines):
                if "function showArtistsPopup" in lines[skip_until]:
                    break
                skip_until += 1
            print(f"  Saltando hasta línea {skip_until+1}")
            continue

        new_lines.append(line)

    content_new = '\n'.join(new_lines)
    print("✓ Sección eliminada con método línea por línea")

# Paso 2: Añadir el código de inicialización dentro de DOMContentLoaded
pattern2 = r"(        // Inicialización\n        document\.addEventListener\('DOMContentLoaded', function\(\) \{\{)\n(            selectedUser = initializeUserSelector\(\);\n            renderStats\(\);\n        \}\}\);)"

replacement2 = r"""\1
            // Inicializar elementos del DOM
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

\2"""

content_final, count2 = re.subn(pattern2, replacement2, content_new, flags=re.DOTALL)

if count2 > 0:
    print(f"✓ Actualizado {count2} DOMContentLoaded")
else:
    print("✗ No se encontró el DOMContentLoaded con regex")
    print("  Intentando búsqueda manual...")

    # Búsqueda manual del DOMContentLoaded
    dom_pattern = "document.addEventListener('DOMContentLoaded', function() {{"
    if dom_pattern in content_new:
        idx = content_new.find(dom_pattern)
        # Encontrar el final del function() {{
        idx_start = idx + len(dom_pattern)

        # Buscar las líneas actuales
        idx_selected = content_new.find("selectedUser = initializeUserSelector();", idx_start)

        if idx_selected != -1:
            # Insertar el nuevo código antes de selectedUser
            new_code = """
            // Inicializar elementos del DOM
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

"""
            content_final = content_new[:idx_selected] + new_code + content_new[idx_selected:]
            print("✓ DOMContentLoaded actualizado manualmente")
        else:
            print("✗ No se encontró selectedUser dentro de DOMContentLoaded")
            content_final = content_new
    else:
        print("✗ No se encontró addEventListener('DOMContentLoaded'")
        content_final = content_new

# Guardar el archivo corregido
output_path = 'temp_html_generator_fixed.py'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(content_final)

print(f"\n✓ Archivo guardado en: {output_path}")
print(f"  Longitud final: {len(content_final)} caracteres")
print(f"  Cambio: {len(content_final) - len(content):+d} caracteres")
