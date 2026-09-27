# eleicoes-2026-nlp

Pipeline ETL + análise NLP dos planos de governo presidenciais brasileiros de 2026. Extrai bigramas e eixos temáticos de PDFs e carrega no PostgreSQL para visualização no Power BI.

## Stack

- **Python** — extração de PDF, NLP, carga no banco
- **PostgreSQL 16** via Docker — armazenamento
- **Power BI** — visualização

## Estrutura

```
├── extrator.py              # Pipeline ETL principal
├── dashboard.py             # Gera dashboard HTML interativo
├── candidatos_config.json   # Mapeamento PDF → dados do candidato
├── init_db.sql              # DDL do banco (schema, tabelas, views)
├── docker-compose.yml       # PostgreSQL via Docker
├── .env                     # Credenciais (não versionado)
└── *.pdf                    # Planos de governo originais
```

## Como rodar

**1. Sobe o banco**
```bash
docker-compose up -d
```

**2. Cria o ambiente virtual e instala dependências**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configura o `.env`**
```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=eleicoes2026
POSTGRES_USER=etl_user
POSTGRES_PASSWORD=sua_senha
```

**4. Roda o ETL**
```bash
# Todos os candidatos de prioridade 1
python extrator.py --prioridade 1

# Candidato específico
python extrator.py --candidato "Lula"

# Todos
python extrator.py
```

**5. (Opcional) Gera o dashboard HTML**
```bash
python dashboard.py
# Abre dashboard_eleitoral_2026.html no navegador
```

## Banco de dados

O schema `eleicoes` contém:

| Tabela / View | Descrição |
|---|---|
| `dim_candidatos` | Dados cadastrais dos candidatos |
| `fato_temas` | Menções por eixo temático |
| `fato_bigramas` | Pares de palavras mais frequentes |
| `fato_bigramas_por_tema` | Bigramas classificados por tema |
| `vw_temas_por_candidato` | View com % e menções/mil palavras |
| `vw_bigramas_relevantes` | View com nível de relevância |
| `vw_bigramas_por_tema` | View para tooltip no Power BI |

## Candidatos mapeados

| Candidato | Partido | Nº |
|---|---|---|
| Ronaldo Caiado | União Brasil | 44 |
| Flávio Bolsonaro | PL | 22 |
| Pablo Marçal | Novo | 30 |
| Lula | PT | 13 |
| Renan Santos | Missão | — |
| Augusto Cury | Avante | 70 |
| Wilson Grassi | Partido Democrata | 35 |
| Samara Martins | UP | 80 |
| Edmilson Costa | PCB | 21 |

## Adicionando um novo candidato

1. Coloca o PDF na raiz do projeto
2. Adiciona uma entrada no `candidatos_config.json`
3. Roda `python extrator.py --candidato "Nome"`
