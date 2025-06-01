DROP TABLE IF EXISTS Utilizatori;
CREATE TABLE Utilizatori (
    id_utilizator INTEGER PRIMARY KEY AUTOINCREMENT,
    nume VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    parola VARCHAR(255) NOT NULL,
    data_inregistrare TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reset_token TEXT,
    reset_token_expirare TEXT
);

DROP TABLE IF EXISTS Abonamente;
CREATE TABLE Abonamente (
    id_abonament INTEGER PRIMARY KEY AUTOINCREMENT,
    id_utilizator INTEGER NOT NULL,
    numar_inmatriculare VARCHAR(20) NOT NULL,
    zona TEXT NOT NULL CHECK( zona IN ('Zona 1', 'Zona 2', 'Zona 3', 'Zona 4') ), -- MODIFICARE AICI
    tip_abonament TEXT NOT NULL CHECK( tip_abonament IN ('ora', 'zi') ),
    durata INTEGER NOT NULL,
    data_inceput DATETIME NOT NULL,
    data_sfarsit DATETIME NOT NULL,
    data_achizitie TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pret DECIMAL(10, 2) NOT NULL,
    status TEXT NOT NULL DEFAULT 'activ' CHECK( status IN ('activ', 'expirat', 'viitor') ),
    FOREIGN KEY (id_utilizator) REFERENCES Utilizatori(id_utilizator)
);

DROP TABLE IF EXISTS Tranzactii;
CREATE TABLE Tranzactii (
    id_tranzactie INTEGER PRIMARY KEY AUTOINCREMENT,
    id_abonament INTEGER NOT NULL,
    data_tranzactie TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    suma DECIMAL(10, 2) NOT NULL,
    metoda_plata VARCHAR(50) NOT NULL,
    status_tranzactie VARCHAR(50) NOT NULL,
    FOREIGN KEY (id_abonament) REFERENCES Abonamente(id_abonament)
);

CREATE INDEX idx_utilizatori_email ON Utilizatori (email);
CREATE INDEX idx_abonamente_numar_inmatriculare ON Abonamente (numar_inmatriculare);
CREATE INDEX idx_abonamente_status ON Abonamente (status);
CREATE INDEX idx_abonamente_id_utilizator ON Abonamente (id_utilizator);