"""
Converte EspeciesCosteiras.csv e EspeciesMarinhas.csv (≈5 GB) num único
arquivo Parquet compacto, que é o que o dashboard consulta.

- Mantém só as colunas usadas no dashboard, já com tipos (lat/lon numéricos,
  ano inteiro etc.).
- Um registro pode estar nos dois CSVs (município costeiro que também está no
  Sistema Marinho): ele aparece uma única vez, com as marcações
  `costeiro` e `marinho`.
- UF: usa SIGLA_UF (municípios costeiros) e, quando não existe, converte o
  "State - parsed" (ex.: "Santa Catarina" -> "SC").

Uso:
    python preparar_dados.py
    python preparar_dados.py --costeiras ../EspeciesCosteiras.csv --marinhas ../EspeciesMarinhas.csv
    python preparar_dados.py --amostra 2000000   # versão menor, p/ testes ou deploy leve

Saída: data/ocorrencias/parte_0.parquet, parte_1.parquet, ...

Biblioteca: duckdb  (pip install duckdb)
"""

import argparse
import glob
import os
import shutil
import time

import duckdb

PASTA = os.path.dirname(os.path.abspath(__file__))

UFS = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA",
    "ceara": "CE", "distrito federal": "DF", "espirito santo": "ES", "goias": "GO",
    "maranhao": "MA", "mato grosso": "MT", "mato grosso do sul": "MS",
    "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ",
    "rio grande do norte": "RN", "rio grande do sul": "RS", "rondonia": "RO",
    "roraima": "RR", "santa catarina": "SC", "sao paulo": "SP", "sergipe": "SE",
    "tocantins": "TO",
}


def ler_csv(caminho):
    caminho = caminho.replace("\\", "/").replace("'", "''")
    return (f"read_csv('{caminho}', all_varchar=true, header=true, quote='\"', "
            f"escape='\"', ignore_errors=true, parallel=true)")


def normalizar(caminho, costeiro):
    """SELECT que padroniza um dos CSVs."""
    def txt(col):
        return f"NULLIF(trim(\"{col}\"), '')"

    casos_uf = " ".join(f"WHEN '{n}' THEN '{s}'" for n, s in UFS.items())
    uf_estado = f"CASE strip_accents(lower(trim(\"State - parsed\"))) {casos_uf} END"
    if costeiro:
        mun = f"{txt('NM_MUN')} AS municipio, {txt('CD_MUN')} AS cd_mun, " \
              f"COALESCE({txt('SIGLA_UF')}, {uf_estado}) AS uf"
    else:
        mun = f"NULL::VARCHAR AS municipio, NULL::VARCHAR AS cd_mun, {uf_estado} AS uf"

    return f"""
        SELECT
            "Record ID"                                         AS id,
            {txt('Data Resource Name')}                         AS conjunto_dados,
            {txt('Institution Code')}                           AS instituicao,
            {txt('Scientific Name (intepreted)')}               AS taxon,
            {txt('Species')}                                    AS especie,
            {txt('Vernacular name')}                            AS nome_popular,
            {txt('Taxon Rank')}                                 AS nivel_taxonomico,
            {txt('Kingdom')}  AS reino,  {txt('Phylum')} AS filo,
            {txt('Class')}    AS classe, {txt('Order')}  AS ordem,
            {txt('Family')}   AS familia, {txt('Genus')} AS genero,
            TRY_CAST("Decimal latitude (WGS84)"  AS DOUBLE)    AS lat,
            TRY_CAST("Decimal longitude (WGS84)" AS DOUBLE)    AS lon,
            CASE WHEN TRY_CAST("Year" AS SMALLINT) BETWEEN 1500 AND year(current_date)
                 THEN TRY_CAST("Year" AS SMALLINT) END          AS ano,
            TRY_CAST("Month" AS TINYINT)                        AS mes,
            {txt('Basis Of Record')}                            AS base_registro,
            TRY_CAST("Individual count" AS INTEGER)             AS n_individuos,
            TRY_CAST("Maximum Depth In Meters" AS FLOAT)        AS profundidade_max,
            {mun}
        FROM {ler_csv(caminho)}
        WHERE TRY_CAST("Decimal latitude (WGS84)" AS DOUBLE) IS NOT NULL
          AND TRY_CAST("Decimal longitude (WGS84)" AS DOUBLE) IS NOT NULL
    """


