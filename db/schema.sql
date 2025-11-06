
Estructura de la tabla: scrobbles
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'user', 'TEXT', 1, None, 0)
(2, 'artist', 'TEXT', 1, None, 0)
(3, 'track', 'TEXT', 1, None, 0)
(4, 'album', 'TEXT', 0, None, 0)
(5, 'timestamp', 'INTEGER', 1, None, 0)

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
