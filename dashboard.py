"""
Dashboard Eleitoral 2026 — Análise de Planos de Governo
Gera um arquivo HTML interativo a partir dos dados do PostgreSQL.

Uso:
    python dashboard.py
    # Abre o arquivo 'dashboard_eleitoral_2026.html' no navegador
"""

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from sqlalchemy import create_engine
from urllib.parse import quote_plus
from dotenv import load_dotenv
from datetime import datetime
from itertools import cycle
import os

load_dotenv()

# ==========================================
# CONEXÃO
# ==========================================
DB_HOST     = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT     = os.getenv("POSTGRES_PORT", "5432")
DB_NAME     = os.getenv("POSTGRES_DB", "eleicoes2026")
DB_USER     = os.getenv("POSTGRES_USER", "etl_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

print("Conectando ao banco...")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# ==========================================
# DADOS
# ==========================================
df_temas    = pd.read_sql("SELECT * FROM eleicoes.vw_temas_por_candidato ORDER BY nome_candidato, mencoes DESC", engine)
df_bigramas = pd.read_sql("SELECT * FROM eleicoes.vw_bigramas_relevantes ORDER BY nome_candidato, frequencia DESC", engine)

candidatos = sorted(df_temas["nome_candidato"].unique().tolist())
temas_ordem = ["Economia", "Tecnologia", "Segurança", "Saúde", "Educação", "Infraestrutura", "Meio Ambiente"]
temas_ordem = [t for t in temas_ordem if t in df_temas["eixo_tematico"].unique()]

print(f"OK: {len(candidatos)} candidatos | {len(temas_ordem)} temas")

# ==========================================
# PALETAS
# ==========================================
CORES_TEMAS = {
    "Saúde":          "#E74C3C",
    "Educação":        "#3498DB",
    "Segurança":       "#E67E22",
    "Economia":        "#2ECC71",
    "Meio Ambiente":   "#27AE60",
    "Infraestrutura":  "#F39C12",
    "Tecnologia":      "#9B59B6",
}

# Paleta de cores para candidatos — cicla se tiver mais que 6
_paleta = ["#00B4D8", "#F44336", "#4CAF50", "#FF9800", "#AB47BC", "#26C6DA", "#FFD700", "#FF69B4"]
CORES_CANDIDATOS = {c: _paleta[i % len(_paleta)] for i, c in enumerate(candidatos)}

# Layout base dark
def layout_base(titulo="", height=450):
    return dict(
        paper_bgcolor="#0D1117",
        plot_bgcolor="#161B22",
        font=dict(family="Inter, sans-serif", color="#C9D1D9", size=12),
        title=dict(text=titulo, font=dict(size=17, color="#F0F6FC"), x=0.5, xanchor="center"),
        height=height,
        margin=dict(l=20, r=20, t=60, b=20),
    )

def grade():
    return dict(gridcolor="#30363D", zerolinecolor="#30363D")

# ==========================================
# FIGURA 1 — Barras Empilhadas 100%
# ==========================================
print("Criando Fig 1: Perfil tematico...")

fig1 = go.Figure()
for tema in temas_ordem:
    df_t = df_temas[df_temas["eixo_tematico"] == tema].copy()
    df_t = df_t.sort_values("nome_candidato")
    fig1.add_trace(go.Bar(
        name=tema,
        x=df_t["nome_candidato"],
        y=df_t["pct_do_candidato"],
        marker_color=CORES_TEMAS.get(tema, "#888"),
        hovertemplate="<b>%{x}</b><br>" + tema + ": %{y:.1f}%<extra></extra>",
    ))

fig1.update_layout(
    **layout_base("Perfil Temático dos Candidatos — % do Discurso", height=430),
    barmode="stack",
    xaxis=dict(**grade(), title=""),
    yaxis=dict(**grade(), title="% do discurso", ticksuffix="%", range=[0, 100]),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                bgcolor="rgba(0,0,0,0)"),
)

# ==========================================
# FIGURA 2 — Heatmap
# ==========================================
print("Criando Fig 2: Heatmap...")

pivot = df_temas.pivot_table(
    index="nome_candidato", columns="eixo_tematico",
    values="mencoes_por_mil_palavras"
).reindex(columns=temas_ordem).fillna(0)

fig2 = go.Figure(data=go.Heatmap(
    z=pivot.values,
    x=list(pivot.columns),
    y=list(pivot.index),
    colorscale="YlOrRd",
    hovertemplate="<b>%{y}</b><br>%{x}: %{z:.1f} por mil palavras<extra></extra>",
    text=[[f"{v:.1f}" for v in row] for row in pivot.values],
    texttemplate="%{text}",
    textfont=dict(size=12, color="#0D1117"),
))

