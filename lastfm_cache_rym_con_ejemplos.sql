🔍 Extractor de Schema SQLite con Ejemplos REALES
-------------------------------------------------------

🔄 Extrayendo schema y ejemplos reales...

📋 Procesando tabla: scrobbles

📋 Procesando tabla: sqlite_sequence

📋 Procesando tabla: artist_genres

📋 Procesando tabla: album_labels

📋 Procesando tabla: album_release_dates

📋 Procesando tabla: artist_details

📋 Procesando tabla: album_details

📋 Procesando tabla: track_details

📋 Procesando tabla: artist_genres_detailed

📋 Procesando tabla: api_cache

📋 Procesando tabla: album_genres

📋 Procesando tabla: group_stats

📋 Procesando tabla: listenbrainz_imports

📋 Procesando tabla: listenbrainz_file_imports

📋 Procesando tabla: import_errors

📋 Procesando tabla: sqlite_stat1

📋 Procesando tabla: sqlite_stat4

📋 Procesando tabla: user_first_artist_listen

📋 Procesando tabla: user_first_album_listen

📋 Procesando tabla: user_first_track_listen

📋 Procesando tabla: user_first_label_listen

📋 Procesando tabla: cache_responses

📋 Selecciona el tipo de reporte:
1. Reporte detallado
2. Reporte resumido
Opción (1 o 2, por defecto 1): 
================================================================================
📊 REPORTE DE SCHEMA DE BASE DE DATOS SQLite
================================================================================
📁 Base de datos: db/lastfm_cache.db
🏷️  Total de tablas: 22

