import sqlite3, os

db_path = os.path.join(os.path.dirname(__file__), "database.db")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS patients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    documento   TEXT UNIQUE NOT NULL,
    telefono    TEXT,
    empresa     TEXT,
    arl         TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consultations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER REFERENCES patients(id),
    fecha         TEXT NOT NULL,
    tipo          TEXT,
    numero_sesion INTEGER,
    estado        TEXT DEFAULT 'pendiente',
    audio_path    TEXT,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transcriptions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    consultation_id   INTEGER REFERENCES consultations(id),
    texto_raw         TEXT,
    texto_limpio      TEXT,
    speakers_json     TEXT,
    duracion_segundos INTEGER,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS extracted_data (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    consultation_id   INTEGER REFERENCES consultations(id),
    fuente            TEXT,
    datos_json        TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    consultation_id   INTEGER REFERENCES consultations(id),
    tipo              TEXT,
    contenido_json    TEXT,
    pdf_path          TEXT,
    docx_path         TEXT,
    aprobado          INTEGER DEFAULT 0,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
conn.close()
print("✅ Base de datos lista:", db_path)
