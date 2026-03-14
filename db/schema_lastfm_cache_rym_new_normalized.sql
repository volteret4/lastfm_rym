
Estructura de la tabla: users
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'username', 'TEXT', 1, None, 0)
(2, 'created_at', 'INTEGER', 0, "strftime('%s','now')", 0)

Estructura de la tabla: sqlite_sequence
(0, 'name', '', 0, None, 0)
(1, 'seq', '', 0, None, 0)

Estructura de la tabla: artists
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'name', 'TEXT', 1, None, 0)
(2, 'mbid', 'TEXT', 0, None, 0)
(3, 'listeners', 'INTEGER', 0, None, 0)
(4, 'playcount', 'INTEGER', 0, None, 0)
(5, 'lastfm_url', 'TEXT', 0, None, 0)
(6, 'img_url', 'TEXT', 0, None, 0)
(7, 'img_urls', 'TEXT', 0, None, 0)
(8, 'bio', 'TEXT', 0, None, 0)
(9, 'country', 'TEXT', 0, None, 0)
(10, 'begin_date', 'TEXT', 0, None, 0)
(11, 'end_date', 'TEXT', 0, None, 0)
(12, 'formed_year', 'INTEGER', 0, None, 0)
(13, 'artist_type', 'TEXT', 0, None, 0)
(14, 'disambiguation', 'TEXT', 0, None, 0)
(15, 'aliases', 'TEXT', 0, None, 0)
(16, 'member_of', 'TEXT', 0, None, 0)
(17, 'spotify_url', 'TEXT', 0, None, 0)
(18, 'youtube_url', 'TEXT', 0, None, 0)
(19, 'discogs_url', 'TEXT', 0, None, 0)
(20, 'bandcamp_url', 'TEXT', 0, None, 0)
(21, 'rateyourmusic_url', 'TEXT', 0, None, 0)
(22, 'wikipedia_url', 'TEXT', 0, None, 0)
(23, 'musicbrainz_url', 'TEXT', 0, None, 0)
(24, 'created_at', 'INTEGER', 0, "strftime('%s','now')", 0)
(25, 'last_updated', 'INTEGER', 0, "strftime('%s','now')", 0)
(26, 'added_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: albums
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'name', 'TEXT', 1, None, 0)
(2, 'artist_id', 'INTEGER', 1, None, 0)
(3, 'mbid', 'TEXT', 0, None, 0)
(4, 'year', 'INTEGER', 0, None, 0)
(5, 'originalyear', 'INTEGER', 0, None, 0)
(6, 'release_date', 'TEXT', 0, None, 0)
(7, 'release_group_mbid', 'TEXT', 0, None, 0)
(8, 'album_type', 'TEXT', 0, None, 0)
(9, 'status', 'TEXT', 0, None, 0)
(10, 'country', 'TEXT', 0, None, 0)
(11, 'barcode', 'TEXT', 0, None, 0)
(12, 'total_tracks', 'INTEGER', 0, None, 0)
(13, 'label', 'TEXT', 0, None, 0)
(14, 'spotify_id', 'TEXT', 0, None, 0)
(15, 'spotify_url', 'TEXT', 0, None, 0)
(16, 'yt_id', 'TEXT', 0, None, 0)
(17, 'rateyourmusic_url', 'TEXT', 0, None, 0)
(18, 'cover_url', 'TEXT', 0, None, 0)
(19, 'wikipedia_url', 'TEXT', 0, None, 0)
(20, 'lastfm_url', 'TEXT', 0, None, 0)
(21, 'musicbrainz_url', 'TEXT', 0, None, 0)
(22, 'scaruffi_rating', 'REAL', 0, None, 0)
(23, 'scaruffi_note', 'TEXT', 0, None, 0)
(24, 'aoty_user_score', 'INTEGER', 0, None, 0)
(25, 'aoty_critic_score', 'INTEGER', 0, None, 0)
(26, 'metacritic_score', 'INTEGER', 0, None, 0)
(27, 'created_at', 'INTEGER', 0, "strftime('%s','now')", 0)
(28, 'last_updated', 'INTEGER', 0, "strftime('%s','now')", 0)
(29, 'added_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: album_metadata
(0, 'album_id', 'INTEGER', 0, None, 1)
(1, 'desc_lfm_album', 'TEXT', 0, None, 0)
(2, 'desc_lfm_artist', 'TEXT', 0, None, 0)
(3, 'desc_mb_album', 'TEXT', 0, None, 0)
(4, 'desc_mb_artist', 'TEXT', 0, None, 0)
(5, 'wikipedia_content', 'TEXT', 0, None, 0)
(6, 'producers', 'TEXT', 0, None, 0)
(7, 'engineers', 'TEXT', 0, None, 0)
(8, 'credits', 'TEXT', 0, None, 0)

Estructura de la tabla: tracks
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'name', 'TEXT', 1, None, 0)
(2, 'artist_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'mbid', 'TEXT', 0, None, 0)
(5, 'duration_ms', 'INTEGER', 0, None, 0)
(6, 'track_number', 'INTEGER', 0, None, 0)
(7, 'isrc', 'TEXT', 0, None, 0)
(8, 'created_at', 'INTEGER', 0, "strftime('%s','now')", 0)
(9, 'last_updated', 'INTEGER', 0, "strftime('%s','now')", 0)

Estructura de la tabla: genres
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'name', 'TEXT', 1, None, 0)
(2, 'source', 'TEXT', 0, None, 0)
(3, 'last_updated', 'INTEGER', 0, None, 0)

