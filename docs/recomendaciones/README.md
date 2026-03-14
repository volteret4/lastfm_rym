# MusicCircle — Sistema de Recomendación Musical para Grupo de Amigos

## Visión General

Aplicación web que genera recomendaciones musicales personalizadas para un grupo de amigos, basándose en sus historiales de escucha de Last.fm (scrobbles) almacenados en una base de datos SQLite. La aplicación combina **42 motores de recomendación** diferentes que cruzan datos internos del grupo, APIs externas y análisis de patrones temporales.

**Filosofía**: No hay UN algoritmo correcto. Se implementan TODOS los motores, cada uno genera candidatos con un score, y el sistema los combina. Con el tiempo iremos desactivando/ponderando según resultados reales.

## Arquitectura

```
proyecto/
├── db/
│   └── lastfm_cache_rym_new_normalized.db    # SQLite existente (no modificar estructura original)
├── scripts/
│   ├── generate_recommendations.py           # Script principal: ejecuta todos los motores
│   ├── engines/                              # Un archivo por motor o grupo de motores
│   │   ├── __init__.py
│   │   ├── collaborative.py                  # Motores 1, 5, 6, 7, 10
│   │   ├── genre_bridge.py                   # Motores 2, 14, 26, 29, 30
│   │   ├── discovery_chains.py               # Motores 3, 9, 21, 23, 24, 25, 40
│   │   ├── trending.py                       # Motor 4
│   │   ├── discography.py                    # Motores 8, 39
│   │   ├── external_similarity.py            # Motores 11, 12, 13, 15 (requiere tabla artist_similarities)
│   │   ├── graph_relations.py                # Motores 16, 17, 19, 20
│   │   ├── label_producer.py                 # Motores 18, 19
│   │   ├── temporal.py                       # Motores 22, 31, 37
│   │   ├── ratings.py                        # Motores 27, 28
│   │   ├── computed.py                       # Motores 32, 33, 34, 35, 36, 38
│   │   ├── narrative.py                      # Motores 41, 42
│   │   └── base.py                           # Clase base RecommendationEngine
│   ├── enrichment/                           # Scripts para poblar datos externos
│   │   ├── fetch_lastfm_similar.py           # Poblar artist_similarities desde LastFM API
│   │   ├── fetch_lastfm_tags.py              # Enriquecer tags/géneros desde LastFM
│   │   ├── fetch_musicbrainz_relations.py    # Relaciones de MB (influencias, miembros, etc.)
│   │   ├── fetch_discogs_styles.py           # Estilos granulares de Discogs
│   │   └── fetch_listenbrainz.py             # Datos de ListenBrainz
│   ├── precompute/                           # Pre-cálculos pesados
│   │   ├── user_profiles.py                  # Perfiles de usuario (géneros, décadas, diversidad, etc.)
│   │   ├── similarity_matrix.py              # Matriz de similitud entre usuarios
│   │   ├── session_clusters.py               # Detección de sesiones de escucha
│   │   ├── artist_embeddings.py              # Artist2Vec desde sesiones
│   │   ├── transition_matrix.py              # Cadenas de Markov artista→artista
│   │   └── loyalty_scores.py                 # Loyalty, engagement, skip detection
│   └── utils/
│       ├── db.py                             # Conexión SQLite y helpers
│       ├── scoring.py                        # Normalización y combinación de scores
│       └── constants.py                      # Pesos, umbrales, configuración
├── output/                                   # Generado por los scripts de Python
│   ├── recommendations/
│   │   ├── {username}.json                   # Recomendaciones finales por usuario
│   │   └── meta.json                         # Metadata: cuándo se generó, motores activos, etc.
│   ├── profiles/
│   │   ├── {username}.json                   # Perfil computado del usuario
│   │   └── similarity_matrix.json            # Similitudes entre usuarios
│   ├── precomputed/
│   │   ├── sessions.json                     # Sesiones detectadas por usuario
│   │   ├── artist_clusters.json              # Clusters de artistas por co-escucha
│   │   ├── transition_matrix.json            # Matriz de transición
│   │   └── artist_embeddings.json            # Embeddings (si se computan)
│   └── stats/
│       ├── group_overview.json               # Estadísticas generales del grupo
│       └── engine_diagnostics.json           # Cuántos candidatos generó cada motor, scores, etc.
├── web/
│   ├── index.html                            # SPA principal
│   ├── css/
│   │   └── styles.css
│   ├── js/
│   │   ├── app.js                            # Lógica principal, carga de JSONs, routing
│   │   ├── views/
│   │   │   ├── home.js                       # Selector de usuario
│   │   │   ├── recommendations.js            # Vista principal de recomendaciones
│   │   │   ├── profile.js                    # Perfil/estadísticas del usuario
│   │   │   ├── compare.js                    # Comparación entre 2 usuarios
│   │   │   └── explorer.js                   # Explorador libre: por género, década, sello...
│   │   └── components/
│   │       ├── artist-card.js                # Tarjeta de artista recomendado con "porqué"
│   │       ├── engine-badge.js               # Badge visual por motor
│   │       ├── filters.js                    # Panel de filtros
│   │       └── charts.js                     # Gráficos (Chart.js o similar vía CDN)
│   └── data/ -> ../output/                   # Symlink o copiar JSONs aquí
└── README.md                                 # Este archivo
```

