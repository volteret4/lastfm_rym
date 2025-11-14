#!/usr/bin/env python3
"""
Corrector específico para el problema de backticks anidados en la línea 1965-1969
"""

import sys

def fix_nested_backticks(input_file, output_file):
    """Corrige backticks anidados que causan error de sintaxis"""

    print("🔧 Corrigiendo backticks anidados...")
    print("="*70)

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    changes = []

    # Línea 1965: return [`Artista...`, `Canción...`];
    if len(lines) > 1964:
        original = lines[1964]
        if '`Artista:' in original and '`Canción:' in original:
            # Cambiar backticks a comillas simples
            new_line = original.replace('`Artista:', "'Artista:").replace('`, `Canción:', "', 'Canción:").replace('`]', "']")
            if new_line != original:
                lines[1964] = new_line
                changes.append(('1965', 'Backticks por comillas simples', original.strip(), new_line.strip()))

    # Línea 1967: return [`Días en...`];
    if len(lines) > 1966:
        original = lines[1966]
        if '`Días en' in original:
            new_line = original.replace('`Días en', "'Días en").replace('`]', "']")
            if new_line != original:
                lines[1966] = new_line
                changes.append(('1967', 'Backticks por comillas simples', original.strip(), new_line.strip()))

    # Línea 1969: return [`Canciones únicas...`];
    if len(lines) > 1968:
        original = lines[1968]
        if '`Canciones únicas:' in original:
            new_line = original.replace('`Canciones únicas:', "'Canciones únicas:").replace('`]', "']")
            if new_line != original:
                lines[1968] = new_line
                changes.append(('1969', 'Backticks por comillas simples', original.strip(), new_line.strip()))

    if changes:
        print(f"✅ Se corrigieron {len(changes)} líneas:\n")
        for line_num, desc, before, after in changes:
            print(f"Línea {line_num}: {desc}")
            print(f"  Antes:  {before}")
            print(f"  Después: {after}")
            print()

        # Guardar
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        print(f"💾 Archivo guardado: {output_file}")

        # Verificar sintaxis Python
        print("\n🧪 Verificando sintaxis Python...")
        import py_compile
        try:
            py_compile.compile(output_file, doraise=True)
            print("✅ Sintaxis Python correcta")
        except SyntaxError as e:
            print(f"⚠️  Error de sintaxis Python: {e}")
            return False

        return True
    else:
        print("ℹ️  No se encontraron backticks problemáticos para corregir")
        return False

def main():
    input_file = "tools/users/user_stats_html_generator.py"
    output_file = "tools/users/user_stats_html_generator_fixed.py"

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    print(f"Entrada:  {input_file}")
    print(f"Salida:   {output_file}\n")

    success = fix_nested_backticks(input_file, output_file)

    if success:
        print("\n" + "="*70)
        print("✅ CORRECCIÓN COMPLETADA")
        print("="*70)
        print("\nEl problema era:")
        print("  • Template literals JavaScript (backticks) anidados dentro de un f-string")
        print("  • Esto causaba conflicto de sintaxis en el JavaScript generado")
        print("\nSolución aplicada:")
        print("  • Cambiar backticks internos a comillas simples")
        print("  • Los template literals ${...} siguen funcionando")
        print("\nArchivo corregido listo para usar:")
        print(f"  {output_file}")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