Estructura de la tabla: album_genres
(0, 'album_id', 'INTEGER', 1, None, 1)
(1, 'genre_id', 'INTEGER', 1, None, 2)
(2, 'weight', 'REAL', 0, '1.0', 0)

Estructura de la tabla: artist_genres
(0, 'artist_id', 'INTEGER', 1, None, 1)
(1, 'genre_id', 'INTEGER', 1, None, 2)
(2, 'weight', 'REAL', 0, '1.0', 0)

Estructura de la tabla: user_first_artist_listen
(0, 'user_id', 'INTEGER', 1, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 2)
(2, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: user_first_album_listen
(0, 'user_id', 'INTEGER', 1, None, 1)
(1, 'album_id', 'INTEGER', 1, None, 2)
(2, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: user_first_track_listen
(0, 'user_id', 'INTEGER', 1, None, 1)
(1, 'track_id', 'INTEGER', 1, None, 2)
(2, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: user_first_label_listen
(0, 'user_id', 'INTEGER', 1, None, 1)
(1, 'label', 'TEXT', 1, None, 2)
(2, 'first_timestamp', 'INTEGER', 0, None, 0)

Estructura de la tabla: group_stats
(0, 'stat_type', 'TEXT', 1, None, 1)
(1, 'stat_key', 'TEXT', 1, None, 2)
(2, 'from_year', 'INTEGER', 0, None, 3)
(3, 'to_year', 'INTEGER', 0, None, 4)
(4, 'user_count', 'INTEGER', 0, None, 0)
(5, 'total_scrobbles', 'INTEGER', 0, None, 0)
(6, 'shared_by_users', 'TEXT', 0, None, 0)
(7, 'data_json', 'TEXT', 0, None, 0)
(8, 'last_updated', 'INTEGER', 0, None, 0)

Estructura de la tabla: scrobbles_eliasj72
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_frikomid
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_gabredmared
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_lonsonxd
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_nubis84
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_rocky_stereo
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_alberto_gu
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_paqueradejere
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_sdecandelario
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

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

Estructura de la tabla: scrobbles_bipolarmuzik
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)

Estructura de la tabla: scrobbles_verygooood
(0, 'id', 'INTEGER', 0, None, 1)
(1, 'artist_id', 'INTEGER', 1, None, 0)
(2, 'track_id', 'INTEGER', 1, None, 0)
(3, 'album_id', 'INTEGER', 0, None, 0)
(4, 'timestamp', 'INTEGER', 1, None, 0)