fig2.update_layout(
    **layout_base("Intensidade Temática — Menções por 1.000 Palavras", height=340),
    xaxis=dict(side="bottom", title=""),
    yaxis=dict(title=""),
)

# ==========================================
# FIGURA 3 — Radar com todos candidatos
# ==========================================
print("Criando Fig 3: Radar...")

fig3 = go.Figure()
for candidato in candidatos:
    df_c = df_temas[df_temas["nome_candidato"] == candidato].copy()
    df_c = df_c.set_index("eixo_tematico").reindex(temas_ordem).fillna(0)
    r = df_c["mencoes_por_mil_palavras"].tolist()
    r.append(r[0])  # fecha o polígono
    theta = temas_ordem + [temas_ordem[0]]

    fig3.add_trace(go.Scatterpolar(
        r=r,
        theta=theta,
        fill="toself",
        name=candidato,
        line_color=CORES_CANDIDATOS[candidato],
        fillcolor=CORES_CANDIDATOS[candidato] + "22",
        hovertemplate=candidato + "<br>%{theta}: %{r:.1f}/mil<extra></extra>",
    ))

fig3.update_layout(
    **layout_base("Radar Temático — Todos os Candidatos", height=490),
    polar=dict(
        radialaxis=dict(visible=True, gridcolor="#30363D", color="#8B949E"),
        angularaxis=dict(gridcolor="#30363D", color="#C9D1D9"),
        bgcolor="#161B22",
    ),
    legend=dict(
        orientation="v", x=1.05, y=0.5,
        bgcolor="#161B22", bordercolor="#30363D", borderwidth=1,
    ),
)

# ==========================================
# FIGURA 4 — Top Bigramas com dropdown
# ==========================================
print("Criando Fig 4: Top Bigramas...")

fig4 = go.Figure()
for i, candidato in enumerate(candidatos):
    df_b = df_bigramas[df_bigramas["nome_candidato"] == candidato].head(20)
    df_b = df_b.sort_values("frequencia", ascending=True)
    cor = CORES_CANDIDATOS[candidato]

    fig4.add_trace(go.Bar(
        name=candidato,
        x=df_b["frequencia"],
        y=df_b["par_de_palavras"],
        orientation="h",
        marker=dict(
            color=df_b["frequencia"],
            colorscale=[[0, "#21262D"], [1, cor]],
            showscale=False,
        ),
        customdata=df_b[["nivel_relevancia"]],
        hovertemplate="<b>%{y}</b><br>Frequência: %{x}x<br>Nível: %{customdata[0]}<extra></extra>",
        visible=(i == 0),
    ))

botoes = []
for i, candidato in enumerate(candidatos):
    visibilidade = [j == i for j in range(len(candidatos))]
    botoes.append(dict(
        label=candidato,
        method="update",
        args=[{"visible": visibilidade},
              {"title": {"text": f"Top 20 Bigramas — {candidato}", "font": {"size": 17, "color": "#F0F6FC"}, "x": 0.5}}],
    ))

fig4.update_layout(
    **layout_base(f"Top 20 Bigramas — {candidatos[0]}", height=530),
    xaxis=dict(**grade(), title="Frequência"),
    yaxis=dict(**grade(), title="", automargin=True),
    showlegend=False,
    updatemenus=[dict(
        type="dropdown",
        direction="down",
        x=0.0, xanchor="left",
        y=1.16, yanchor="top",
        buttons=botoes,
        bgcolor="#21262D",
        bordercolor="#30363D",
        font=dict(color="#C9D1D9"),
        active=0,
    )],
)

# ==========================================
# MONTA O HTML
# ==========================================
print("Montando HTML...")

def fig_to_html(fig):
    return pio.to_html(fig, full_html=False, include_plotlyjs=False, config={"displayModeBar": False})

# KPI cards
kpi_html = ""
for candidato in candidatos:
    df_c = df_temas[df_temas["nome_candidato"] == candidato]
    palavras   = int(df_c["total_palavras"].iloc[0])
    partido    = df_c["sigla_partido"].iloc[0] or "—"
    tema_top   = df_c.sort_values("mencoes", ascending=False).iloc[0]["eixo_tematico"]
    cor        = CORES_CANDIDATOS[candidato]
    cor_tema   = CORES_TEMAS.get(tema_top, "#888")
    kpi_html += f"""
    <div class="kpi-card" style="border-top: 3px solid {cor}">
        <div class="kpi-partido">{partido}</div>
        <div class="kpi-name">{candidato}</div>
        <div class="kpi-value">{palavras:,}</div>
        <div class="kpi-label">palavras analisadas</div>
        <div class="kpi-tema" style="background:{cor_tema}22; color:{cor_tema}; border:1px solid {cor_tema}44">
            📌 {tema_top}
        </div>
    </div>"""