## Base de Datos

### SQLite existente: `lastfm_cache_rym_new_normalized.db`

**NO modificar tablas existentes.** Solo AÑADIR tablas nuevas.

#### Tablas existentes relevantes

- **users**: id, username
- **artists**: id, name, mbid, country, formed_year, artist_type, listeners, playcount, + URLs a Spotify, YouTube, Discogs, Bandcamp, RYM, Wikipedia, MusicBrainz
- **albums**: id, name, artist_id, year, originalyear, album_type, label, total_tracks, + URLs + ratings (scaruffi_rating, aoty_user_score, aoty_critic_score, metacritic_score)
- **album_metadata**: album_id, producers, engineers, credits, descripciones, wikipedia_content
- **tracks**: id, name, artist_id, album_id, duration_ms, track_number
- **genres**: id, name, source
- **album_genres**: album_id, genre_id, weight
- **artist_genres**: artist_id, genre_id, weight
- **user_first_artist_listen**: user_id, artist_id, first_timestamp
- **user_first_album_listen**: user_id, album_id, first_timestamp
- **user_first_track_listen**: user_id, track_id, first_timestamp
- **user_first_label_listen**: user_id, label, first_timestamp
- **group_stats**: stat_type, stat_key, from_year, to_year, user_count, total_scrobbles, shared_by_users, data_json
- **scrobbles\_{username}**: id, artist_id, track_id, album_id, timestamp — UNA TABLA POR USUARIO:
  - scrobbles_eliasj72
  - scrobbles_frikomid
  - scrobbles_gabredmared
  - scrobbles_lonsonxd
  - scrobbles_nubis84
  - scrobbles_rocky_stereo
  - scrobbles_alberto_gu
  - scrobbles_paqueradejere
  - scrobbles_sdecandelario
  - scrobbles_bipolarmuzik
  - scrobbles_verygooood

**Nota importante**: cada usuario tiene su propia tabla de scrobbles. Para queries que comparan usuarios hay que hacer UNION o iterar por tablas. Crear un helper en `utils/db.py` que abstraiga esto:

```python
def get_all_scrobble_tables(conn) -> list[tuple[str, str]]:
    """Devuelve [(username, table_name), ...] para todas las tablas de scrobbles."""
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'scrobbles_%'")
    tables = []
    for (table_name,) in cursor:
        username = table_name.replace('scrobbles_', '')
        tables.append((username, table_name))
    return tables

def get_user_scrobbles_query(username: str) -> str:
    """Devuelve el nombre de tabla de scrobbles para un usuario."""
    return f'scrobbles_{username}'
```

#### Tablas NUEVAS a crear (scripts de enrichment las poblan)

```sql
-- Similitudes entre artistas (LastFM artist.getSimilar)
CREATE TABLE IF NOT EXISTS artist_similarities (
    artist_id INTEGER NOT NULL,
    similar_artist_id INTEGER NOT NULL,
    match_score REAL NOT NULL,       -- 0.0 a 1.0, viene de LastFM
    source TEXT DEFAULT 'lastfm',    -- 'lastfm', 'computed', 'musicbrainz'
    last_updated INTEGER,
    PRIMARY KEY (artist_id, similar_artist_id, source)
);

-- Relaciones entre artistas (MusicBrainz)
CREATE TABLE IF NOT EXISTS artist_relations (
    artist_id INTEGER NOT NULL,
    related_artist_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL,      -- 'member_of', 'collaborated_with', 'influenced_by',
                                      -- 'influenced', 'producer', 'remix', 'tribute', 'cover'
    direction TEXT,                    -- 'forward', 'backward'
    attributes TEXT,                   -- JSON con datos extra
    source TEXT DEFAULT 'musicbrainz',
    PRIMARY KEY (artist_id, related_artist_id, relation_type)
);

-- Tags extendidos de LastFM (más granulares que artist_genres)
CREATE TABLE IF NOT EXISTS artist_tags_lastfm (
    artist_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    count INTEGER DEFAULT 0,          -- peso del tag en LastFM (0-100)
    PRIMARY KEY (artist_id, tag)
);

-- Estilos de Discogs (taxonomía diferente)
CREATE TABLE IF NOT EXISTS artist_styles_discogs (
    artist_id INTEGER NOT NULL,
    style TEXT NOT NULL,
    PRIMARY KEY (artist_id, style)
);

-- Datos pre-computados por usuario (evitar recalcular)
CREATE TABLE IF NOT EXISTS user_computed_profiles (
    user_id INTEGER NOT NULL,
    profile_type TEXT NOT NULL,        -- 'genre_distribution', 'decade_distribution',
                                       -- 'diversity_index', 'loyalty_scores', etc.
    data_json TEXT NOT NULL,
    computed_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, profile_type)
);

-- Sesiones de escucha detectadas
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    start_timestamp INTEGER NOT NULL,
    end_timestamp INTEGER NOT NULL,
    track_count INTEGER,
    artist_ids TEXT,                    -- JSON array de artist_ids en la sesión
    album_ids TEXT,                     -- JSON array de album_ids
    genre_ids TEXT,                     -- JSON array de genre_ids dominantes
    session_type TEXT                   -- 'single_artist', 'single_album', 'genre_focused', 'mixed'
);

-- Caché de recomendaciones generadas
CREATE TABLE IF NOT EXISTS recommendation_cache (
    user_id INTEGER NOT NULL,
    engine_id TEXT NOT NULL,           -- 'motor_01', 'motor_02', etc.
    artist_id INTEGER NOT NULL,
    score REAL NOT NULL,
    explanation TEXT,                   -- Texto explicativo de por qué se recomienda
    metadata_json TEXT,                 -- Datos extra del motor (amigos que lo escuchan, etc.)
    generated_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, engine_id, artist_id)
);

-- Score final combinado
CREATE TABLE IF NOT EXISTS recommendations_final (
    user_id INTEGER NOT NULL,
    artist_id INTEGER NOT NULL,
    final_score REAL NOT NULL,
    engine_scores TEXT NOT NULL,        -- JSON: {"motor_01": 0.8, "motor_05": 0.6, ...}
    explanation TEXT NOT NULL,          -- Explicación narrativa combinada
    category TEXT,                      -- 'high_confidence', 'adventurous', 'deep_cut', 'trending'
    generated_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, artist_id)
);
```

