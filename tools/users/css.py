#!/usr/bin/env python3
"""
Script para corregir las llaves del CSS en el f-string
"""

def fix_css_braces():
    """Corrige las llaves del CSS dentro del f-string"""

    with open('user_stats_html_generator.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Encontrar las secciones de CSS dentro del f-string
    style_start = content.find('<style>')
    style_end = content.find('</style>')

    if style_start == -1 or style_end == -1:
        print("❌ No se encontraron las etiquetas <style>")
        return

    # Extraer las tres partes
    before_style = content[:style_start]
    style_content = content[style_start:style_end + len('</style>')]
    after_style = content[style_end + len('</style>'):]

    # En la sección de CSS, todas las llaves deben ser dobles para el f-string
    style_lines = style_content.split('\n')
    corrected_style_lines = []

    for line in style_lines:
        if '<style>' in line or '</style>' in line:
            corrected_style_lines.append(line)
            continue

        # Si la línea contiene CSS (tiene : o ;), necesita llaves dobles
        if ':' in line or ';' in line or line.strip().endswith('{') or line.strip() == '}':
            # Reemplazar { por {{ y } por }}
            line = line.replace('{', '{{').replace('}', '}}')

        corrected_style_lines.append(line)

    style_content = '\n'.join(corrected_style_lines)

    # Reconstruir el archivo
    content = before_style + style_content + after_style

    # Escribir el archivo
    with open('user_stats_html_generator_fixed.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ CSS corregido para f-string")

    # Verificar sintaxis
    try:
        with open('user_stats_html_generator.py', 'r') as f:
            code = f.read()
        compile(code, 'user_stats_html_generator_fixed.py', 'exec')
        print("✅ Sintaxis Python válida")
    except SyntaxError as e:
        print(f"❌ Error de sintaxis en línea {e.lineno}: {e.text}")
        print(f"   Error: {e.msg}")

if __name__ == "__main__":
    fix_css_braces()