now = datetime.now().strftime("%d/%m/%Y às %H:%M")

HTML = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Eleitoral 2026</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
  
  body {{
    background: #0D1117;
    color: #C9D1D9;
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
  }}

  /* ── HEADER ── */
  .header {{
    background: linear-gradient(135deg, #161B22 0%, #0D1117 100%);
    border-bottom: 1px solid #30363D;
    padding: 28px 48px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(10px);
  }}
  .header-left h1 {{
    font-size: 26px;
    font-weight: 800;
    color: #F0F6FC;
    letter-spacing: -0.5px;
  }}
  .header-left h1 span {{ color: #388BFD; }}
  .header-left p {{ color: #8B949E; font-size: 13px; margin-top: 3px; }}
  .header-badge {{
    background: #21262D;
    border: 1px solid #30363D;
    border-radius: 20px;
    padding: 8px 18px;
    font-size: 13px;
    color: #8B949E;
  }}

  /* ── KPI SECTION ── */
  .kpi-section {{
    padding: 28px 48px 0;
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
  }}
  .kpi-card {{
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 12px;
    padding: 18px 20px;
    flex: 1;
    min-width: 150px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    cursor: default;
  }}
  .kpi-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }}
  .kpi-partido {{ font-size: 11px; font-weight: 600; color: #8B949E; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
  .kpi-name {{ font-size: 15px; font-weight: 700; color: #F0F6FC; margin-bottom: 10px; }}
  .kpi-value {{ font-size: 28px; font-weight: 800; color: #F0F6FC; line-height: 1; }}
  .kpi-label {{ font-size: 11px; color: #8B949E; margin-top: 3px; margin-bottom: 10px; }}
  .kpi-tema {{
    display: inline-block;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
  }}

  /* ── SECTIONS ── */
  .section {{ padding: 28px 48px; }}
  .section-label {{
    font-size: 11px;
    font-weight: 700;
    color: #8B949E;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 1px solid #21262D;
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .chart-card {{
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 14px;
    padding: 8px;
    overflow: hidden;
    transition: border-color 0.2s;
  }}
  .chart-card:hover {{ border-color: #388BFD44; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}

  /* ── FOOTER ── */
  .footer {{
    text-align: center;
    padding: 24px 48px;
    color: #8B949E;
    font-size: 12px;
    border-top: 1px solid #21262D;
    margin-top: 12px;
  }}
  .footer a {{ color: #388BFD; text-decoration: none; }}

  @media (max-width: 900px) {{
    .header {{ padding: 20px 24px; flex-direction: column; gap: 12px; }}
    .kpi-section, .section {{ padding: 20px 24px; }}
    .grid-2 {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-left">
    <h1>Dashboard <span>Eleitoral 2026</span></h1>
    <p>Análise de Planos de Governo Presidenciais · Atualizado em {now}</p>
  </div>
  <div class="header-badge">🗳️ {len(candidatos)} candidatos · {len(temas_ordem)} eixos temáticos</div>
</div>

<!-- KPIs -->
<div class="kpi-section">{kpi_html}</div>

<!-- FIG 1: PERFIL TEMÁTICO -->
<div class="section">
  <div class="section-label">📊 Perfil Temático</div>
  <div class="chart-card">{fig_to_html(fig1)}</div>
</div>

<!-- FIG 2: HEATMAP -->
<div class="section">
  <div class="section-label">🔥 Mapa de Calor · menções por 1.000 palavras</div>
  <div class="chart-card">{fig_to_html(fig2)}</div>
</div>

<!-- FIG 3 + FIG 4: RADAR + BIGRAMAS -->
<div class="section">
  <div class="grid-2">
    <div>
      <div class="section-label">🕸️ Radar Temático</div>
      <div class="chart-card">{fig_to_html(fig3)}</div>
    </div>
    <div>
      <div class="section-label">📝 Top 20 Bigramas por Candidato</div>
      <div class="chart-card">{fig_to_html(fig4)}</div>
    </div>
  </div>
</div>

<!-- FOOTER -->
<div class="footer">
  Dados extraídos de PDFs oficiais dos planos de governo · ETL Python + PostgreSQL · Visualização Plotly
</div>

</body>
</html>"""

output = "dashboard_eleitoral_2026.html"
with open(output, "w", encoding="utf-8") as f:
    f.write(HTML)

print(f"\nDashboard gerado: {output}")
print(f"   Abre no navegador: start {output}")
