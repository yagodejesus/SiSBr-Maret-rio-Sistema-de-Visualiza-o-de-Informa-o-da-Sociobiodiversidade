# Dashboard: Biodiversidade Costeira e Marinha do Brasil

Dashboard web em Python (Dash + Plotly + DuckDB) para **filtrar**, **analisar** e
**ver no mapa** as ocorrências de espécies dos municípios costeiros e do Sistema
Marinho. Os usuários também podem **contribuir com novas características no mapa**
(ninhos, encalhes, lixo, habitats etc.). As contribuições ficam visíveis para todos.

Paleta: `#054163` (azul), `#cab54b` (dourado, contribuições), `#f3f2e6` (fundo),
`#64c5b0` (verde-água, ocorrências).

## O que tem

| Aba | Conteúdo |
|---|---|
| **Mapa** | Grade agregada (o detalhe aumenta conforme o zoom), mapa de calor ou pontos (amostra). Mapas base: claro, oceano (batimetria), satélite e ruas. Clique numa célula para ver as espécies mais registradas ali. |
| **Análises** | Registros e espécies por ano, espécies e classes mais registradas, registros por UF, tipo de registro e tabela de espécies (ordenável e filtrável). |
| **Contribuições** | Gráficos e tabela das contribuições, download em CSV e exclusão (só com senha de administrador). |

**Filtros:** recorte (costeiro/marinho), espécie ou nome popular, reino → classe →
ordem → família (em cascata), UF → município, ano, tipo de registro e conjunto de
dados. O botão **Baixar CSV** exporta até 200 mil registros filtrados.

**Contribuir:** clique num ponto ou célula do mapa, ou centralize o mapa na mira
e clique em *Usar o centro do mapa*. Depois preencha categoria e característica e
clique em *Salvar*.

## Estrutura

```
app.py              # layout e callbacks do Dash
dados.py            # consultas DuckDB sobre os .parquet
contribuicoes.py    # contribuições (SQLite local / PostgreSQL no Railway)
preparar_dados.py   # converte os CSVs (5 GB) em data/ocorrencias/*.parquet (195 MB)
assets/style.css    # visual com a paleta
```

## Rodar local

```bash
pip install -r requirements.txt

# 1) só na primeira vez, ou quando os CSVs mudarem (~2 min)
python preparar_dados.py          # lê ../EspeciesCosteiras.csv e ../EspeciesMarinhas.csv

# 2) iniciar
python app.py                     # http://127.0.0.1:8050
```