## Los 42 Motores de Recomendación

Cada motor es una clase que hereda de `RecommendationEngine` y produce una lista de `(artist_id, score, explanation, metadata)`.

### Clase base

```python
# scripts/engines/base.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Recommendation:
    artist_id: int
    score: float              # 0.0 - 1.0 normalizado
    explanation: str           # Texto legible para el usuario
    metadata: dict             # Datos extra para debug/UI
    engine_id: str

class RecommendationEngine:
    engine_id: str = ""
    engine_name: str = ""
    description: str = ""
    requires_external_data: bool = False   # True si necesita tablas de enrichment
    requires_precompute: bool = False      # True si necesita pre-cálculos

    def __init__(self, db_conn, target_user_id: int):
        self.conn = db_conn
        self.target_user_id = target_user_id

    def is_ready(self) -> bool:
        """Comprueba si los datos necesarios están disponibles."""
        return True

    def generate(self) -> list[Recommendation]:
        """Genera las recomendaciones. Cada subclase implementa esto."""
        raise NotImplementedError

    def get_user_artists(self, user_id: int) -> set[int]:
        """Helper: devuelve set de artist_ids que ha escuchado un usuario."""
        # Implementar usando la tabla de scrobbles del usuario
        pass
```

### Especificación de cada motor

#### BLOQUE A: Basados en el grupo de amigos

**Motor 01 — Collaborative Filtering Directo** (`collaborative.py`)

- engine_id: `collab_direct`
- Lógica: Para el usuario target, buscar artistas que escuchan otros usuarios pero target no. Ponderar por: (1) similitud de gustos entre target y el otro usuario, (2) intensidad de escucha del otro usuario para ese artista (scrobbles), (3) número de usuarios del grupo que lo escuchan.
- Score: `sum(similarity_with_friend * friend_scrobble_intensity * friend_count_factor)`
- Datos: Solo tablas de scrobbles + artistas. No requiere datos externos.
- Explicación ejemplo: "Lo escuchan 5 de tus amigos. frikomid tiene 234 scrobbles y es tu perfil más similar."

**Motor 02 — Puente de Géneros Adyacentes** (`genre_bridge.py`)

- engine_id: `genre_bridge`
- Lógica: Identificar géneros que target y un amigo comparten con peso alto. Luego, buscar géneros que ESE amigo escucha mucho pero target apenas toca (géneros "adyacentes"). Recomendar los artistas top del amigo en esos géneros adyacentes.
- Score: `shared_genre_weight * friend_adjacent_genre_intensity * artist_scrobbles_norm`
- Datos: artist_genres, album_genres, scrobbles.
- Explicación: "Tú y lonsonxd compartís mucho shoegaze. Él también escucha mucho dream pop y este artista es su favorito de ese género."

**Motor 03 — Cadena de Descubrimiento** (`discovery_chains.py`)

- engine_id: `discovery_chain`
- Lógica: Usando `user_first_artist_listen`, construir secuencias de descubrimiento por usuario. Buscar patrones comunes: si 3+ usuarios descubrieron Artista B en los 60 días siguientes a descubrir Artista A, y target escucha A pero no B → recomendar B.
- Score: `count_users_with_pattern / total_users * temporal_proximity_factor`
- Datos: user_first_artist_listen, scrobbles.
- Explicación: "4 de tus amigos descubrieron este artista poco después de empezar a escuchar [Artista X], que tú escuchas."

**Motor 04 — Trending en el Grupo** (`trending.py`)

- engine_id: `trending_group`
- Lógica: Detectar artistas con un spike de scrobbles en las últimas 2-4 semanas respecto a su media histórica para un usuario. Si el spike es significativo y target no lo escucha → recomendar.
- Score: `spike_ratio * recency_factor`
- Datos: scrobbles (con timestamps recientes).
- Explicación: "rocky_stereo está obsesionado con este artista últimamente: 87 scrobbles en las últimas 2 semanas vs su media de 5."

**Motor 05 — Gemelo Musical** (`collaborative.py`)

