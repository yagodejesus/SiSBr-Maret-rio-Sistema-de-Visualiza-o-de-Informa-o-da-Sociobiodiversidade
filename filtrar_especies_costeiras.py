"""
Filtra os registros de ocorrência de espécies (EspeciesTotal*.csv) mantendo
apenas os pontos que caem dentro dos polígonos de um GeoJSON.

Os CSVs são grandes demais para caber na memória (~3 GB cada), então cada
arquivo é lido em blocos (chunks) e o resultado é gravado incrementalmente
num único CSV de saída.

Uso:
    # Municípios costeiros (padrão), anexando o município de cada ponto
    python filtrar_especies_costeiras.py

    # Sistema Marinho (um único polígono, sem colunas para anexar)
    python filtrar_especies_costeiras.py --poligonos SistemaMarinho.geojson --colunas "" --saida EspeciesMarinhas.csv

Bibliotecas: pandas, geopandas, shapely  (pip install geopandas)
"""

import argparse
import csv
import glob
import os
import time

import geopandas as gpd
import pandas as pd
import shapely

PASTA = os.path.dirname(os.path.abspath(__file__))

COL_LAT = "Decimal latitude (WGS84)"
COL_LON = "Decimal longitude (WGS84)"


def carregar_poligonos(caminho, colunas):
    pol = gpd.read_file(caminho)
    # Os GeoJSONs estão em SIRGAS 2000 (EPSG:4674); os pontos estão em WGS84.
    # A diferença entre os dois é submétrica, mas convertemos para ficar correto.
    pol = pol.to_crs("EPSG:4326")
    # Corrige geometrias inválidas (auto-interseções etc.)
    pol["geometry"] = pol.geometry.make_valid()
    pol = pol[colunas + ["geometry"]]
    pol.sindex  # constrói o índice espacial uma única vez
    return pol


def filtrar_chunk(df, poligonos, area, colunas):
    lat = pd.to_numeric(df[COL_LAT], errors="coerce")
    lon = pd.to_numeric(df[COL_LON], errors="coerce")

    # Pré-filtro barato: descarta coordenadas vazias e fora do retângulo envolvente
    minx, miny, maxx, maxy = poligonos.total_bounds
    ok = lat.notna() & lon.notna() & lon.between(minx, maxx) & lat.between(miny, maxy)
    if not ok.any():
        return df.iloc[0:0]

    # "intersects" inclui pontos exatamente sobre a borda do polígono
    dentro = shapely.intersects_xy(area, lon[ok].values, lat[ok].values)
    df = df[ok][dentro]
    if not colunas or df.empty:
        return df

    # Anexa os atributos do polígono (ex.: município) a cada ponto
    pontos = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(lon[df.index], lat[df.index]),
        crs="EPSG:4326",
    )
    junto = gpd.sjoin(pontos, poligonos, how="left", predicate="intersects")
    # Um ponto na divisa entre dois polígonos aparece duas vezes: mantém um só
    junto = junto[~junto.index.duplicated(keep="first")]
    return pd.DataFrame(junto.drop(columns=["geometry", "index_right"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--poligonos", default=os.path.join(PASTA, "MunicipiosCosteiros.geojson"))
    parser.add_argument("--colunas", default="CD_MUN,NM_MUN,SIGLA_UF",
                        help='atributos do GeoJSON anexados a cada ponto, separados por vírgula ("" para nenhum)')
    parser.add_argument("--pasta-csv", default=os.path.join(PASTA, "EspeciesTotal"))
    parser.add_argument("--saida", default=os.path.join(PASTA, "EspeciesCosteiras.csv"))
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    args = parser.parse_args()
    colunas = [c.strip() for c in args.colunas.split(",") if c.strip()]

    arquivos = sorted(glob.glob(os.path.join(args.pasta_csv, "EspeciesTotal*.csv")))
    if not arquivos:
        raise SystemExit(f"Nenhum EspeciesTotal*.csv encontrado em {args.pasta_csv}")

    print(f"Carregando {os.path.basename(args.poligonos)}...")
    poligonos = carregar_poligonos(args.poligonos, colunas)
    # União de todos os polígonos, "preparada" para testes ponto-no-polígono
    # rápidos mesmo com centenas de milhares de vértices
    area = poligonos.geometry.union_all()
    shapely.prepare(area)
    print(f"  {len(poligonos)} polígono(s) carregado(s)")

    # O CSV tem a coluna "Data Resource ID" repetida; o pandas renomeia a
    # segunda para "Data Resource ID.1". Guardamos o cabeçalho original para
    # escrever a saída com os mesmos nomes de coluna da entrada.
    with open(arquivos[0], encoding="utf-8", newline="") as f:
        cabecalho = next(csv.reader(f))
    cabecalho_saida = cabecalho + colunas

    with open(args.saida, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerow(cabecalho_saida)

    total_lido = 0
    total_mantido = 0
    inicio = time.time()

    for arquivo in arquivos:
        nome = os.path.basename(arquivo)
        lido = mantido = 0
        leitor = pd.read_csv(
            arquivo,
            dtype=str,  # mantém todos os valores exatamente como no original
            keep_default_na=False,
            chunksize=args.chunksize,
            encoding="utf-8",
            on_bad_lines="warn",
        )
        for chunk in leitor:
            filtrado = filtrar_chunk(chunk, poligonos, area, colunas)
            lido += len(chunk)
            mantido += len(filtrado)
            if len(filtrado):
                filtrado.to_csv(
                    args.saida, mode="a", header=False, index=False,
                    encoding="utf-8", quoting=csv.QUOTE_ALL,
                )
            print(f"  {nome}: {lido:,} lidos, {mantido:,} dentro "
                  f"({time.time() - inicio:.0f}s)", flush=True)

        total_lido += lido
        total_mantido += mantido
        print(f"{nome} concluído: {mantido:,} de {lido:,} registros mantidos")

    print(f"\nFinalizado em {(time.time() - inicio) / 60:.1f} min")
    print(f"Total: {total_mantido:,} de {total_lido:,} registros dentro dos polígonos")
    print(f"Saída: {args.saida}")


if __name__ == "__main__":
    main()