def main():
    pai = os.path.dirname(PASTA)
    p = argparse.ArgumentParser()
    p.add_argument("--costeiras", default=os.path.join(pai, "EspeciesCosteiras.csv"))
    p.add_argument("--marinhas", default=os.path.join(pai, "EspeciesMarinhas.csv"))
    p.add_argument("--saida", default=os.path.join(PASTA, "data", "ocorrencias"),
                   help="pasta de saída; os dados são divididos em arquivos de ~90 MB "
                        "(o GitHub não aceita arquivos > 100 MB)")
    p.add_argument("--amostra", type=int, default=0,
                   help="se > 0, grava só N registros aleatórios (arquivo menor)")
    p.add_argument("--memoria", default="8GB", help="limite de memória do DuckDB")
    args = p.parse_args()

    os.makedirs(args.saida, exist_ok=True)
    for antigo in glob.glob(os.path.join(args.saida, "*.parquet")):
        os.remove(antigo)
    tmp = os.path.join(os.path.dirname(args.saida), "_tmp")
    os.makedirs(tmp, exist_ok=True)
    tmp_c = os.path.join(tmp, "costeiras.parquet").replace("\\", "/")
    tmp_m = os.path.join(tmp, "marinhas.parquet").replace("\\", "/")
    saida = args.saida.replace("\\", "/")

    con = duckdb.connect()
    con.execute(f"SET memory_limit='{args.memoria}'")
    con.execute(f"SET temp_directory='{tmp.replace(chr(92), '/')}'")
    con.execute("SET preserve_insertion_order=false")
    inicio = time.time()

    for nome, csv, destino, costeiro in [("costeiras", args.costeiras, tmp_c, True),
                                         ("marinhas", args.marinhas, tmp_m, False)]:
        print(f"Lendo {nome}: {csv}", flush=True)
        con.execute(f"COPY ({normalizar(csv, costeiro)}) TO '{destino}' "
                    f"(FORMAT parquet, COMPRESSION zstd)")
        n = con.execute(f"SELECT count(*) FROM '{destino}'").fetchone()[0]
        print(f"  {n:,} registros com coordenadas ({time.time() - inicio:.0f}s)", flush=True)

    print("Unindo e removendo duplicados...", flush=True)
    final = f"""
        WITH c AS (SELECT * FROM '{tmp_c}'),
             m AS (SELECT * FROM '{tmp_m}'),
             ids_m AS (SELECT DISTINCT id FROM m)
        SELECT c.*, true AS costeiro, (c.id IN (SELECT id FROM ids_m)) AS marinho FROM c
        UNION ALL
        SELECT m.*, false AS costeiro, true AS marinho
        FROM m ANTI JOIN c USING (id)
    """
    if args.amostra > 0:
        final = f"SELECT * FROM ({final}) USING SAMPLE {args.amostra} ROWS"
    # Ordenar agrupa valores repetidos -> arquivo bem menor e filtros mais rápidos
    con.execute(f"""
        COPY (SELECT * FROM ({final}) ORDER BY reino, classe, familia, especie, ano)
        TO '{saida}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 250000,
                      FILE_SIZE_BYTES '90MB', FILENAME_PATTERN 'parte_{{i}}', OVERWRITE_OR_IGNORE)
    """)

    n, nc, nm = con.execute(
        f"SELECT count(*), count(*) FILTER (costeiro), count(*) FILTER (marinho) "
        f"FROM '{saida}/*.parquet'"
    ).fetchone()
    for f in (tmp_c, tmp_m):
        os.remove(f)
    shutil.rmtree(tmp, ignore_errors=True)
    partes = glob.glob(os.path.join(args.saida, "*.parquet"))
    mb = sum(os.path.getsize(f) for f in partes) / 1e6
    print(f"\nFinalizado em {(time.time() - inicio) / 60:.1f} min")
    print(f"{n:,} registros ({nc:,} costeiros, {nm:,} marinhos) -> {args.saida} ({len(partes)} arquivos, {mb:.0f} MB)")


if __name__ == "__main__":
    main()