- engine_id: `musical_twin`
- Lógica: Calcular similitud comprehensiva entre target y cada usuario (Jaccard de artistas, coseno de distribución de géneros, overlap de sesiones). Identificar el "gemelo" (más similar). Recomendar todo lo que el gemelo escucha mucho y target no.
- Score: `twin_similarity * twin_scrobbles_for_artist_norm`
- Explicación: "Tu gemelo musical es frikomid (82% de compatibilidad). Este es su artista #3 más escuchado y tú aún no lo conoces."

**Motor 06 — Anti-burbuja Grupal** (`collaborative.py`)

- engine_id: `anti_bubble`
- Lógica: Artistas que SOLO escucha 1 miembro del grupo. Son los más únicos. Recomendar selectivamente basándose en match de géneros con target.
- Score: `genre_compatibility_with_target * uniqueness_factor * scrobble_intensity`
- Explicación: "Solo bipolarmuzik escucha este artista en todo el grupo. Encaja con tu gusto por el post-punk."

**Motor 07 — Escucha Sincronizada** (`collaborative.py`)

- engine_id: `sync_listen`
- Lógica: Detectar cuando 2+ usuarios escucharon al mismo artista en la misma ventana de 48h. Estos patrones revelan "momentos compartidos" (probablemente se recomendaron algo). Cruzar el resto de escuchas de esos usuarios en esa ventana temporal.
- Score: `sync_frequency * involved_users_similarity`
- Explicación: "Tú y alberto_gu escuchasteis a [Artista X] el mismo día 3 veces. Él también escuchó a este artista esos días."

**Motor 08 — Profundización de Discografía** (`discography.py`)

- engine_id: `deep_discography`
- Lógica: Para artistas que target ya escucha, buscar álbumes específicos que sus amigos escuchan mucho y target no ha tocado (0 scrobbles de tracks de ese álbum).
- Score: `friends_album_scrobbles * album_rating_factor`
- Output: NO recomienda artistas nuevos, sino álbumes de artistas conocidos.
- Explicación: "Escuchas a Radiohead pero no has tocado 'Amnesiac'. frikomid y nubis84 tienen 150+ scrobbles de ese álbum."

**Motor 09 — Herencia de Gustos** (`discovery_chains.py`)

- engine_id: `taste_inheritance`
- Lógica: Si un amigo dejó de escuchar un artista (mucho hace 1 año, nada en 6 meses) y target está empezando a escucharlo ahora → target podría estar en la misma "trayectoria". Recomendar lo que el amigo escuchó DESPUÉS de su fase con ese artista.
- Score: `trajectory_match * post_phase_artist_quality`
- Explicación: "lonsonxd tuvo una fase de Sonic Youth hace 2 años y después descubrió estos artistas. Tú estás en tu fase de Sonic Youth ahora."

**Motor 10 — Consenso del Grupo** (`collaborative.py`)

- engine_id: `group_consensus`
- Lógica: Artistas que escuchan 5+ de los 11 miembros del grupo pero target no. Umbral alto de consenso.
- Score: `(user_count / total_users) * avg_scrobbles_across_users`
- Explicación: "8 de 11 del grupo escuchan a este artista. Puede que te estés perdiendo algo."

#### BLOQUE B: Basados en similitudes externas

**Motor 11 — Similar Artists Cruzado con Grupo** (`external_similarity.py`)

- engine_id: `similar_cross_group`
- Lógica: Para artistas top de target, obtener sus similares de LastFM. Filtrar los que un amigo escucha mucho. Doble señal: similar algorítmico + validado por humano del grupo.
- Score: `lastfm_match_score * friend_scrobble_intensity * friend_similarity`
- Requiere: tabla `artist_similarities` poblada.
- Explicación: "Similar a [Artista X] que escuchas mucho, y además frikomid lo tiene en su top 20."

**Motor 12 — Similar Transitivo (distancia 2)** (`external_similarity.py`)

- engine_id: `similar_transitive`
- Lógica: Similar de similar. A→B→C donde A es un artista de target y C lo escucha alguien del grupo. Más arriesgado pero descubre cosas más lejanas.
- Score: `match_score_A_B * match_score_B_C * group_validation * decay_factor`
- Requiere: tabla `artist_similarities`.
- Explicación: "A dos saltos de [Artista X]: similar a [B], que es similar a este artista. nubis84 lo valida con 89 scrobbles."

**Motor 13 — Tags como Vector de Perfil** (`external_similarity.py`)

- engine_id: `tag_profile_match`
- Lógica: Obtener top tags de LastFM por artista. Construir perfil de tags del usuario (ponderado por scrobbles). Recomendar artistas cuyos tags tienen alto coseno similarity con el perfil pero que no ha escuchado.
- Score: `cosine_similarity(user_tag_profile, artist_tag_profile)`
- Requiere: tabla `artist_tags_lastfm`.

**Motor 14 — Top Artists por Tag** (`genre_bridge.py`)

- engine_id: `tag_top_artists`
- Lógica: Para cada tag relevante del perfil del usuario, consultar LastFM `tag.getTopArtists`. Recomendar los que no conoce.
- Score: `tag_weight_in_profile * artist_rank_in_tag`
- Puede hacerse via API en tiempo de generación o pre-cacheando.

**Motor 15 — Track-level Similarity** (`external_similarity.py`)

