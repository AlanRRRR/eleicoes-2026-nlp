"""
ETL - Análise de Planos de Governo 2026

Uso:
    python extrator.py
    python extrator.py --prioridade 1
    python extrator.py --candidato "Ronaldo Caiado"
"""

import pdfplumber
import re
import nltk
import json
import logging
import argparse
import os
from nltk.corpus import stopwords
from nltk.util import bigrams
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

load_dotenv()

DB_HOST     = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT     = os.getenv("POSTGRES_PORT", "5432")
DB_NAME     = os.getenv("POSTGRES_DB", "eleicoes2026")
DB_USER     = os.getenv("POSTGRES_USER", "etl_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# quote_plus evita que caracteres especiais na senha quebrem a URL de conexão
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- NLP ---
nltk.download("stopwords", quiet=True)
stop_words_pt = set(stopwords.words("portuguese"))
stop_words_pt.update({
    "brasil", "governo", "nacional", "federal", "estado", "programa",
    "política", "politica", "ser", "ter", "fazer", "dois", "três", "quatro",
    "cinco", "dez", "cem", "mil", "anos", "ano", "vez", "parte",
})

MIN_BIGRAMA_FREQ = 3  # bigramas abaixo disso são ruído estatístico

DICIONARIO_TEMAS = {
    "Saúde": [
        "saúde", "saude", "sus", "ubs", "upa", "hospital", "clínica", "clinica",
        "posto", "leito", "uti", "samu", "pronto", "socorro", "ambulância", "ambulancia",
        "médico", "medico", "enfermagem", "enfermeiro", "farmacêutico", "farmaceutico",
        "dentista", "odontologia", "nutrição", "nutricao", "psicólogo", "psicologo",
        "doença", "doenca", "epidemia", "pandemia", "vacina", "vacinação", "vacinacao",
        "remédio", "remedio", "medicamento", "tratamento", "diagnóstico", "diagnostico",
        "prevenção", "prevencao", "internação", "internacao", "cirurgia", "consulta",
        "mental", "psiquiátrico", "psiquiatrico", "oncologia", "câncer", "cancer",
        "cardíaco", "cardiaco", "materno", "infantil", "idoso", "deficiência", "deficiencia",
        "farmácia", "farmacia", "popular", "mais", "médicos", "medicos", "humaniza",
    ],

    "Educação": [
        "educação", "educacao", "escola", "ensino", "creche", "universidade", "faculdade",
        "técnico", "tecnico", "profissional", "enem", "vestibular", "prouni", "fies",
        "professor", "aluno", "estudante", "pedagogo", "diretor", "gestor",
        "aprendizagem", "alfabetização", "alfabetizacao", "letramento", "currículo", "curriculo",
        "evasão", "evasao", "matrícula", "matricula", "merenda", "transporte", "escolar",
        "bolsa", "bolsista", "mérito", "merito", "avaliação", "avaliacao",
        "ead", "distância", "distancia", "integral", "período", "periodo", "turno",
        "pesquisa", "ciência", "ciencia", "inovação", "inovacao", "pós", "pos",
        "graduação", "graduacao", "mestrado", "doutorado", "capes", "cnpq",
    ],

    "Segurança": [
        "segurança", "seguranca", "polícia", "policia", "militar", "civil", "federal",
        "guarda", "bombeiro", "penal", "penitenciária", "penitenciaria", "presídio", "presidio",
        "crime", "violência", "violencia", "homicídio", "homicidio", "assassinato",
        "roubo", "furto", "assalto", "sequestro", "extorsão", "extorsao",
        "tráfico", "trafico", "droga", "narcotráfico", "narcotrafico", "milícia", "milicia",
        "armas", "armamento", "combate", "investigação", "investigacao", "delegacia",
        "encarceramento", "reincidência", "reincidencia", "ressocialização", "ressocializacao",
        "fronteira", "patrulha", "vigilância", "vigilancia", "monitoramento",
        "corrupção", "corrupcao", "fraude", "lavagem", "impunidade", "transparência", "transparencia",
    ],

    "Economia": [
        "economia", "pib", "inflação", "inflacao", "deflação", "deflacao", "juros",
        "selic", "câmbio", "cambio", "déficit", "deficit", "superávit", "superavit",
        "fiscal", "orçamento", "orcamento", "dívida", "divida", "tributário", "tributario",
        "emprego", "desemprego", "trabalho", "renda", "salário", "salario", "mínimo",
        "minimo", "previdência", "previdencia", "aposentadoria", "benefício", "beneficio",
        "indústria", "industria", "agronegócio", "agronegocio", "exportação", "exportacao",
        "importação", "importacao", "comércio", "comercio", "empresas", "empresa",
        "empreendedorismo", "mei", "microempresa", "startup", "investimento",
        "crédito", "credito", "financiamento", "banco", "imposto", "carga", "tributária", "tributaria",
        "privatização", "privatizacao", "concessão", "concessao", "mercado",
    ],

    "Meio Ambiente": [
        "ambiente", "amazônia", "amazonia", "cerrado", "pantanal", "caatinga",
        "mata", "atlântica", "atlantica", "floresta", "biodiversidade",
        "água", "agua", "rio", "oceano", "mar", "solo", "fauna", "flora",
        "pesca", "marinha", "costeiro",
        "desmatamento", "queimada", "incêndio", "incendio", "erosão", "erosao",
        "poluição", "poluicao", "agrotóxico", "agrotoxico", "carbono", "emissão", "emissao",
        "sustentabilidade", "sustentável", "sustentavel", "verde", "renovável", "renovavel",
        "solar", "eólica", "eolica", "hidrelétrica", "hidreletrica", "biomassa",
        "reflorestamento", "conservação", "conservacao", "preservação", "preservacao",
        "clima", "climática", "climatica", "aquecimento",
    ],

    "Infraestrutura": [
        "infraestrutura", "rodovia", "estrada", "ferrovia", "trem", "metrô", "metro",
        "porto", "aeroporto", "ponte", "viaduto", "pavimentação", "pavimentacao",
        "logística", "logistica", "transporte", "mobilidade", "ciclovia", "brt",
        "habitação", "habitacao", "moradia", "casa", "minha",
        "regularização", "regularizacao", "fundiária", "fundiaria", "urbanização", "urbanizacao",
        "saneamento", "esgoto", "água", "agua", "tratamento", "distribuição", "distribuicao",
        "energia", "elétrica", "eletrica", "rede", "transmissão", "transmissao",
        "iluminação", "iluminacao",
        "fibra", "óptica", "optica", "internet", "conectividade", "5g", "banda",
    ],

    "Tecnologia": [
        "tecnologia", "digital", "inteligência", "inteligencia", "artificial",
        "blockchain", "dados", "big", "computação", "computacao", "nuvem",
        "robótica", "robotica", "automação", "automacao", "algoritmo",
        "inovação", "inovacao", "pesquisa", "desenvolvimento", "startup",
        "ecossistema", "hub", "incubadora", "aceleração", "aceleracao",
        "governo", "digital", "e-gov", "online", "plataforma", "aplicativo",
        "cibersegurança", "ciberseguranca", "privacidade", "lgpd",
        "programação", "programacao", "software", "hardware", "ciência", "ciencia",
        "stem", "código", "codigo",
        "fintech", "healthtech", "edtech", "agtech", "satélite", "satelite", "espacial",
    ],
}


# --- Funções ---

def conectar_banco():
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Conexao com PostgreSQL estabelecida.")
        return engine
    except Exception as e:
        log.error(f"Falha ao conectar: {e}")
        log.error("Verifique se o Docker esta rodando: docker-compose up -d")
        raise


def carregar_config_candidatos(caminho_config="candidatos_config.json"):
    caminho = Path(caminho_config)
    if not caminho.exists():
        raise FileNotFoundError(caminho_config)
    with open(caminho, "r", encoding="utf-8") as f:
        config = json.load(f)
    log.info(f"{len(config['candidatos'])} candidatos encontrados no config.")
    return config["candidatos"]


def extrair_texto_pdf(caminho_pdf):
    texto_completo = ""
    with pdfplumber.open(caminho_pdf) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text()
            if texto:
                texto_completo += texto + " "
        log.info(f"   {len(pdf.pages)} paginas lidas.")
    return texto_completo


def limpar_texto(texto):
    texto_limpo = re.sub(r"[^a-záàâãéèêíïóôõöúüçña-z\s]", "", texto.lower())
    palavras = texto_limpo.split()
    return [p for p in palavras if p not in stop_words_pt and len(p) >= 3]


def analisar_bigramas(palavras):
    pares = [f"{p1} {p2}" for p1, p2 in bigrams(palavras)]
    contagem = Counter(pares)
    df = pd.DataFrame(contagem.items(), columns=["par_de_palavras", "frequencia"])
    df = df[df["frequencia"] >= MIN_BIGRAMA_FREQ]
    return df.sort_values("frequencia", ascending=False).reset_index(drop=True)


def analisar_temas(palavras):
    contagem = {tema: 0 for tema in DICIONARIO_TEMAS}
    for palavra in palavras:
        for tema, keywords in DICIONARIO_TEMAS.items():
            if palavra in keywords:
                contagem[tema] += 1
    df = pd.DataFrame(list(contagem.items()), columns=["eixo_tematico", "mencoes"])
    return df.sort_values("mencoes", ascending=False).reset_index(drop=True)


def upsert_candidato(engine, candidato_config, total_palavras):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                INSERT INTO eleicoes.dim_candidatos
                    (nome_candidato, sigla_partido, numero_urna, arquivo_pdf, total_palavras)
                VALUES
                    (:nome, :partido, :numero, :arquivo, :total_palavras)
                ON CONFLICT (arquivo_pdf)
                DO UPDATE SET
                    nome_candidato = EXCLUDED.nome_candidato,
                    sigla_partido  = EXCLUDED.sigla_partido,
                    numero_urna    = EXCLUDED.numero_urna,
                    total_palavras = EXCLUDED.total_palavras,
                    dt_carga       = NOW()
                RETURNING id_candidato
            """),
            {
                "nome":           candidato_config["nome_candidato"],
                "partido":        candidato_config["sigla_partido"],
                "numero":         candidato_config.get("numero_urna"),
                "arquivo":        candidato_config["arquivo_pdf"],
                "total_palavras": total_palavras,
            },
        )
        return result.scalar_one()


def carregar_fatos(engine, id_candidato, df_bigramas, df_temas):
    with engine.begin() as conn:
        # Temas
        for _, row in df_temas.iterrows():
            conn.execute(
                text("""
                    INSERT INTO eleicoes.fato_temas (id_candidato, eixo_tematico, mencoes)
                    VALUES (:id_c, :tema, :mencoes)
                    ON CONFLICT (id_candidato, eixo_tematico)
                    DO UPDATE SET mencoes = EXCLUDED.mencoes, dt_carga = NOW()
                """),
                {"id_c": id_candidato, "tema": row["eixo_tematico"], "mencoes": int(row["mencoes"])},
            )

        # Bigramas
        conn.execute(text("DELETE FROM eleicoes.fato_bigramas WHERE id_candidato = :id_c"), {"id_c": id_candidato})
        df_b = df_bigramas.copy()
        df_b["id_candidato"] = id_candidato
        df_b["dt_carga"] = datetime.now()
        df_b[["id_candidato", "par_de_palavras", "frequencia", "dt_carga"]].to_sql(
            "fato_bigramas", conn, schema="eleicoes", if_exists="append", index=False, method="multi", chunksize=500,
        )

        # Bigramas por tema (classifica cada par pelas palavras do dicionário)
        conn.execute(text("DELETE FROM eleicoes.fato_bigramas_por_tema WHERE id_candidato = :id_c"), {"id_c": id_candidato})
        registros = []
        for _, row in df_bigramas.iterrows():
            temas = {
                tema
                for palavra in row["par_de_palavras"].split()
                for tema, keywords in DICIONARIO_TEMAS.items()
                if palavra in keywords
            }
            for tema in temas:
                registros.append({
                    "id_candidato": id_candidato,
                    "eixo_tematico": tema,
                    "par_de_palavras": row["par_de_palavras"],
                    "frequencia": int(row["frequencia"]),
                    "dt_carga": datetime.now(),
                })

        if registros:
            pd.DataFrame(registros).to_sql(
                "fato_bigramas_por_tema", conn, schema="eleicoes", if_exists="append", index=False, method="multi", chunksize=500,
            )

    log.info(f"   Temas: {len(df_temas)} | Bigramas: {len(df_bigramas)} | Bigramas/tema: {len(registros)}")


# --- Pipeline ---

def processar_candidato(engine, candidato_config):
    nome    = candidato_config["nome_candidato"]
    arquivo = candidato_config["arquivo_pdf"]
    caminho = Path(arquivo)

    log.info(f"\n{'='*50}")
    log.info(f"Processando: {nome}")

    if not caminho.exists():
        log.warning(f"PDF nao encontrado: {arquivo} — pulando.")
        return False

    log.info("   Extraindo texto...")
    texto = extrair_texto_pdf(caminho)
    if not texto.strip():
        log.warning(f"Nenhum texto extraido de {arquivo} — pulando.")
        return False

    log.info("   Analisando...")
    palavras    = limpar_texto(texto)
    df_bigramas = analisar_bigramas(palavras)
    df_temas    = analisar_temas(palavras)
    log.info(f"   {len(palavras)} palavras | {len(df_bigramas)} bigramas")

    log.info("   Salvando...")
    id_candidato = upsert_candidato(engine, candidato_config, total_palavras=len(palavras))
    carregar_fatos(engine, id_candidato, df_bigramas, df_temas)

    log.info(f"   Concluido (id={id_candidato})")
    return True


def main():
    parser = argparse.ArgumentParser(description="ETL - Planos de Governo 2026")
    parser.add_argument("--prioridade", type=int, default=None)
    parser.add_argument("--candidato",  type=str, default=None)
    args = parser.parse_args()

    inicio = datetime.now()
    log.info(f"ETL iniciado — {DB_NAME} em {DB_HOST}:{DB_PORT}")

    engine     = conectar_banco()
    candidatos = carregar_config_candidatos()

    if args.prioridade is not None:
        candidatos = [c for c in candidatos if c.get("prioridade", 99) <= args.prioridade]
        log.info(f"Filtro prioridade <= {args.prioridade}: {len(candidatos)} candidatos")

    if args.candidato:
        candidatos = [c for c in candidatos if args.candidato.lower() in c["nome_candidato"].lower()]
        log.info(f"Filtro nome '{args.candidato}': {len(candidatos)} candidatos")

    if not candidatos:
        log.warning("Nenhum candidato para processar.")
        return

    resultados = {"sucesso": 0, "pulado": 0, "erro": 0}
    for config in candidatos:
        try:
            ok = processar_candidato(engine, config)
            resultados["sucesso" if ok else "pulado"] += 1
        except Exception as e:
            log.error(f"Erro em {config['nome_candidato']}: {e}")
            resultados["erro"] += 1

    duracao = (datetime.now() - inicio).seconds
    log.info(f"\n{'='*50}")
    log.info(f"ETL concluido em {duracao}s — Sucesso: {resultados['sucesso']} | Pulados: {resultados['pulado']} | Erros: {resultados['erro']}")


if __name__ == "__main__":
    main()