import sqlite3

DB_PATH = "lastfm_cache.db"  # Cambia esto

def get_missing_summary(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Obtener todas las tablas del esquema (ignorando las internas de SQLite)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]

    resumen = {}

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table});")
        columns = [col[1] for col in cursor.fetchall()]

        resumen[table] = {}
        for col in columns:
            query = f"""
                SELECT COUNT(*) FROM {table}
                WHERE {col} IS NULL OR TRIM({col}) = '';
            """
            cursor.execute(query)
            count = cursor.fetchone()[0]
            if count > 0:
                resumen[table][col] = count

    conn.close()
    return resumen


if __name__ == "__main__":
    resumen = get_missing_summary(DB_PATH)

    for tabla, columnas in resumen.items():
        print(f"\nTabla: {tabla}")
        if not columnas:
            print("  ✓ Sin huecos.")
        else:
            for col, count in columnas.items():
                print(f"  - {col}: {count} valores vacíos o nulos")