- engine_id: `track_similarity`
- Lógica: Para los tracks más escuchados del target, usar `track.getSimilar` de LastFM. Extraer artistas de esos tracks similares.
- Score: `track_scrobble_count * track_similarity_match`
- Granularidad más fina que artista.

#### BLOQUE C: Basados en grafos y relaciones

**Motor 16 — Grafo de Colaboraciones** (`graph_relations.py`)

- engine_id: `collaboration_graph`
- Lógica: Desde MusicBrainz, obtener relaciones (collaborations, guest appearances, "recorded with"). Si target escucha A y A colaboró con B → recomendar B.
- Score: `collaboration_strength * genre_compatibility`
- Requiere: tabla `artist_relations`.
- Explicación: "Este artista colaboró con [X] en 3 álbumes. Tú escuchas mucho a [X]."

**Motor 17 — Árbol de Influencias** (`graph_relations.py`)

- engine_id: `influence_tree`
- Lógica: Relaciones "influenced by" de MusicBrainz/Wikidata. Recomendar influencias de artistas que escucha (ir atrás en el tiempo) o artistas influenciados (ir adelante).
- Score: `influence_direction_weight * genre_match`
- Explicación: "Este artista fue una influencia directa de [X], al que escuchas mucho."

**Motor 18 — Sello Discográfico** (`label_producer.py`)

- engine_id: `label_curator`
- Lógica: Calcular afinidad del usuario con sellos discográficos (`albums.label`). Para sellos con alta afinidad, recomendar otros artistas del sello que no conoce.
- Score: `label_affinity * artist_quality_in_label`
- Datos: albums.label — ya disponible, no necesita API.
- Explicación: "Escuchas 7 artistas de 4AD. Este es otro artista del sello que no conoces."

**Motor 19 — Productores/Ingenieros Compartidos** (`label_producer.py`)

- engine_id: `shared_producers`
- Lógica: `album_metadata.producers` y `album_metadata.engineers`. Si te gustan 3+ álbumes de un mismo productor, recomendar otros álbumes/artistas que produjo.
- Score: `producer_affinity * album_rating`
- Datos: album_metadata — ya disponible.
- Explicación: "Te gustan 4 álbumes producidos por Steve Albini. Este artista también fue producido por él."

**Motor 20 — Red de Miembros** (`graph_relations.py`)

- engine_id: `member_network`
- Lógica: `artists.member_of` (ya en DB) + relaciones de MusicBrainz. Si te gusta banda X, recomendar proyectos solistas de miembros. Si te gustan 2 proyectos solistas de miembros de la misma banda, recomendar la banda.
- Score: `member_overlap * project_quality`
- Explicación: "El guitarrista de [X] tiene este proyecto paralelo."

#### BLOQUE D: Basados en patrones temporales

**Motor 21 — Detector de Rabbit Holes** (`discovery_chains.py`)

- engine_id: `rabbit_hole`
- Lógica: Detectar ventanas de 7-14 días donde un usuario descubrió 3+ artistas nuevos del mismo género. Recomendar esos rabbit holes completos a usuarios compatibles.
- Score: `genre_match * rabbit_hole_depth * rabbit_hole_quality`
- Explicación: "Tu amigo sdecandelario se metió en un rabbit hole de krautrock en marzo. Descubrió estos 6 artistas en orden."

**Motor 22 — Estacionalidad** (`temporal.py`)

- engine_id: `seasonal`
- Lógica: Analizar distribución de scrobbles por mes del año para cada artista en el grupo. Detectar artistas con picos estacionales. Recomendar según época actual.
- Score: `seasonal_peak_current_month * genre_match`
- Explicación: "El grupo tiende a escuchar más a este artista en verano. Puede ser buen momento."

**Motor 23 — Ritmo de Adopción** (`discovery_chains.py`)

- engine_id: `adoption_pace`
- Lógica: Clasificar usuarios como early adopters (descubren antes) vs followers (descubren después). Para early adopters: recomendar lo más nicho. Para followers: recomendar lo que los early adopters descubrieron hace 2-3 meses.
- Score: depende del tipo de usuario.

**Motor 24 — Ciclos de Re-descubrimiento** (`discovery_chains.py`)

- engine_id: `rediscovery_cycle`
- Lógica: Artistas que un amigo escuchó, dejó, y volvió a escuchar. Estos "retornos" son señal de gusto profundo. Peso extra si lo hizo más de una vez.
- Score: `return_count * return_intensity * genre_match_with_target`

**Motor 25 — Velocidad de Enganche** (`discovery_chains.py`)

- engine_id: `hook_speed`
- Lógica: Scrobbles en los primeros 7 días tras descubrir un artista. Los artistas con "enganche rápido" en amigos compatibles son mejores candidatos.
- Score: `first_week_scrobbles / avg_first_week * friend_similarity`

**Motor 40 — Linaje Musical** (`discovery_chains.py`)

- engine_id: `musical_lineage`
- Lógica: Construir cadenas reales de descubrimiento de amigos. Si un amigo descubrió A→B→C→D en ese orden y target escucha A y B pero no C ni D, recomendar C como siguiente paso.
- Score: `chain_length * chain_users * position_in_chain`
- Explicación: "frikomid recorrió este camino: Joy Division → Bauhaus → Siouxsie → este artista. Tú ya escuchas los dos primeros."

#### BLOQUE E: Basados en taxonomías y ratings