🔷 TABLA: scrobbles
   Columnas: 9
   Filas: 1686800
   ------------------------------------------------------------
   📌 id (INTEGER)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: 8, 23, 5

   📌 user (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: BipolarMuzik, EliasJ72, Lonsonxd

   📌 artist (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: !deladap, !!! (Chk Chk Chk), "A LA PLATA LA GASTO COMO QUIERO"

   📌 track (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: !!! KWE, !, !!!...

   📌 album (TEXT)
      💡 Ejemplos reales: !!!, !!Going Places!!, !

   📌 timestamp (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1186593753, 1186592219, 1186593140

   📌 artist_mbid (TEXT)
      💡 Ejemplos reales: 00aab979-da36-4efd-9086-e409cda07f9c, 000fc734-b7e1-4a01-92d1-f544261b43f5, 0039c7ae-e1a7-4a7d-9b49-0cbc716821a6

   📌 album_mbid (TEXT)
      💡 Ejemplos reales: 000127ea-bac2-488f-979d-c153d461e40b, 00007f96-14a8-43e8-955d-0b00323a53bd, 000227c7-043c-40ae-a942-ed526e9514dc

   📌 track_mbid (TEXT)
      💡 Ejemplos reales: 00001b2e-16ad-48da-ad50-a3b73c4ab743, 000005ea-bb35-3294-9154-69f8889a5658, 000016fe-83b9-41da-99a8-c50389f431f4


🔷 TABLA: sqlite_sequence
   Columnas: 2
   Filas: 2
   ------------------------------------------------------------
   📌 name ()
      💡 Ejemplos reales: scrobbles, listenbrainz_file_imports

   📌 seq ()
      💡 Ejemplos reales: 1853633, 136


🔷 TABLA: artist_genres
   Columnas: 3
   Filas: 32578
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: "Me he pasado TODOS los CALL OF DUTY", "I forgo the vengeance of my son", "I Have So Much Strength In Me, You Have No Idea" | Punch

   📌 genres (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: ["ambient", "new age", "Nature", "relaxation", "Meditation"], ["post-rock", "ambient", "instrumental", "electronic", "Korean"], ["heavy metal", "darkwave", "hard rock", "Power metal", "electro-gothic"]

   📌 updated_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762800440, 1762800448, 1762800445


🔷 TABLA: album_labels
   Columnas: 4
   Filas: 91935
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !!!, !nertia, "Powers of Ten"

   📌 album (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: 31 Minutos, Ratoncitos, 360, 30 Degrees Everywhere

   📌 label (TEXT)
      💡 Ejemplos reales: APLAPLAC, Tokyo Broadcasting System, Inc., Sony Music Spain

   📌 updated_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762702553, 1762702557, 1762702551


🔷 TABLA: album_release_dates
   Columnas: 5
   Filas: 115759
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !deladap, "Powers of Ten", "Blue" Gene Tyranny

   📌 album (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: (What's the Story) Morning Glory? [Remastered], 31 Minutos, Ratoncitos, 360

   📌 release_year (INTEGER)
      💡 Ejemplos reales: 2014, 2002, 2023

   📌 release_date (TEXT)
      💡 Ejemplos reales: 2023, 2013, 2014

   📌 updated_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762702551, 1762702558, 1762702559


🔷 TABLA: artist_details
   Columnas: 15
   Filas: 64373
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: "A LA PLATA LA GASTO COMO QUIERO", !!! (Chk Chk Chk), !deladap

   📌 mbid (TEXT)
      💡 Ejemplos reales: 0003bd90-7cdc-43bc-ab79-73595f8f4019, 0005682c-3083-415e-ae4c-debd7be3e47e, 00050e90-e93a-4b06-b233-8899d437d201

   📌 begin_date (TEXT)
      💡 Ejemplos reales: 1971-10-24, 2018-01-01, 1981

   📌 end_date (TEXT)
      💡 Ejemplos reales: 1997, 2017, 1983

   📌 artist_type (TEXT)
      💡 Ejemplos reales: Other, Character, Orchestra

   📌 country (TEXT)
      💡 Ejemplos reales: MX, GB, AU

   📌 disambiguation (TEXT)
      💡 Ejemplos reales: fka Tity Boi, Nenad Marković, DJ & electronic music producer from Azov, lives in Rostov-On-Don, Russia

   📌 similar_artists (TEXT)
      💡 Ejemplos reales: [], ["Tee Vee Repairmann", "Billiam", "Gee Tee", "R.M.F.C.", "Cherry Cheeks", "The Gobs", "Satanic Togas", "Prison Affair", "Ghoulies", "C.C.T.V."], ["Rabo Karabekian", "Cone of Depression", "Yeziti", "Morphetik", "Dargothar", "Mentor", "Berserk Mode", "Bastardizer", "Killing", "Forced Neglect"]

   📌 last_updated (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762701439, 1762701438, 1762701442

   📌 bio (TEXT)
      💡 Ejemplos reales: <a href="https://www.last.fm/music/%C3%98wnvision">Read more on Last.fm</a>, <a href="https://www.last.fm/music/Izo+Pro+Official">Read more on Last.fm</a>, <a href="https://www.last.fm/music/SII">Read more on Last.fm</a>

   📌 tags (TEXT)
      💡 Ejemplos reales: ["pop", "indietronica", "electropop", "synthpop", "christian"], ["funk", "electronic", "nippon", "ghost box", "mordant music"], ["hardcore techno", "experimental", "hit em", "hardcore electronic", "jersey club"]

   📌 listeners (TEXT)
      💡 Ejemplos reales: 599, 567, 9

   📌 playcount (TEXT)
      💡 Ejemplos reales: 2190, 47, 13239

   📌 url (TEXT)
      💡 Ejemplos reales: https://www.last.fm/music/M%C3%BAsica+Infantil+TV, https://www.last.fm/music/Izo+Pro+Official, https://www.last.fm/music/New+West

   📌 image_url (TEXT)
      💡 Ejemplos reales: https://lastfm.freetls.fastly.net/i/u/300x300/2a96cbd8b46e442fc41c2b86b821562f.png


🔷 TABLA: album_details
   Columnas: 13
   Filas: 118355
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !!!, !Va, !deladap

   📌 album (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: As If, Let It Be Blue, Louden Up Now

   📌 mbid (TEXT)
      💡 Ejemplos reales: 0002b931-787e-4516-b22d-babf3c8b28f5, 000127ea-bac2-488f-979d-c153d461e40b, 0001a90e-252d-3af0-8e1c-173c1c4835c3

   📌 release_group_mbid (TEXT)
      💡 Ejemplos reales: 1dec285b-0ff2-475d-99b2-c8bcd7af4d0a, 561be5b7-a39c-3866-859d-d86f30816ae7, 69caa61f-bf7b-42fc-a9a8-05e8a04333b8

   📌 original_release_date (TEXT)
      💡 Ejemplos reales: 2014, 2023, 2002

   📌 album_type (TEXT)
      💡 Ejemplos reales: Other, Album, Single

   📌 status (TEXT)
      💡 Ejemplos reales: Withdrawn, Promotion, Bootleg

   📌 packaging (TEXT)
      💡 Ejemplos reales: None, Gatefold Cover, Jewel Case

   📌 country (TEXT)
      💡 Ejemplos reales: JP, ES, AF

   📌 barcode (TEXT)
      💡 Ejemplos reales: 4988002446407, 9340650008829, 00888072019195

   📌 catalog_number (TEXT)
      💡 Ejemplos reales: (sin valores en esta columna)

   📌 total_tracks (INTEGER)
      💡 Ejemplos reales: 22, 12, 7

   📌 last_updated (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762702556, 1762702551, 1762702554


🔷 TABLA: track_details
   Columnas: 8
   Filas: 156204
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !!!, "Atendedor de boludos", "Are You Threatening Me?" | Punch

   📌 track (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: Bend Over Beethoven, $50 Million, Bam City

   📌 mbid (TEXT)
      💡 Ejemplos reales: 000032c3-cc8d-490b-a78b-f2edf6a0741b, 000005ea-bb35-3294-9154-69f8889a5658, 00001b2e-16ad-48da-ad50-a3b73c4ab743

   📌 duration_ms (INTEGER)
      💡 Ejemplos reales: 219000, 236000, 258000

   📌 track_number (INTEGER)
      💡 Ejemplos reales: (sin valores en esta columna)

   📌 album (TEXT)
      💡 Ejemplos reales: Spanish Model, 9.0: Live, RAT WARS

   📌 isrc (TEXT)
      💡 Ejemplos reales: GBK3W2403080, USAT22410878, GBDHC2443211

   📌 last_updated (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762703550, 1762703551, 1762703555


🔷 TABLA: artist_genres_detailed
   Columnas: 5
   Filas: 266410
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !!! (Chk Chk Chk), !nertia, !deladap

   📌 source (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: lastfm, musicbrainz

   📌 genre (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: beat, breaks, Lo-Fi

   📌 weight (REAL)
      📋 DEFAULT: 1.0
      💡 Ejemplos reales: 1.0, 2.0, 3.0

   📌 last_updated (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762701439, 1762701442, 1762701440


🔷 TABLA: api_cache
   Columnas: 4
   Filas: 154684
   ------------------------------------------------------------
   📌 cache_key (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: album_enrich_$lum_2000: Parte 2, album_enrich_!!!_All U Writers / Gonna Guetta Stomp, album_enrich_(un)familiar., STOMACH BOOK y death do us apart_123 (the longest dream)

   📌 response_data (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: {"processed": true}

   📌 created_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762701442, 1762701440, 1762701438

   📌 expires_at (INTEGER)
      💡 Ejemplos reales: 1762787841, 1762787839, 1762787840


🔷 TABLA: album_genres
   Columnas: 6
   Filas: 99320
   ------------------------------------------------------------
   📌 artist (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !!!, $lum, "Blue" Gene Tyranny

   📌 album (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: !!!, THR!!!ER, The Long Walk

   📌 source (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: musicbrainz, discogs

   📌 genre (TEXT)
      🔑 PRIMARY KEY | ❗ NOT NULL
      💡 Ejemplos reales: Folk, World, & Country, Hip Hop, Rock

   📌 weight (REAL)
      📋 DEFAULT: 1.0
      💡 Ejemplos reales: 1.0, 2.0, 3.0

   📌 last_updated (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762801985, 1762802006, 1762801992


🔷 TABLA: group_stats
   Columnas: 10
   Filas: 0
   ------------------------------------------------------------
   📌 id (INTEGER)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 stat_type (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 stat_key (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 from_year (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 to_year (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 user_count (INTEGER)
      📋 DEFAULT: 0
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 total_scrobbles (INTEGER)
      📋 DEFAULT: 0
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 shared_by_users (TEXT)
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 data_json (TEXT)
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 created_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: listenbrainz_imports
   Columnas: 7
   Filas: 0
   ------------------------------------------------------------
   📌 id (INTEGER)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 listenbrainz_user (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 lastfm_user (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 last_import_timestamp (INTEGER)
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 total_imported (INTEGER)
      📋 DEFAULT: 0
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 created_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 updated_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: listenbrainz_file_imports
   Columnas: 7
   Filas: 136
   ------------------------------------------------------------
   📌 id (INTEGER)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: 1, 2, 6

   📌 source_directory (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: /home/huan/Descargas

   📌 lastfm_user (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: paqueradejere

   📌 file_path (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: listens/2023/1.jsonl, listens/2025/1.jsonl, listens/2024/1.jsonl

   📌 file_mtime (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762948944, 1762948998, 1762948962

   📌 listens_imported (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 25, 40, 3

   📌 created_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1762954117, 1762954119, 1762954116


🔷 TABLA: import_errors
   Columnas: 7
   Filas: 0
   ------------------------------------------------------------
   📌 id (INTEGER)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 file_path (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 line_number (INTEGER)
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 error_type (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 error_message (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 raw_data (TEXT)
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 created_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: sqlite_stat1
   Columnas: 3
   Filas: 46
   ------------------------------------------------------------
   📌 tbl ()
      💡 Ejemplos reales: artist_details, artist_genres_detailed, album_details

   📌 idx ()
      💡 Ejemplos reales: idx_album_genres_artist_album, idx_file_imports_path, sqlite_autoindex_listenbrainz_file_imports_1

   📌 stat ()
      💡 Ejemplos reales: 266269 7 5, 51721 4 2, 136 136 136 1


🔷 TABLA: sqlite_stat4
   Columnas: 6
   Filas: 1050
   ------------------------------------------------------------
   📌 tbl ()
      💡 Ejemplos reales: artist_details, listenbrainz_file_imports, album_genres

   📌 idx ()
      💡 Ejemplos reales: sqlite_autoindex_listenbrainz_file_imports_1, idx_file_imports_path, idx_album_genres_artist_album

   📌 neq ()
      💡 Ejemplos reales: 136 1 1, 41 7 1, 47 9 1

   📌 nlt ()
      💡 Ejemplos reales: 0 31 31, 0 61 61, 0 2 2

   📌 ndlt ()
      💡 Ejemplos reales: 0 47 47, 0 36 36, 0 15 15

   📌 sample ()
      💡 Ejemplos reales: b'\x0457\x01/home/huan/Descargaslistens/2019/11.jsonl\x1a', b'\x0455\x01/home/huan/Descargaslistens/2014/3.jsonl=', b'\x0455\x01/home/huan/Descargaslistens/2015/9.jsonl\x7f'


🔷 TABLA: user_first_artist_listen
   Columnas: 3
   Filas: 0
   ------------------------------------------------------------
   📌 user (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 artist (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 first_timestamp (INTEGER)
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: user_first_album_listen
   Columnas: 4
   Filas: 0
   ------------------------------------------------------------
   📌 user (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 artist (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 album (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 first_timestamp (INTEGER)
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: user_first_track_listen
   Columnas: 4
   Filas: 0
   ------------------------------------------------------------
   📌 user (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 artist (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 track (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 first_timestamp (INTEGER)
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: user_first_label_listen
   Columnas: 3
   Filas: 0
   ------------------------------------------------------------
   📌 user (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 label (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: (sin datos en la tabla)

   📌 first_timestamp (INTEGER)
      💡 Ejemplos reales: (sin datos en la tabla)


🔷 TABLA: cache_responses
   Columnas: 4
   Filas: 184248
   ------------------------------------------------------------
   📌 cache_key (TEXT)
      🔑 PRIMARY KEY
      💡 Ejemplos reales: album_enrich_v2_!!!_Louden Up Now, album_enrich_v2_!!!_Slyd, album_enrich_v2_!!!_Let It Be Blue

   📌 response_data (TEXT)
      ❗ NOT NULL
      💡 Ejemplos reales: {"processed": true}

   📌 created_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1763232955, 1763232954, 1763232953

   📌 expires_at (INTEGER)
      ❗ NOT NULL
      💡 Ejemplos reales: 1763319353, 1763319355, 1763319454


💾 ¿Deseas exportar el schema a un archivo JSON? (s/n): 
✨ ¡Proceso completado!
