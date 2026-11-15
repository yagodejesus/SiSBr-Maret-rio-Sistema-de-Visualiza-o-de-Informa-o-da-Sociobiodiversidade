# SiSBr-Maretório

**Sistema de Visualização de Informação da Sociobiodiversidade nos Maretórios**
*Information visualization system for socio-biodiversity in Brazilian maretórios (coastal and marine territories)*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/release-v1.0.0-054163.svg)](../../releases/tag/v1.0.0)
[![Python](https://img.shields.io/badge/python-3.13-64c5b0.svg)](https://www.python.org/)

[English](#english) · [Português](#português)

---

## English

### Overview

SiSBr-Maretório is a web dashboard, written entirely in Python, for exploring
**6.6 million species occurrence records** in Brazil's coastal municipalities and
Marine System. Users can **filter** the records, **analyse** them with charts and
tables, and **see their spatial distribution** on an interactive map. They can also
**contribute** new georeferenced characteristics to the map, such as nesting
sites, strandings, litter or habitats. Every contribution is stored and shown
to all users.

It runs on a regular laptop and on a small cloud container. The raw data (≈5 GB of
CSV) is converted once into compressed Parquet files (≈195 MB), and
[DuckDB](https://duckdb.org/) queries them directly without loading them
into memory. Most queries take 0.03–0.2 s.

| Dataset in v1.0.0 | |
|---|---|
| Occurrence records | 6,630,720 |
| In coastal municipalities | 5,181,242 |
| In the Marine System | 4,148,033 |
| Species | 38,338 |
| Families | 3,034 |
| Coastal municipalities with records | 280 |
| Time span | 1669–2026 |

A record can fall in both a coastal municipality and the Marine System. Such
records are stored once and flagged for both.

### Features

**Filters.** Every view responds to the same filter panel:
- geographic scope (coastal municipalities, Marine System or both)
- species or common-name search
- taxonomy cascade (kingdom → class → order → family) and a species-rank-only toggle
- state (UF) → municipality
- year range, with or without undated records
- basis of record and source dataset

The filtered records can be downloaded as CSV, up to 200,000 rows.

**Map tab**
- Three views: aggregated grid, heat map and point sample.
  - The grid cells get smaller as you zoom in, from 0.5° down to 0.01°.
  - The colour scale is logarithmic.
- Four base maps: light, ocean (bathymetry), satellite and streets.
- Clicking a grid cell lists the species recorded most often in it. Clicking a
  point shows that record's details.
- *Fit results* zooms the map to the filtered records.

**Analyses tab**
- Records per year and species per year.
- Most recorded species and classes.
- Records per state and by basis of record.
- A sortable, filterable table of up to 500 species.

**Contributions tab (citizen contributions)**
- To pick a location, click the map, or pan the map so the crosshair sits on
  the location and press *Use map centre*.
- Each contribution has a category, a characteristic and an optional value,
  related species, description, author and observation date.
- Contributions appear as gold markers. They can be listed, charted and
  exported as CSV.
- Deleting contributions requires an administrator password.

### Repository structure

```
app.py                         Dash layout and callbacks (user interface)
dados.py                       DuckDB query layer over the Parquet files
contribuicoes.py               Contribution storage (SQLite locally, PostgreSQL if DATABASE_URL is set)
preparar_dados.py              Converts the occurrence CSVs into data/ocorrencias/*.parquet
filtrar_especies_costeiras.py  Spatial filter: keeps occurrences inside the coastal/marine polygons
assets/style.css               Visual identity
data/ocorrencias/*.parquet     Processed dataset used by the dashboard (≈195 MB)
EspeciesCosteiras.csv.gz       Raw occurrences in coastal municipalities (Git LFS, ≈750 MB)
EspeciesMarinhas.csv.gz        Raw occurrences in the Marine System (Git LFS, ≈560 MB)
```

### Requirements

- Python 3.13 (tested on Windows 11). The packages are listed in
  [`requirements.txt`](requirements.txt): Dash 4.4, Plotly 7.1, Dash Bootstrap
  Components 2.0, DuckDB 2.0, pandas 3.0, SQLAlchemy 2.1, waitress, gunicorn.
- A modern browser with WebGL, which the map needs.
- About 1 GB of free RAM.

### Installation and usage

```bash
# The processed data is already in the repository. Skipping the raw CSVs
# (Git LFS, ≈1.3 GB) makes the clone much faster:
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/yagodejesus/SiSBr-Maret-rio-Sistema-de-Visualiza-o-de-Informa-o-da-Sociobiodiversidade.git sisbr-maretorio
cd sisbr-maretorio

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python app.py                      # open http://127.0.0.1:8050
```

Set `DEBUG=1` before `python app.py` to get auto-reload while developing.

### Reproducing the dataset

The Parquet files in `data/ocorrencias/` can be rebuilt from the raw CSVs in
about 2 minutes:

```bash
git lfs pull                       # download the raw .csv.gz files
python preparar_dados.py --costeiras EspeciesCosteiras.csv.gz --marinhas EspeciesMarinhas.csv.gz
```

`preparar_dados.py` does four things:
- keeps the columns the dashboard uses and types them (coordinates, year, month and so on)
- discards records without coordinates
- merges the two files, removing duplicates by `Record ID`
- derives the state (UF) from the municipality or from the parsed state name

The raw CSVs were made by `filtrar_especies_costeiras.py`. It takes the
nationwide occurrence export (`EspeciesTotal*.csv`) and keeps only the points
that fall inside GeoJSON polygons, one file for the coastal municipalities and
one for the Marine System (SIRGAS 2000 / EPSG:4674). The nationwide export and
the polygons are not in this repository. Running that step also needs
`pip install geopandas`.

### License

Released under the [MIT License](LICENSE).

### Citation

If you use this software, please cite the release you used, for example
*SiSBr-Maretório v1.0.0*,
https://github.com/yagodejesus/SiSBr-Maret-rio-Sistema-de-Visualiza-o-de-Informa-o-da-Sociobiodiversidade/releases/tag/v1.0.0.

### Support

Please report bugs and questions through the repository's
[Issues](../../issues).

---

## Português

### Visão geral

O SiSBr-Maretório é um dashboard web, escrito todo em Python, para explorar
**6,6 milhões de registros de ocorrência de espécies** nos municípios costeiros e
no Sistema Marinho do Brasil. Com ele é possível **filtrar** os registros,
**analisá-los** com gráficos e tabelas e **ver sua distribuição** num mapa
interativo. Os usuários também podem **contribuir** com novas características
georreferenciadas no mapa, como ninhos, encalhes, lixo ou habitats. As
contribuições ficam salvas e visíveis para todos.

Ele roda num computador comum e num container pequeno na nuvem. Os dados brutos
(≈5 GB de CSV) são convertidos uma única vez em arquivos Parquet compactados
(≈195 MB), e o [DuckDB](https://duckdb.org/) consulta esses arquivos diretamente,
sem carregá-los na memória. A maioria das consultas leva de 0,03 a 0,2 s.

| Base na v1.0.0 | |
|---|---|
| Registros de ocorrência | 6.630.720 |
| Em municípios costeiros | 5.181.242 |
| No Sistema Marinho | 4.148.033 |
| Espécies | 38.338 |
| Famílias | 3.034 |
| Municípios costeiros com registros | 280 |
| Período | 1669–2026 |

Um registro pode estar ao mesmo tempo num município costeiro e no Sistema
Marinho. Nesse caso ele aparece uma única vez, com as duas marcações.

### Funcionalidades

**Filtros.** Todas as visualizações respondem ao mesmo painel:
- recorte geográfico (municípios costeiros, Sistema Marinho ou ambos)
- busca por espécie ou nome popular
- taxonomia em cascata (reino → classe → ordem → família) e opção de mostrar só
  registros identificados até espécie
- UF → município
- intervalo de anos, com ou sem registros sem data
- tipo de registro e conjunto de dados de origem

Os registros filtrados podem ser baixados em CSV, até 200 mil linhas.

**Aba Mapa**
- Três visualizações: grade agregada, mapa de calor e amostra de pontos.
  - As células da grade diminuem conforme o zoom, de 0,5° até 0,01°.
  - A escala de cor é logarítmica.
- Quatro mapas base: claro, oceano (batimetria), satélite e ruas.
- Clicar numa célula mostra as espécies mais registradas nela. Clicar num ponto
  mostra os detalhes do registro.
- *Enquadrar resultados* dá zoom na área dos registros filtrados.

**Aba Análises**
- Registros por ano e espécies por ano.
- Espécies e classes mais registradas.
- Registros por estado e por tipo de registro.
- Tabela ordenável e filtrável com até 500 espécies.

**Aba Contribuições (ciência cidadã)**
- Para escolher o local, clique no mapa, ou arraste o mapa até a mira ficar
  sobre o local e clique em *Usar o centro do mapa*.
- Cada contribuição tem categoria, característica e, opcionalmente, valor,
  espécie relacionada, descrição, autor e data da observação.
- As contribuições aparecem como marcadores dourados. Dá para listá-las, vê-las
  em gráficos e exportá-las em CSV.
- Excluir contribuições exige senha de administrador.

### Estrutura do repositório

```
app.py                         Layout e callbacks do Dash (interface)
dados.py                       Consultas DuckDB sobre os arquivos Parquet
contribuicoes.py               Contribuições (SQLite local; PostgreSQL se DATABASE_URL estiver definida)
preparar_dados.py              Converte os CSVs de ocorrência em data/ocorrencias/*.parquet
filtrar_especies_costeiras.py  Filtro espacial: mantém as ocorrências dentro dos polígonos
assets/style.css               Identidade visual
data/ocorrencias/*.parquet     Base processada usada pelo dashboard (≈195 MB)
EspeciesCosteiras.csv.gz       Ocorrências brutas nos municípios costeiros (Git LFS, ≈750 MB)
EspeciesMarinhas.csv.gz        Ocorrências brutas no Sistema Marinho (Git LFS, ≈560 MB)
```

### Requisitos

- Python 3.13 (testado no Windows 11). Os pacotes estão em
  [`requirements.txt`](requirements.txt).
- Navegador atual com WebGL, que o mapa usa.
- Cerca de 1 GB de RAM livre.

### Instalação e uso

```bash
# A base processada já está no repositório. Pular os CSVs brutos
# (Git LFS, ≈1,3 GB) deixa o clone bem mais rápido:
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/yagodejesus/SiSBr-Maret-rio-Sistema-de-Visualiza-o-de-Informa-o-da-Sociobiodiversidade.git sisbr-maretorio
cd sisbr-maretorio

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python app.py                      # abra http://127.0.0.1:8050
```

Defina `DEBUG=1` antes de `python app.py` para recarregar o app automaticamente
durante o desenvolvimento.

### Reproduzir a base de dados

Os arquivos Parquet de `data/ocorrencias/` podem ser recriados a partir dos CSVs
brutos em cerca de 2 minutos:

```bash
git lfs pull                       # baixa os .csv.gz brutos
python preparar_dados.py --costeiras EspeciesCosteiras.csv.gz --marinhas EspeciesMarinhas.csv.gz
```

O `preparar_dados.py` faz quatro coisas:
- mantém só as colunas usadas pelo dashboard, já com tipos (coordenadas, ano,
  mês etc.)
- descarta registros sem coordenadas
- une os dois arquivos, removendo duplicados pelo `Record ID`
- obtém a UF do município ou do nome do estado

Os CSVs brutos foram gerados pelo `filtrar_especies_costeiras.py`. Ele parte da
exportação nacional de ocorrências (`EspeciesTotal*.csv`) e mantém só os pontos
que caem dentro de polígonos GeoJSON: um arquivo com os municípios costeiros e
outro com o Sistema Marinho (SIRGAS 2000 / EPSG:4674). A exportação nacional e os
polígonos não estão neste repositório. Essa etapa também precisa de
`pip install geopandas`.

### Licença

Distribuído sob a [Licença MIT](LICENSE).

### Como citar

Se usar este software, cite a versão utilizada, por exemplo
*SiSBr-Maretório v1.0.0*,
https://github.com/yagodejesus/SiSBr-Maret-rio-Sistema-de-Visualiza-o-de-Informa-o-da-Sociobiodiversidade/releases/tag/v1.0.0.

### Suporte

Relate erros e dúvidas pelas [Issues](../../issues) do repositório.