**Motor 26 — Taxonomía Granular de Discogs** (`genre_bridge.py`)

- engine_id: `discogs_styles`
- Lógica: Estilos de Discogs (mucho más específicos: "Italo-Disco", "EBM", "Zolo"). Matching por estilos específicos.
- Requiere: tabla `artist_styles_discogs`.

**Motor 27 — Ratings como Curador** (`ratings.py`)

- engine_id: `rating_curator`
- Lógica: Analizar correlación entre ratings (Scaruffi, AOTY, Metacritic) y scrobbles del usuario. Si hay correlación positiva con Scaruffi → recomendar artistas bien valorados por Scaruffi en géneros compatibles.
- Score: `rating_correlation * rating_value * genre_match`
- Datos: ya disponibles en albums.
- Explicación: "Tus álbumes favoritos coinciden mucho con los gustos de Scaruffi. Él da un 8/10 a este álbum de un género que escuchas."

**Motor 28 — Disonancia Crítica** (`ratings.py`)

- engine_id: `critical_dissonance`
- Lógica: Artistas donde aoty_critic_score >> aoty_user_score (infravalorados por el público) o viceversa. Ofrecer "hidden gems" según el perfil.
- Score: `abs(critic - user_score) * genre_match`

**Motor 29 — Exploración por Década** (`genre_bridge.py`)

- engine_id: `decade_explorer`
- Lógica: Distribución de escuchas por década del usuario. Recomendar artistas de su década preferida que no conoce. También: "¿y si exploras los 70s?" si escucha 80s.
- Score: `decade_preference * artist_quality_in_decade`

**Motor 30 — País de Origen** (`genre_bridge.py`)

- engine_id: `country_affinity`
- Lógica: `artists.country`. Detectar afinidades geográficas implícitas (ej: escucha mucho música japonesa sin saberlo). Recomendar más de ese país.
- Score: `country_scrobble_ratio * genre_match`
- Explicación: "El 15% de tus escuchas son de artistas japoneses. Aquí hay más que podrían gustarte."

#### BLOQUE F: Señales implícitas y computadas

**Motor 31 — Skip Detection** (`temporal.py`)

- engine_id: `skip_aware`
- Lógica: Si `timestamp[n+1] - timestamp[n] < duration_ms[n] * 0.5` → probable skip. Tracks completados pesan más en el perfil. Recalcular perfil real del usuario excluyendo skips.
- Efecto: Modifica los scores de otros motores más que generar recomendaciones propias.

**Motor 32 — Loyalty Score** (`computed.py`)

- engine_id: `loyalty_based`
- Lógica: Artistas escuchados en 6+ meses distintos = alta lealtad. Géneros con alta lealtad definen el "core" real del usuario (no las modas pasajeras).
- Efecto: Alimenta perfiles de usuario para otros motores.

**Motor 33 — Índice de Diversidad** (`computed.py`)

- engine_id: `diversity_calibrated`
- Lógica: Shannon entropy de la distribución de artistas/géneros del usuario. Alta diversidad → recomendaciones más arriesgadas. Baja diversidad → recomendaciones seguras.
- Efecto: Modula el riesgo de las recomendaciones de otros motores.

**Motor 34 — Clustering por Co-escucha** (`computed.py`)

- engine_id: `colistening_cluster`
- Lógica: Grafo donde dos artistas se conectan si aparecen juntos frecuentemente en sesiones del grupo. Community detection (Louvain o similar) para encontrar clusters. Recomendar artistas del mismo cluster.
- Score: `cluster_cohesion * artist_centrality_in_cluster`
- Librería sugerida: `networkx` con `community` (Louvain).
- Explicación: "Este artista aparece en el mismo cluster de escucha que [X], [Y] y [Z], que tú escuchas."

**Motor 35 — Artist2Vec Embeddings** (`computed.py`)

- engine_id: `artist2vec`
- Lógica: Tratar sesiones como frases, artistas como palabras. Entrenar Word2Vec (gensim). Artistas cercanos en el espacio son similares por comportamiento real.
- Score: `cosine_similarity(target_artist_embedding, candidate_embedding)`
- Librería: `gensim`.
- Requiere: pre-cálculo de sesiones y entrenamiento del modelo.

**Motor 36 — Matriz de Transición** (`computed.py`)

- engine_id: `markov_transition`
- Lógica: ¿Después de escuchar artista A, qué artista suele poner el grupo? Cadena de Markov. Si target escucha A y la transición más probable es B → recomendar B.
- Score: `transition_probability * group_frequency`
- Explicación: "Cuando alguien del grupo escucha a [X], suele poner a este artista después."

**Motor 37 — Guilty Pleasures** (`temporal.py`)

- engine_id: `guilty_pleasure`
- Lógica: Artistas escuchados en horarios inusuales (3-6 AM) o en sesiones aisladas (1-2 tracks sin contexto de sesión larga). Pueden revelar gustos ocultos de amigos.
- Score: `unusual_time_ratio * isolated_session_ratio`

**Motor 38 — Perfil de Duración/Energía** (`computed.py`)

- engine_id: `duration_energy`
- Lógica: Usar `tracks.duration_ms` como proxy de energía/estilo (tracks cortos ~punk, largos ~prog/ambient). Calcular perfil de duración del usuario y recomendar artistas con perfil similar.
- Score: `duration_profile_similarity`

