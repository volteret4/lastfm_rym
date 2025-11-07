
Estructura de la tabla: scrobbles
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user', 'TEXT', 1, None, 0)
(2, 'artist', 'TEXT', 1, None, 0)
(3, 'track', 'TEXT', 1, None, 0)
(4, 'album', 'TEXT', 0, None, 0)
(5, 'timestamp', 'INTEGER', 1, None, 0)
(6, 'artist_mbid', 'TEXT', 0, None, 0)
(7, 'album_mbid', 'TEXT', 0, None, 0)
(8, 'track_mbid', 'TEXT', 0, None, 0)

Estructura de la tabla: sqlite_sequence
(0, 'name', '', 0, None, 0)
(1, 'seq', '', 0, None, 0)

Estructura de la tabla: artist_genres
(0, 'artist', 'TEXT', 0, None, 1)
(1, 'genres', 'TEXT', 1, None, 0)
(2, 'updated_at', 'INTEGER', 1, None, 0)

Estructura de la tabla: album_labels
(0, 'artist', 'TEXT', 1, None, 1)
(1, 'album', 'TEXT', 1, None, 2)
(2, 'label', 'TEXT', 0, None, 0)
(3, 'updated_at', 'INTEGER', 1, None, 0)

Estructura de la tabla: album_release_dates
(0, 'artist', 'TEXT', 1, None, 1)
(1, 'album', 'TEXT', 1, None, 2)
(2, 'release_year', 'INTEGER', 0, None, 0)
(3, 'release_date', 'TEXT', 0, None, 0)
(4, 'updated_at', 'INTEGER', 1, None, 0)

Estructura de la tabla: artist_details
(0, 'artist', 'TEXT', 0, None, 1)
(1, 'mbid', 'TEXT', 0, None, 0)
(2, 'begin_date', 'TEXT', 0, None, 0)
(3, 'end_date', 'TEXT', 0, None, 0)
(4, 'artist_type', 'TEXT', 0, None, 0)
(5, 'country', 'TEXT', 0, None, 0)
(6, 'disambiguation', 'TEXT', 0, None, 0)
(7, 'similar_artists', 'TEXT', 0, None, 0)
(8, 'last_updated', 'INTEGER', 1, None, 0)

Estructura de la tabla: album_details
(0, 'artist', 'TEXT', 1, None, 1)
(1, 'album', 'TEXT', 1, None, 2)
(2, 'mbid', 'TEXT', 0, None, 0)
(3, 'release_group_mbid', 'TEXT', 0, None, 0)
(4, 'original_release_date', 'TEXT', 0, None, 0)
(5, 'album_type', 'TEXT', 0, None, 0)
(6, 'status', 'TEXT', 0, None, 0)
(7, 'packaging', 'TEXT', 0, None, 0)
(8, 'country', 'TEXT', 0, None, 0)
(9, 'barcode', 'TEXT', 0, None, 0)
(10, 'catalog_number', 'TEXT', 0, None, 0)
(11, 'total_tracks', 'INTEGER', 0, None, 0)
(12, 'last_updated', 'INTEGER', 1, None, 0)

Estructura de la tabla: track_details
(0, 'artist', 'TEXT', 1, None, 1)
(1, 'track', 'TEXT', 1, None, 2)
(2, 'mbid', 'TEXT', 0, None, 0)
(3, 'duration_ms', 'INTEGER', 0, None, 0)
(4, 'track_number', 'INTEGER', 0, None, 0)
(5, 'album', 'TEXT', 0, None, 0)
(6, 'isrc', 'TEXT', 0, None, 0)
(7, 'last_updated', 'INTEGER', 1, None, 0)

Estructura de la tabla: artist_genres_detailed
(0, 'artist', 'TEXT', 1, None, 1)
(1, 'source', 'TEXT', 1, None, 2)
(2, 'genre', 'TEXT', 1, None, 3)
(3, 'weight', 'REAL', 0, '1.0', 0)
(4, 'last_updated', 'INTEGER', 1, None, 0)

Estructura de la tabla: api_cache
(0, 'cache_key', 'TEXT', 0, None, 1)
(1, 'response_data', 'TEXT', 1, None, 0)
(2, 'created_at', 'INTEGER', 1, None, 0)
(3, 'expires_at', 'INTEGER', 0, None, 0)

Estructura de la tabla: sqlite_stat1
(0, 'tbl', '', 0, None, 0)
(1, 'idx', '', 0, None, 0)
(2, 'stat', '', 0, None, 0)

Estructura de la tabla: sqlite_stat4
(0, 'tbl', '', 0, None, 0)
(1, 'idx', '', 0, None, 0)
(2, 'neq', '', 0, None, 0)
(3, 'nlt', '', 0, None, 0)
(4, 'ndlt', '', 0, None, 0)
(5, 'sample', '', 0, None, 0)
