#!/usr/bin/env python3
"""
Descargador de Umami Analytics
Descarga el script de Umami y lo sirve localmente para evitar bloqueos
"""

import os
import requests
import hashlib
import json
from datetime import datetime
from pathlib import Path

def download_umami_script(script_url, output_dir="docs/js"):
    """
    Descarga el script de Umami Analytics y lo guarda localmente
    """
    print(f"📥 Descargando script de Umami desde: {script_url}")

    # Crear directorio si no existe
    os.makedirs(output_dir, exist_ok=True)

    try:
        # Descargar el script
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(script_url, headers=headers, timeout=30)
        response.raise_for_status()

        script_content = response.text

        # Verificar que el contenido parece ser un script válido de Umami
        if 'umami' not in script_content.lower():
            print("⚠️  El script descargado no parece ser de Umami")
            return None

        # Generar hash para verificar cambios
        script_hash = hashlib.sha256(script_content.encode()).hexdigest()[:8]

        # Guardar el script
        script_filename = f"umami-{script_hash}.js"
        script_path = os.path.join(output_dir, script_filename)

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        # Crear también una copia con nombre fijo para facilitar referencias
        main_script_path = os.path.join(output_dir, "umami.js")
        with open(main_script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        # Guardar metadatos
        metadata = {
            'download_date': datetime.now().isoformat(),
            'source_url': script_url,
            'hash': script_hash,
            'filename': script_filename,
            'size': len(script_content)
        }

        metadata_path = os.path.join(output_dir, "umami-metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Script descargado: {script_path}")
        print(f"✅ Enlace principal: {main_script_path}")
        print(f"📊 Tamaño: {len(script_content)} bytes")
        print(f"🔒 Hash: {script_hash}")

        return {
            'local_path': "js/umami.js",  # Ruta relativa desde la raíz web (GitHub Pages sirve docs/ como /)
            'full_path': main_script_path,
            'hash': script_hash,
            'size': len(script_content)
        }

    except requests.RequestException as e:
        print(f"❌ Error al descargar el script: {e}")
        return None
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return None

def check_script_updates(script_url, current_hash, output_dir="docs/js"):
    """
    Verifica si hay actualizaciones disponibles del script
    """
    try:
        print("🔍 Verificando actualizaciones del script...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.head(script_url, headers=headers, timeout=10)
        response.raise_for_status()

        # Si no hay información de ETag o Last-Modified, descargar para comparar
        response = requests.get(script_url, headers=headers, timeout=30)
        script_content = response.text
        new_hash = hashlib.sha256(script_content.encode()).hexdigest()[:8]

        if new_hash != current_hash:
            print(f"🆕 Nueva versión disponible (hash: {new_hash})")
            return True
        else:
            print("✅ Script actualizado")
            return False

    except Exception as e:
        print(f"⚠️  No se pudo verificar actualizaciones: {e}")
        return False

def get_local_script_info(output_dir="docs/js"):
    """
    Obtiene información del script local si existe
    """
    metadata_path = os.path.join(output_dir, "umami-metadata.json")
    script_path = os.path.join(output_dir, "umami.js")

    if os.path.exists(metadata_path) and os.path.exists(script_path):
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            return metadata
        except:
            return None
    return None

def create_privacy_compliant_script(website_id, local_script_path="js/umami.js"):
    """
    Genera el código HTML para cargar el script local con configuración de privacidad
    """
    script_html = f"""
        <!-- Umami Analytics (Local) -->
        <script>
            // Configuración de privacidad mejorada
            window.umamiConfig = {{
                websiteId: '{website_id}',
                respectDNT: true,
                autoTrack: true,
                enableLocalStorage: false,  // No usar localStorage para mayor privacidad
                domains: [window.location.hostname]
            }};
        </script>
        <script async src="{local_script_path}"
                data-website-id="{website_id}"
                data-auto-track="true"
                data-do-not-track="true"
                data-cache="true"></script>"""

    return script_html

def setup_local_umami(force_download=False):
    """
    Configuración completa de Umami local
    """
    print("🔧 Configuración de Umami Analytics Local")
    print("=" * 50)

    # Leer configuración actual
    script_url = os.getenv('UMAMI_SCRIPT_URL', 'https://analytics.umami.is/script.js')
    website_id = os.getenv('UMAMI_WEBSITE_ID', '')

    if not website_id:
        print("❌ UMAMI_WEBSITE_ID no está configurado en .env")
        print("💡 Ejecuta 'python3 setup_umami.py' primero")
        return None

    print(f"📊 Website ID: {website_id}")
    print(f"🌐 Script URL: {script_url}")

    # Verificar script local existente
    local_info = get_local_script_info()

    if local_info and not force_download:
        print(f"\n📁 Script local encontrado:")
        print(f"   Descargado: {local_info['download_date']}")
        print(f"   Hash: {local_info['hash']}")
        print(f"   Tamaño: {local_info['size']} bytes")

        # Verificar actualizaciones
        if check_script_updates(script_url, local_info['hash']):
            update = input("\n🆕 ¿Descargar nueva versión? (Y/n): ").lower().strip()
            if update != 'n':
                force_download = True

        if not force_download:
            print("✅ Usando script local existente")
            return {
                'local_path': 'js/umami.js',
                'website_id': website_id,
                'html': create_privacy_compliant_script(website_id)
            }

    # Descargar script
    result = download_umami_script(script_url)

    if result:
        print("\n✅ Script configurado correctamente")
        print("📁 Archivos creados:")
        print(f"   - docs/js/umami.js (script principal)")
        print(f"   - docs/js/umami-{result['hash']}.js (versión específica)")
        print(f"   - docs/js/umami-metadata.json (metadatos)")

        return {
            'local_path': result['local_path'],
            'website_id': website_id,
            'html': create_privacy_compliant_script(website_id, result['local_path'])
        }
    else:
        print("❌ Error al configurar el script local")
        return None

def clean_old_scripts(output_dir="docs/js", keep_latest=3):
    """
    Limpia versiones antiguas del script manteniendo las más recientes
    """
    try:
        if not os.path.exists(output_dir):
            return

        # Encontrar archivos umami-*.js
        script_files = []
        for file in os.listdir(output_dir):
            if file.startswith('umami-') and file.endswith('.js') and file != 'umami.js':
                file_path = os.path.join(output_dir, file)
                script_files.append((file, os.path.getctime(file_path)))

        # Ordenar por fecha de creación (más recientes primero)
        script_files.sort(key=lambda x: x[1], reverse=True)

        # Eliminar archivos antiguos
        if len(script_files) > keep_latest:
            for file, _ in script_files[keep_latest:]:
                file_path = os.path.join(output_dir, file)
                os.remove(file_path)
                print(f"🗑️  Eliminado script antiguo: {file}")

    except Exception as e:
        print(f"⚠️  Error al limpiar scripts antiguos: {e}")

def main():
    """
    Función principal del script
    """
    import argparse

    parser = argparse.ArgumentParser(description="Configurador de Umami Analytics Local")
    parser.add_argument('--force', action='store_true', help="Forzar descarga aunque ya exista")
    parser.add_argument('--clean', action='store_true', help="Limpiar scripts antiguos")
    parser.add_argument('--check', action='store_true', help="Solo verificar actualizaciones")

    args = parser.parse_args()

    # Cargar variables de entorno
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if args.check:
        # Solo verificar actualizaciones
        local_info = get_local_script_info()
        if local_info:
            script_url = os.getenv('UMAMI_SCRIPT_URL', 'https://analytics.umami.is/script.js')
            has_updates = check_script_updates(script_url, local_info['hash'])
            if not has_updates:
                print("✅ El script está actualizado")
        else:
            print("❌ No hay script local para verificar")
        return

    if args.clean:
        clean_old_scripts()
        return

    # Configurar Umami local
    result = setup_local_umami(force_download=args.force)

    if result:
        print("\n🚀 Próximos pasos:")
        print("1. El script html_index.py ya está configurado para usar el script local")
        print("2. Ejecuta: python3 html_index.py")
        print("3. Despliega tu sitio")
        print("4. ¡El script se cargará desde tu propio dominio!")

        print(f"\n📊 Código HTML generado:")
        print(result['html'])
    else:
        print("\n❌ No se pudo configurar Umami local")
        print("💡 Verifica tu conexión a internet y la configuración en .env")

if __name__ == "__main__":
    main()
