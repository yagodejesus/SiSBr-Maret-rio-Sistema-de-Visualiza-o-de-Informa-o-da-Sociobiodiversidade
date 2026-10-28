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

Para desenvolver com recarga automática: `DEBUG=1 python app.py`.

## Deploy no Railway

Os dados já ficam em `data/ocorrencias/` em partes de menos de 100 MB, então
dá para enviar tudo pelo GitHub.

1. Crie um repositório só com a pasta `dashboard/` e envie para o GitHub:
   ```bash
   cd dashboard
   git init && git add . && git commit -m "Dashboard biodiversidade"
   git remote add origin https://github.com/<usuario>/<repo>.git
   git push -u origin main
   ```
   (Ou, sem GitHub: `npm i -g @railway/cli`, `railway login`, `railway init`, `railway up`.)
2. No Railway: **New Project → Deploy from GitHub repo**. O `railway.json` já
   define o comando de início (gunicorn).
3. **Banco para as contribuições** (sem ele, elas se perdem a cada deploy):
   *New → Database → PostgreSQL*. Depois, no serviço do dashboard, em
   *Variables*, adicione `DATABASE_URL = ${{Postgres.DATABASE_URL}}`.
4. Em *Settings → Networking*, clique em **Generate Domain**.

### Variáveis de ambiente (opcionais)

| Variável | Para quê |
|---|---|
| `DATABASE_URL` | PostgreSQL das contribuições. Sem ela, usa `data/contribuicoes.db` (SQLite). |
| `ADMIN_TOKEN` | Senha que libera a exclusão de contribuições na aba *Contribuições*. |
| `DUCKDB_MEMORY` | Limite de memória do DuckDB (padrão `1GB`). |
| `DATA_PATH` | Pasta com os `.parquet` (padrão `data/ocorrencias`). |
| `DATA_URL` | Link de um `.parquet` baixado na inicialização se a pasta estiver vazia. Serve para não versionar os dados. |
