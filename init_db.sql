-- Schema: eleicoes — Análise de Planos de Governo 2026
CREATE SCHEMA IF NOT EXISTS eleicoes;
SET search_path TO eleicoes;

-- Dimensão: candidatos
CREATE TABLE IF NOT EXISTS dim_candidatos (
    id_candidato    SERIAL PRIMARY KEY,
    nome_candidato  VARCHAR(150) NOT NULL,
    sigla_partido   VARCHAR(50),
    numero_urna     SMALLINT,
    arquivo_pdf     VARCHAR(300) NOT NULL UNIQUE,
    total_palavras  INT DEFAULT 0,
    dt_carga        TIMESTAMP DEFAULT NOW()
);

-- Fato: menções por eixo temático
CREATE TABLE IF NOT EXISTS fato_temas (
    id              SERIAL PRIMARY KEY,
    id_candidato    INT NOT NULL REFERENCES dim_candidatos(id_candidato) ON DELETE CASCADE,
    eixo_tematico   VARCHAR(100) NOT NULL,
    mencoes         INT NOT NULL DEFAULT 0,
    dt_carga        TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_candidato_tema UNIQUE (id_candidato, eixo_tematico)
);

-- Fato: bigramas por candidato
CREATE TABLE IF NOT EXISTS fato_bigramas (
    id              SERIAL PRIMARY KEY,
    id_candidato    INT NOT NULL REFERENCES dim_candidatos(id_candidato) ON DELETE CASCADE,
    par_de_palavras VARCHAR(300) NOT NULL,
    frequencia      INT NOT NULL DEFAULT 0,
    dt_carga        TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_candidato_bigrama UNIQUE (id_candidato, par_de_palavras)
);

-- Fato: bigramas classificados por tema (para tooltip no Power BI)
CREATE TABLE IF NOT EXISTS fato_bigramas_por_tema (
    id              SERIAL PRIMARY KEY,
    id_candidato    INT NOT NULL REFERENCES dim_candidatos(id_candidato) ON DELETE CASCADE,
    eixo_tematico   VARCHAR(100) NOT NULL,
    par_de_palavras VARCHAR(300) NOT NULL,
    frequencia      INT NOT NULL,
    dt_carga        TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_candidato_tema_bigrama UNIQUE (id_candidato, eixo_tematico, par_de_palavras)
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_fato_temas_candidato      ON fato_temas(id_candidato);
CREATE INDEX IF NOT EXISTS idx_fato_bigramas_candidato   ON fato_bigramas(id_candidato);
CREATE INDEX IF NOT EXISTS idx_fato_bigramas_frequencia  ON fato_bigramas(frequencia DESC);
CREATE INDEX IF NOT EXISTS idx_fato_bigramas_tema        ON fato_bigramas_por_tema(id_candidato, eixo_tematico);

-- Views para Power BI
CREATE OR REPLACE VIEW vw_temas_por_candidato AS
    SELECT
        c.nome_candidato,
        c.sigla_partido,
        c.numero_urna,
        c.total_palavras,
        t.eixo_tematico,
        t.mencoes,
        ROUND(t.mencoes * 1000.0 / NULLIF(c.total_palavras, 0), 2) AS mencoes_por_mil_palavras,
        ROUND(t.mencoes * 100.0 / NULLIF(SUM(t.mencoes) OVER (PARTITION BY c.id_candidato), 0), 1) AS pct_do_candidato
    FROM fato_temas t
    JOIN dim_candidatos c ON c.id_candidato = t.id_candidato
    ORDER BY c.nome_candidato, t.mencoes DESC;

CREATE OR REPLACE VIEW vw_bigramas_por_candidato AS
    SELECT
        c.nome_candidato,
        c.sigla_partido,
        c.numero_urna,
        b.par_de_palavras,
        b.frequencia
    FROM fato_bigramas b
    JOIN dim_candidatos c ON c.id_candidato = b.id_candidato
    ORDER BY c.nome_candidato, b.frequencia DESC;

CREATE OR REPLACE VIEW vw_bigramas_relevantes AS
    SELECT
        c.nome_candidato,
        c.sigla_partido,
        c.numero_urna,
        c.total_palavras,
        b.par_de_palavras,
        b.frequencia,
        ROUND(b.frequencia * 1000.0 / NULLIF(c.total_palavras, 0), 2) AS freq_por_mil_palavras,
        CASE
            WHEN b.frequencia >= 10 THEN 'Tema Central'
            WHEN b.frequencia >= 5  THEN 'Relevante'
            ELSE                         'Mencionado'
        END AS nivel_relevancia
    FROM fato_bigramas b
    JOIN dim_candidatos c ON c.id_candidato = b.id_candidato
    ORDER BY c.nome_candidato, b.frequencia DESC;

CREATE OR REPLACE VIEW vw_bigramas_por_tema AS
    SELECT
        c.nome_candidato,
        c.sigla_partido,
        b.eixo_tematico,
        b.par_de_palavras,
        b.frequencia
    FROM fato_bigramas_por_tema b
    JOIN dim_candidatos c ON c.id_candidato = b.id_candidato
    ORDER BY c.nome_candidato, b.eixo_tematico, b.frequencia DESC;
