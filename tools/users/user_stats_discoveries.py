#!/usr/bin/env python3
"""
Script para generar archivos JSON de novedades por usuario
Crea docs/data/usuarios/{periodo}/usuario.json para cada usuario
"""

import os
import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    if not os.getenv('LASTFM_USERS'):
        load_dotenv()
except ImportError:
    pass


class DiscoveriesDataGenerator:
    """Generador de archivos JSON con datos de novedades por usuario"""

    def __init__(self, db_path='db/lastfm_cache.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def get_user_discoveries_by_year(self, user: str, from_year: int, to_year: int,
                                   discovery_type: str = 'artists') -> dict:
        """Obtiene las novedades del usuario por año"""
        cursor = self.conn.cursor()

        from_timestamp = int(datetime(from_year, 1, 1).timestamp())
        to_timestamp = int(datetime(to_year + 1, 1, 1).timestamp()) - 1

        discoveries_by_year = {}

        table_map = {
            'artists': 'user_first_artist_listen',
            'albums': 'user_first_album_listen',
            'tracks': 'user_first_track_listen',
            'labels': 'user_first_label_listen'
        }

        if discovery_type not in table_map:
            return {}

        table = table_map[discovery_type]

        try:
            if discovery_type == 'artists':
                cursor.execute(f'''
                    SELECT artist as name, first_timestamp
                    FROM {table}
                    WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                    ORDER BY first_timestamp ASC
                ''', (user, from_timestamp, to_timestamp))

            elif discovery_type == 'albums':
                cursor.execute(f'''
                    SELECT (artist || ' - ' || album) as name, first_timestamp
                    FROM {table}
                    WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                    ORDER BY first_timestamp ASC
                ''', (user, from_timestamp, to_timestamp))

            elif discovery_type == 'tracks':
                cursor.execute(f'''
                    SELECT (artist || ' - ' || track) as name, first_timestamp
                    FROM {table}
                    WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                    ORDER BY first_timestamp ASC
                ''', (user, from_timestamp, to_timestamp))

            elif discovery_type == 'labels':
                cursor.execute(f'''
                    SELECT label as name, first_timestamp
                    FROM {table}
                    WHERE user = ? AND first_timestamp >= ? AND first_timestamp <= ?
                    ORDER BY first_timestamp ASC
                ''', (user, from_timestamp, to_timestamp))

            for row in cursor.fetchall():
                first_date = datetime.fromtimestamp(row['first_timestamp'])
                year = first_date.year

                if year not in discoveries_by_year:
                    discoveries_by_year[year] = []

                discoveries_by_year[year].append({
                    'name': row['name'],
                    'timestamp': row['first_timestamp'],
                    'date': first_date.strftime('%Y-%m-%d'),
                    'month': first_date.strftime('%Y-%m')
                })

        except sqlite3.OperationalError as e:
            print(f"Error consultando tabla {table}: {e}")
            return {}

        return discoveries_by_year

    def get_user_discoveries_stats(self, user: str, from_year: int, to_year: int) -> dict:
        """Obtiene estadísticas resumidas de novedades"""
        stats = {
            'user': user,
            'period': f"{from_year}-{to_year}",
            'discoveries': {},
            'totals': {},
            'yearly_totals': {}
        }

        discovery_types = ['artists', 'albums', 'tracks', 'labels']

        # Inicializar estructura de años
        for year in range(from_year, to_year + 1):
            stats['yearly_totals'][year] = {}

        for discovery_type in discovery_types:
            discoveries = self.get_user_discoveries_by_year(
                user, from_year, to_year, discovery_type
            )

            # Guardar solo los primeros 50 elementos por año para el JSON
            # (el resto se puede cargar dinámicamente si se necesita)
            limited_discoveries = {}
            yearly_counts = {}

            for year in range(from_year, to_year + 1):
                year_data = discoveries.get(year, [])
                count = len(year_data)
                yearly_counts[year] = count

                # Limitar a 50 elementos por año
                limited_discoveries[year] = {
                    'count': count,
                    'items': year_data[:50],  # Solo primeros 50
                    'has_more': count > 50
                }

                stats['yearly_totals'][year][discovery_type] = count

            stats['discoveries'][discovery_type] = limited_discoveries
            stats['totals'][discovery_type] = sum(yearly_counts.values())

        return stats

    def generate_user_json(self, user: str, from_year: int, to_year: int,
                          output_dir: str) -> str:
        """Genera archivo JSON para un usuario específico"""
        print(f"  📊 Generando datos para {user}...")

        # Generar estadísticas
        user_data = self.get_user_discoveries_stats(user, from_year, to_year)

        # Crear directorio si no existe
        user_output_dir = Path(output_dir)
        user_output_dir.mkdir(parents=True, exist_ok=True)

        # Guardar archivo JSON
        output_file = user_output_dir / f"{user}.json"

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, indent=2, ensure_ascii=False)

        # Mostrar estadísticas
        total_discoveries = sum(user_data['totals'].values())
        print(f"    ✨ Total novedades: {total_discoveries}")
        for discovery_type, count in user_data['totals'].items():
            if count > 0:
                print(f"      - {discovery_type}: {count}")

        return str(output_file)

    def generate_all_users_data(self, users: list, years_back: int = 5) -> str:
        """Genera archivos JSON para todos los usuarios"""
        current_year = datetime.now().year
        from_year = current_year - years_back
        to_year = current_year
        period = f"{from_year}-{to_year}"

        print(f"🎵 Generando datos de novedades para periodo {period}...")

        # Directorio de salida
        output_dir = f"docs/data/usuarios/{period}"

        # Verificar que las tablas existan
        if not self._check_tables():
            print("❌ Las tablas de primeras escuchas no existen.")
            print("Ejecuta: python create_first_listen_tables.py")
            return ""

        generated_files = []

        for user in users:
            try:
                output_file = self.generate_user_json(user, from_year, to_year, output_dir)
                generated_files.append(output_file)
            except Exception as e:
                print(f"    ❌ Error generando datos para {user}: {e}")

        # Generar archivo índice
        index_file = self._generate_index_file(output_dir, users, period)

        print(f"\n✅ Generados {len(generated_files)} archivos en {output_dir}")
        print(f"📋 Archivo índice: {index_file}")

        return output_dir

    def _check_tables(self) -> bool:
        """Verifica que las tablas de primeras escuchas existan"""
        cursor = self.conn.cursor()
        required_tables = [
            'user_first_artist_listen',
            'user_first_album_listen',
            'user_first_track_listen',
            'user_first_label_listen'
        ]

        for table in required_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                cursor.fetchone()
            except sqlite3.OperationalError:
                return False
        return True

    def _generate_index_file(self, output_dir: str, users: list, period: str) -> str:
        """Genera archivo índice con información de todos los usuarios"""
        index_data = {
            'period': period,
            'users': users,
            'generated_at': datetime.now().isoformat(),
            'files': [f"{user}.json" for user in users],
            'structure': {
                'discoveries': {
                    'artists': 'Nuevos artistas por año',
                    'albums': 'Nuevos álbumes por año',
                    'tracks': 'Nuevas canciones por año',
                    'labels': 'Nuevos sellos por año'
                },
                'yearly_format': {
                    'count': 'Número total de novedades',
                    'items': 'Lista de elementos (máximo 50)',
                    'has_more': 'True si hay más elementos'
                }
            }
        }

        index_file = Path(output_dir) / "_index.json"

        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

        return str(index_file)

    def close(self):
        """Cerrar conexión"""
        self.conn.close()


def main():
    """Función principal"""
    try:
        # Obtener usuarios de variables de entorno
        users = [u.strip() for u in os.getenv('LASTFM_USERS', '').split(',') if u.strip()]
        if not users:
            print("❌ Variable LASTFM_USERS no configurada")
            print("Ejemplo: export LASTFM_USERS='usuario1,usuario2,usuario3'")
            sys.exit(1)

        print(f"👥 Usuarios: {users}")

        # Generar archivos JSON
        generator = DiscoveriesDataGenerator()
        output_dir = generator.generate_all_users_data(users, years_back=5)

        if output_dir:
            print(f"\n🎉 Archivos JSON generados correctamente!")
            print(f"📁 Directorio: {output_dir}")
            print(f"📊 Archivos por usuario: [usuario].json")
            print(f"📋 Índice: _index.json")

            print(f"\n💡 Para usar en el HTML:")
            print(f"   - Los archivos JSON son mucho más pequeños")
            print(f"   - Se cargan dinámicamente cuando el usuario selecciona un gráfico")
            print(f"   - Mejor rendimiento y tamaño de archivo")

        generator.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