#### BLOQUE G: Sociales y narrativos

**Motor 39 — Completar la Colección** (`discography.py`)

- engine_id: `complete_collection`
- Lógica: Si escuchas 4 de 5 artistas clave de un movimiento/escena/sello, recomendar el quinto. Usar clusters de género + época + país para detectar "escenas".
- Score: `completion_ratio * scene_cohesion`
- Explicación: "Escuchas a 4 de las 5 bandas clave del shoegaze de Thames Valley. Solo te falta esta."

**Motor 41 — El Eslabón Perdido** (`narrative.py`)

- engine_id: `missing_link`
- Lógica: Dos usuarios comparten mucho pero difieren en un género. Buscar artistas que sean PUENTE entre ambos mundos (ej: mezcla de electrónica y jazz).
- Score: `bridge_genre_match * artist_hybrid_score`
- Explicación: "Tú escuchas mucho electrónica y lonsonxd escucha mucho jazz. Este artista mezcla ambos mundos."

**Motor 42 — Explicación Narrativa** (`narrative.py`)

- engine_id: `narrative`
- Lógica: NO es un motor de scoring propio. Es un post-procesador que toma las recomendaciones finales y genera explicaciones ricas combinando las razones de múltiples motores.
- Output: Texto narrativo para cada recomendación.
- Explicación: "Recomendado porque: (1) es similar a Joy Division que escuchas mucho, (2) 6 de tus amigos lo escuchan, (3) tu gemelo musical frikomid lo tiene en su top 10, y (4) encaja con tu rabbit hole reciente de post-punk."

## Sistema de Scoring

### Normalización

```python
# scripts/utils/scoring.py

def normalize_scores(recommendations: list[Recommendation]) -> list[Recommendation]:
    """Normaliza scores de un motor a rango [0, 1] usando min-max."""
    if not recommendations:
        return []
    scores = [r.score for r in recommendations]
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        for r in recommendations:
            r.score = 0.5
        return recommendations
    for r in recommendations:
        r.score = (r.score - min_s) / (max_s - min_s)
    return recommendations
```

### Combinación

```python
# Pesos por motor (configurables en constants.py)
ENGINE_WEIGHTS = {
    'collab_direct': 0.30,
    'musical_twin': 0.25,
    'group_consensus': 0.20,
    'similar_cross_group': 0.25,
    'genre_bridge': 0.20,
    'discovery_chain': 0.15,
    'trending_group': 0.15,
    'label_curator': 0.15,
    'colistening_cluster': 0.20,
    'markov_transition': 0.15,
    # ... etc para los 42 motores
    # Motores no implementados o sin datos: 0.0
}

# Score final:
# 1. Recoger todos los candidatos de todos los motores
# 2. Por artista, combinar: final_score = sum(engine_weight * engine_score) / sum(active_engine_weights)
# 3. Bonus por número de motores que lo recomiendan (multi-signal bonus)
# 4. Penalty si target ya tiene >5 scrobbles del artista (ya lo conoce un poco)
# 5. Diversity penalty: si ya hay 3 recomendaciones del mismo género en el top, penalizar la 4ª
```

## Output JSON — Formato para la Web

### `output/recommendations/{username}.json`

```json
{
  "user": {
    "id": 1,
    "username": "frikomid",
    "generated_at": "2025-01-15T10:30:00Z"
  },
  "recommendations": [
    {
      "rank": 1,
      "artist": {
        "id": 1234,
        "name": "Artista Ejemplo",
        "country": "GB",
        "formed_year": 1985,
        "genres": ["post-punk", "darkwave"],
        "cover_url": "https://...",
        "spotify_url": "https://...",
        "youtube_url": "https://...",
        "lastfm_url": "https://..."
      },
      "final_score": 0.87,
      "confidence": "high",
      "category": "high_confidence",
      "engines": {
        "collab_direct": {
          "score": 0.9,
          "explanation": "Lo escuchan 6 amigos..."
        },
        "musical_twin": {
          "score": 0.85,
          "explanation": "Tu gemelo nubis84 lo tiene en su top 5."
        },
        "similar_cross_group": {
          "score": 0.78,
          "explanation": "Similar a Joy Division."
        }
      },
      "explanation_short": "6 amigos lo escuchan, similar a lo que te gusta, validado por tu gemelo musical.",
      "explanation_full": "Texto narrativo largo del motor 42...",
      "recommended_album": {
        "id": 5678,
        "name": "Álbum para empezar",
        "year": 1987,
        "reason": "El más escuchado por tus amigos"
      },
      "friends_who_listen": [
        { "username": "nubis84", "scrobbles": 234 },
        { "username": "lonsonxd", "scrobbles": 156 }
      ]
    }
  ],
  "engine_stats": {
    "collab_direct": { "candidates": 450, "active": true },
    "artist2vec": {
      "candidates": 0,
      "active": false,
      "reason": "Modelo no entrenado aún"
    }
  }
}
```

### `output/profiles/{username}.json`

