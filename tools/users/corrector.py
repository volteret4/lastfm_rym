#!/usr/bin/env python3
"""
Script corrector DEFINITIVO para user_stats_html_generator.py

Este script corrige el f-string gigante (líneas 34-2519) que contiene:
- CSS con miles de llaves {}
- JavaScript con template literals ${...}
- Algunos ${...} mal escritos como $${...} o $$${...}
- Emojis corruptos en líneas 2468 y 2474

Estrategia:
1. Encontrar y proteger todas las expresiones ${...} (con llaves anidadas)
2. Limpiar los $ extra ($${ → ${)
3. Escapar todas las llaves restantes ({ → {{, } → }})
4. Restaurar las expresiones ${...}
5. Corregir emojis corruptos
"""

import sys

def find_template_literals(line):
    """
    Encuentra todas las expresiones ${...} en una línea, incluso con llaves anidadas.
    Retorna lista de (start_pos, end_pos, contenido_completo)
    """
    results = []
    i = 0

    while i < len(line):
        # Buscar inicio de expresión
        if i < len(line) - 1 and line[i] == '$' and line[i+1] == '{':
            # Contar $ consecutivos
            dollar_count = 0
            j = i
            while j >= 0 and line[j] == '$':
                dollar_count += 1
                j -= 1

            start = i - dollar_count + 1
            i += 2  # Saltar ${

            # Encontrar la } que cierra, contando anidamiento
            brace_count = 1
            while i < len(line) and brace_count > 0:
                if line[i] == '{':
                    brace_count += 1
                elif line[i] == '}':
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                end = i
                results.append((start, end, line[start:end]))
        else:
            i += 1

    return results

def fix_html_generator(input_file, output_file):
    """Aplica todas las correcciones necesarias"""

    print("🔧 CORRECTOR DEFINITIVO - user_stats_html_generator.py")
    print("="*70)
    print(f"📖 Leyendo: {input_file}\n")

    with open(input_file, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    total_changes = 0
    fstring_start = 33  # línea 34
    fstring_end = 2518  # línea 2519

    # ============================================================
    # PASO 1: Procesar f-string (escapar llaves + limpiar $)
    # ============================================================
    print("🔧 PASO 1: Procesando f-string (CSS/JS + template literals)...")
    paso1_changes = 0

    for i in range(fstring_start + 1, fstring_end):
        original = lines[i]

        # Encontrar todas las expresiones ${...}
        template_literals = find_template_literals(original)

        if not template_literals:
            # Sin template literals, solo escapar llaves
            modified = original.replace('{', '{{').replace('}', '}}')
        else:
            # Construir línea nueva con protección de template literals
            modified = ""
            last_pos = 0

            for start, end, literal in template_literals:
                # Agregar parte antes del literal (escapar llaves)
                before = original[last_pos:start]
                modified += before.replace('{', '{{').replace('}', '}}')

                # Agregar literal limpiado (quitar $ extra)
                clean_literal = literal
                # Reemplazar múltiples $ por uno solo
                while '$$' in clean_literal:
                    clean_literal = clean_literal.replace('$$', '$')
                modified += clean_literal

                last_pos = end

            # Agregar parte final (escapar llaves)
            after = original[last_pos:]
            modified += after.replace('{', '{{').replace('}', '}}')

        if modified != original:
            lines[i] = modified
            paso1_changes += 1

    print(f"   ✅ Procesadas {paso1_changes} líneas")
    total_changes += paso1_changes

    # ============================================================
    # PASO 2: Corregir emojis corruptos
    # ============================================================
    print("\n🔧 PASO 2: Corrigiendo emojis corruptos...")
    paso2_changes = 0

    emoji_fixes = [
        (2467, '                            🎵 ${item.track}\n'),
        (2473, '                            💿 ${item.album}\n')
    ]

    for line_idx, new_content in emoji_fixes:
        if line_idx < len(lines) and 'ðŸ' in lines[line_idx]:
            lines[line_idx] = new_content
            paso2_changes += 1

    print(f"   ✅ Corregidos {paso2_changes} emojis")
    total_changes += paso2_changes

    # ============================================================
    # GUARDAR Y VERIFICAR
    # ============================================================
    print(f"\n💾 Guardando archivo...")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"✅ Guardado: {output_file}")

    # Verificar sintaxis
    print(f"\n🧪 Verificando sintaxis...")
    import py_compile
    try:
        py_compile.compile(output_file, doraise=True)
        print("✅ ¡Sintaxis correcta!")
        success = True
    except SyntaxError as e:
        print(f"❌ Error en línea {e.lineno}: {e.msg}")
        if e.text:
            print(f"   {e.text.strip()}")
        # Mostrar contexto
        print(f"\n📄 Contexto (líneas {e.lineno-2} a {e.lineno+2}):")
        for j in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            prefix = ">>>" if j == e.lineno-1 else "   "
            print(f"{prefix} {j+1:4d}: {lines[j].rstrip()}")
        success = False

    # Resumen
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    print(f"Paso 1: {paso1_changes} líneas procesadas (llaves+template literals)")
    print(f"Paso 2: {paso2_changes} emojis corregidos")
    print(f"Total:  {total_changes} cambios")
    print(f"\n{'✅ ÉXITO - Archivo listo para usar' if success else '❌ ERROR - Revisar sintaxis'}")

    return success

def main():
    input_file = "user_stats_html_generator.py"
    output_file = "user_stats_html_generator_fixed.py"

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    success = fix_html_generator(input_file, output_file)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
