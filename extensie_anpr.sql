-- Creează tabela pentru camere și zone
CREATE TABLE IF NOT EXISTS Camere (
    id_camera INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_camera TEXT UNIQUE NOT NULL,
    zona TEXT NOT NULL
);

-- Creează tabela pentru detecții ANPR
CREATE TABLE IF NOT EXISTS Detectii (
    id_detectie INTEGER PRIMARY KEY AUTOINCREMENT,
    numar_inmatriculare TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    snapshot_path TEXT NOT NULL,
    zona TEXT NOT NULL,
    are_abonament BOOLEAN NOT NULL,
    id_camera INTEGER,
    FOREIGN KEY (id_camera) REFERENCES Camere(id_camera)
);

-- Creează tabela pentru amenzi
CREATE TABLE IF NOT EXISTS Amenzi (
    id_amenda INTEGER PRIMARY KEY AUTOINCREMENT,
    numar_inmatriculare TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    motiv TEXT NOT NULL,
    snapshot_path TEXT NOT NULL,
    zona TEXT NOT NULL
);

