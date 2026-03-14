
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
(9, 'bio', 'TEXT', 0, None, 0)
(10, 'tags', 'TEXT', 0, None, 0)
(11, 'listeners', 'TEXT', 0, None, 0)
(12, 'playcount', 'TEXT', 0, None, 0)
(13, 'url', 'TEXT', 0, None, 0)
(14, 'image_url', 'TEXT', 0, None, 0)

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

Estructura de la tabla: album_genres
(0, 'artist', 'TEXT', 1, None, 1)
(1, 'album', 'TEXT', 1, None, 2)
(2, 'source', 'TEXT', 1, None, 3)
(3, 'genre', 'TEXT', 1, None, 4)
(4, 'weight', 'REAL', 0, '1.0', 0)
(5, 'last_updated', 'INTEGER', 1, None, 0)

Estructura de la tabla: group_stats
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'stat_type', 'TEXT', 1, None, 0)
(2, 'stat_key', 'TEXT', 1, None, 0)
(3, 'from_year', 'INTEGER', 1, None, 0)
(4, 'to_year', 'INTEGER', 1, None, 0)
(5, 'user_count', 'INTEGER', 0, '0', 0)
(6, 'total_scrobbles', 'INTEGER', 0, '0', 0)
(7, 'shared_by_users', 'TEXT', 0, None, 0)
(8, 'data_json', 'TEXT', 0, None, 0)
(9, 'created_at', 'INTEGER', 1, None, 0)

Estructura de la tabla: listenbrainz_imports
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'listenbrainz_user', 'TEXT', 1, None, 0)
(2, 'lastfm_user', 'TEXT', 1, None, 0)
(3, 'last_import_timestamp', 'INTEGER', 0, None, 0)
(4, 'total_imported', 'INTEGER', 0, '0', 0)
(5, 'created_at', 'INTEGER', 1, None, 0)
(6, 'updated_at', 'INTEGER', 1, None, 0)

Estructura de la tabla: listenbrainz_file_imports
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'source_directory', 'TEXT', 1, None, 0)
(2, 'lastfm_user', 'TEXT', 1, None, 0)
(3, 'file_path', 'TEXT', 1, None, 0)
(4, 'file_mtime', 'INTEGER', 1, None, 0)
(5, 'listens_imported', 'INTEGER', 1, None, 0)
(6, 'created_at', 'INTEGER', 1, None, 0)

Estructura de la tabla: import_errors
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'file_path', 'TEXT', 1, None, 0)
(2, 'line_number', 'INTEGER', 0, None, 0)
(3, 'error_type', 'TEXT', 1, None, 0)
(4, 'error_message', 'TEXT', 1, None, 0)
(5, 'raw_data', 'TEXT', 0, None, 0)
(6, 'created_at', 'INTEGER', 1, None, 0)

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

Estructura de la tabla: user_first_artist_listen
(0, 'user', 'TEXT', 0, None, 1)
(1, 'artist', 'TEXT', 0, None, 2)
(2, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: user_first_album_listen
(0, 'user', 'TEXT', 0, None, 1)
(1, 'artist', 'TEXT', 0, None, 2)
(2, 'album', 'TEXT', 0, None, 3)
(3, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: user_first_track_listen
(0, 'user', 'TEXT', 0, None, 1)
(1, 'artist', 'TEXT', 0, None, 2)
(2, 'track', 'TEXT', 0, None, 3)
(3, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: user_first_label_listen
(0, 'user', 'TEXT', 0, None, 1)
(1, 'label', 'TEXT', 0, None, 2)
(2, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: cache_responses
(0, 'cache_key', 'TEXT', 0, None, 1)
(1, 'response_data', 'TEXT', 1, None, 0)
(2, 'created_at', 'INTEGER', 1, None, 0)
(3, 'expires_at', 'INTEGER', 1, None, 0)