```json
{
  "username": "frikomid",
  "total_scrobbles": 45023,
  "unique_artists": 892,
  "unique_albums": 1456,
  "first_scrobble": "2018-03-15",
  "diversity_index": 0.72,
  "adopter_type": "early_adopter",
  "genre_distribution": [
    { "genre": "post-punk", "weight": 0.18, "scrobbles": 8104 },
    { "genre": "shoegaze", "weight": 0.12, "scrobbles": 5403 }
  ],
  "decade_distribution": [
    { "decade": "1980s", "weight": 0.35 },
    { "decade": "1990s", "weight": 0.28 }
  ],
  "country_distribution": [
    { "country": "GB", "weight": 0.42 },
    { "country": "US", "weight": 0.31 }
  ],
  "top_labels": [{ "label": "4AD", "scrobbles": 3200, "artists": 8 }],
  "musical_twin": "nubis84",
  "twin_similarity": 0.82,
  "core_artists": [
    {
      "artist_id": 100,
      "name": "Joy Division",
      "loyalty_score": 0.95,
      "total_scrobbles": 1200
    }
  ],
  "recent_discoveries": [
    {
      "artist_id": 500,
      "name": "Nuevo Artista",
      "first_listen": "2025-01-03",
      "scrobbles_since": 45
    }
  ]
}
```

## Web Frontend

### Tecnología

- HTML + CSS + Vanilla JS (sin frameworks, sin build step)
- Carga JSONs estáticos desde `output/` (o `web/data/` via symlink)
- Chart.js via CDN para gráficos
- Servir con `python -m http.server` desde `web/`

### Vistas

1. **Home / Selector de usuario**: Grid de avatares/nombres. Click → vista de recomendaciones.
2. **Recomendaciones**: Lista de artistas recomendados en tarjetas. Cada tarjeta muestra:
   - Nombre del artista, cover, links (Spotify, YouTube, LastFM)
   - Score de confianza (barra visual)
   - Badges de motores activos (iconos pequeños por cada motor que contribuyó)
   - Explicación corta visible, expandible a explicación larga
   - Amigos que lo escuchan (avatares pequeños)
   - Álbum recomendado para empezar
   - Filtros: por motor, por género, por década, por categoría (high confidence / adventurous / deep cut / trending)
3. **Perfil de usuario**: Estadísticas, gráficos de géneros/décadas/países, top artistas, diversidad, tipo de listener.
4. **Comparación**: Seleccionar 2 usuarios. Mostrar overlap, diferencias, gemelo score, recomendaciones cruzadas.
5. **Explorador**: Buscar por género, década, sello, país. Ver qué escucha el grupo en esa dimensión.

### Diseño

- Dark theme (contexto musical)
- Responsivo (funciona en móvil)
- Carga rápida (son JSONs estáticos)
- Colores por motor para identificar visualmente de dónde viene cada recomendación

## Plan de Ejecución

### Fase 1 — Fundación (sin APIs externas)

1. `utils/db.py` — helpers de base de datos
2. `precompute/user_profiles.py` — perfiles de usuario
3. `precompute/session_clusters.py` — detección de sesiones
4. `precompute/similarity_matrix.py` — similitud entre usuarios
5. Motores 1, 2, 4, 5, 6, 8, 10, 18, 19, 27, 29, 30, 31, 32, 33 (todos usando datos ya en DB)
6. `scoring.py` — combinación de scores
7. Generación de JSONs
8. Web básica funcional

### Fase 2 — Motores computados

9. `precompute/transition_matrix.py` — cadenas de Markov
10. `precompute/artist_embeddings.py` — Artist2Vec
11. Motores 3, 7, 9, 21, 22, 23, 24, 25, 34, 35, 36, 37, 38, 39, 40, 41
12. Motor 42 (narrativas)
13. Web con todas las vistas

### Fase 3 — Enriquecimiento externo

14. `enrichment/fetch_lastfm_similar.py` — poblar artist_similarities
15. `enrichment/fetch_lastfm_tags.py` — poblar artist_tags
16. `enrichment/fetch_musicbrainz_relations.py` — poblar artist_relations
17. `enrichment/fetch_discogs_styles.py` — poblar artist_styles
18. Motores 11, 12, 13, 14, 15, 16, 17, 20, 26
19. Web completa con filtros avanzados

### Fase 4 — Pulido

20. Ajuste de pesos según resultados
21. A/B testing informal con el grupo de amigos
22. Desactivar motores que no aporten
23. UI polish

## Dependencias Python

```
sqlite3          # stdlib
numpy
scipy            # para cosine similarity, etc.
networkx         # para grafos y community detection
python-louvain   # community detection (louvain)
gensim           # para Artist2Vec (Word2Vec)
requests         # para APIs externas
```

## Notas Técnicas

- **Timestamps**: Todos son Unix timestamps (seconds). Usar `datetime.fromtimestamp()`.
- **Scrobble tables**: Una por usuario. SIEMPRE usar el helper para iterar. NUNCA hardcodear nombres de tablas.
- **Género weights**: `album_genres.weight` y `artist_genres.weight` van de 0 a 1 (o más). Normalizar.
- **NULL handling**: Muchos campos pueden ser NULL (country, year, label, etc.). Siempre manejar.
- **Performance**: La DB puede tener cientos de miles de scrobbles. Usar índices, evitar N+1 queries. Pre-computar lo posible.
- **Idempotencia**: Los scripts de generación deben poder re-ejecutarse sin efectos secundarios. REPLACE INTO o DELETE+INSERT.
