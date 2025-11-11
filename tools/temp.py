#!/usr/bin/env python3
"""
Script para reemplazar completamente el método get_evolution_data
"""

def replace_evolution_method():
    """Reemplaza el método get_evolution_data con la versión corregida"""

    # Leer el archivo completo
    with open('group_stats_database.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Encontrar las líneas de inicio y fin de la función
    start_line = None
    end_line = None

    for i, line in enumerate(lines):
        if 'def get_evolution_data(' in line:
            start_line = i
        elif start_line is not None and 'def get_total_shared_counts(' in line:
            end_line = i
            break

    if start_line is None or end_line is None:
        print("❌ No se pudo encontrar la función get_evolution_data")
        return

    print(f"🔍 Función encontrada en líneas {start_line + 1} a {end_line}")

    # Nuevo método corregido
    new_method = '''    def get_evolution_data(self, users: List[str], from_year: int, to_year: int,
                         mbid_only: bool = False) -> Dict:
        """Obtiene datos de evoluciÃ³n temporal para grÃ¡ficos lineales"""
        years = list(range(from_year, to_year + 1))

        evolution = {
            'artists': {},
            'albums': {},
            'tracks': {},
            'genres': {},
            'labels': {},
            'release_years': {},
            'years': years
        }

        # Recopilar todos los elementos únicos por categoría primero
        all_items = {
            'artists': set(),
            'albums': set(),
            'tracks': set(),
            'genres': set(),
            'labels': set(),
            'release_years': set()
        }

        # Para cada año, obtener tops y recopilar elementos únicos
        for year in years:
            # Artistas
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                all_items['artists'].add(item['name'])

            # Álbumes
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                all_items['albums'].add(item['name'])

            # Canciones
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                all_items['tracks'].add(item['name'])

            # Géneros
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                all_items['genres'].add(item['name'])

            # Sellos
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                all_items['labels'].add(item['name'])

            # Años de lanzamiento
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                all_items['release_years'].add(item['name'])

        # Inicializar estructura completa para todos los elementos
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            for item_name in all_items[category]:
                evolution[category][item_name] = {y: {'total': 0, 'users': {}} for y in years}

        # Ahora llenar con datos reales año por año
        for year in years:
            # Procesar artistas para este año
            top_artists = self.get_top_artists_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_artists:
                if item['name'] in evolution['artists']:
                    evolution['artists'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_artist(users, item['name'], year, year, mbid_only)
                    evolution['artists'][item['name']][year]['users'] = user_details

            # Procesar álbumes para este año
            top_albums = self.get_top_albums_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_albums:
                if item['name'] in evolution['albums']:
                    evolution['albums'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_album(users, item['artist'], item['album'], year, year, mbid_only)
                    evolution['albums'][item['name']][year]['users'] = user_details

            # Procesar canciones para este año
            top_tracks = self.get_top_tracks_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_tracks:
                if item['name'] in evolution['tracks']:
                    evolution['tracks'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_track(users, item['artist'], item['track'], year, year, mbid_only)
                    evolution['tracks'][item['name']][year]['users'] = user_details

            # Procesar géneros para este año
            top_genres = self.get_top_genres_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_genres:
                if item['name'] in evolution['genres']:
                    evolution['genres'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_genre(users, item['name'], year, year, mbid_only)
                    evolution['genres'][item['name']][year]['users'] = user_details

            # Procesar sellos para este año
            top_labels = self.get_top_labels_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_labels:
                if item['name'] in evolution['labels']:
                    evolution['labels'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_label(users, item['name'], year, year, mbid_only)
                    evolution['labels'][item['name']][year]['users'] = user_details

            # Procesar años de lanzamiento para este año
            top_years = self.get_top_release_years_by_scrobbles_only(users, year, year, 15, mbid_only)
            for item in top_years:
                if item['name'] in evolution['release_years']:
                    evolution['release_years'][item['name']][year]['total'] = item['total_scrobbles']
                    user_details = self._get_user_breakdown_for_release_year(users, item['name'], year, year, mbid_only)
                    evolution['release_years'][item['name']][year]['users'] = user_details

        # Reducir a top 15 por categoría para visualización
        for category in ['artists', 'albums', 'tracks', 'genres', 'labels', 'release_years']:
            # Calcular total por elemento
            totals = {}
            for item, year_data in evolution[category].items():
                totals[item] = sum(year_data[y]['total'] for y in years)

            # Quedarse con top 15
            top_items = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:15]
            evolution[category] = {item: evolution[category][item] for item, _ in top_items}

        return evolution

'''

    # Reemplazar las líneas
    new_lines = lines[:start_line] + [new_method] + lines[end_line:]

    # Escribir el archivo modificado
    with open('group_stats_database.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print("✅ Método get_evolution_data reemplazado exitosamente")
    print("🎯 Cambios realizados:")
    print("  - Recopila TODOS los elementos únicos antes de inicializar")
    print("  - Inicializa estructura completa para todos los años")
    print("  - Llena datos año por año garantizando consistencia")

if __name__ == '__main__':
    replace_evolution_method()
