#!/usr/bin/env python3
"""
Corrector DEFINITIVO para el error de sintaxis JavaScript
Corrige la línea 1421 que tiene:
1. Variable incorrecta: 'label' en lugar de 'genre'
2. Exceso de signos de dólar: $$$$$$ en lugar de $$$$
"""

import sys

def fix_syntax_error(input_file, output_file):
    """Corrige el error de sintaxis en la línea 1421"""

    print("🔧 CORRECTOR DEFINITIVO - Error de Sintaxis JavaScript")
    print("="*70)
    print(f"Entrada:  {input_file}")
    print(f"Salida:   {output_file}\n")

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    changes = []

    # CORRECCIÓN 1: Línea 1421 - Variable incorrecta y $ extra
    if len(lines) > 1420:
        original = lines[1420]  # índice 1420 = línea 1421

        if 'labelScatterChart_$$$$$${{label.replace' in original:
            print("🐛 PROBLEMA ENCONTRADO en línea 1421:")
            print(f"   {original.strip()}\n")

            # Corrección: label → genre, $$$$$$ → $$$$
            new_line = original.replace(
                'labelScatterChart_$$$$$${{label.replace',
                'genreScatterChart_$$$${{genre.replace'
            )

            if new_line != original:
                lines[1420] = new_line
                changes.append({
                    'line': 1421,
                    'before': original.strip(),
                    'after': new_line.strip(),
                    'issues': [
                        'Variable incorrecta: label → genre',
                        'Exceso de $: $$$$$$ → $$$$',
                        'Nombre incorrecto: labelScatterChart → genreScatterChart'
                    ]
                })

    # CORRECCIÓN 2: Verificar línea 1590 (contexto de labels, debería estar OK)
    if len(lines) > 1589:
        line_1590 = lines[1589]
        if 'labelScatterChart_$$$${{label.replace' in line_1590:
            print("✅ Línea 1590 correcta (contexto de labels)")

    # CORRECCIÓN 3: Línea 1747 - Verificar contexto de géneros
    if len(lines) > 1746:
        line_1747 = lines[1746]
        if 'scatterChart_$$$${{genre.replace' in line_1747:
            print("✅ Línea 1747 correcta (contexto de géneros)")

    if changes:
        print("\n✅ CORRECCIONES APLICADAS:")
        print("="*70)

        for change in changes:
            print(f"\n📍 Línea {change['line']}:")
            print(f"   Problemas detectados:")
            for issue in change['issues']:
                print(f"      • {issue}")
            print(f"\n   Antes:")
            print(f"      {change['before']}")
            print(f"\n   Después:")
            print(f"      {change['after']}")

        # Guardar archivo corregido
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        print("\n" + "="*70)
        print("💾 ARCHIVO GUARDADO")
        print("="*70)
        print(f"📁 {output_file}")

        # Verificar sintaxis Python
        print("\n🧪 Verificando sintaxis Python...")
        import py_compile
        try:
            py_compile.compile(output_file, doraise=True)
            print("✅ Sintaxis Python correcta")
        except SyntaxError as e:
            print(f"❌ Error de sintaxis Python: {e}")
            return False

        print("\n" + "="*70)
        print("✅ CORRECCIÓN COMPLETADA")
        print("="*70)
        print("\nEl problema era:")
        print("  1. Línea 1421 usaba variable 'label' en contexto de 'genre'")
        print("  2. Tenía 6 signos de dólar ($$$$$$$) en lugar de 4 ($$$$)")
        print("  3. Esto causaba que JavaScript intentara interpolar una variable indefinida")
        print("\nEfecto:")
        print("  • JavaScript generaba: label.replace(...) donde 'label' no existe")
        print("  • Esto causaba: 'missing ) after argument list'")
        print("\nSolución aplicada:")
        print("  • Cambiado 'label' a 'genre'")
        print("  • Corregido $$$$$$ a $$$$")
        print("  • Renombrado canvas ID a 'genreScatterChart'")

        return True
    else:
        print("ℹ️  No se encontraron problemas para corregir")
        return False

def main():
    input_file = "tools/users/user_stats_html_generator.py"
    output_file = "tools/users/user_stats_html_generator_final.py"

    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    success = fix_syntax_error(input_file, output_file)

    if success:
        print("\n💡 PRÓXIMOS PASOS:")
        print("="*70)
        print("1. Copia el archivo corregido a tu ubicación:")
        print(f"   cp {output_file} tools/users/user_stats_html_generator.py")
        print("\n2. Regenera el HTML:")
        print("   python3 html_usuarios.py --years-back 5")
        print("\n3. Abre en el navegador y verifica:")
        print("   • F12 → Console")
        print("   • No debe haber error de sintaxis")
        print("   • Los gráficos deben aparecer")

        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
