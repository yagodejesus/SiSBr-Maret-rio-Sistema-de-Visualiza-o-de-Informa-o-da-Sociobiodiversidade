"""
Consultas ao Parquet de ocorrências com DuckDB.

O arquivo não é carregado inteiro na memória: cada consulta lê só as colunas
e os blocos necessários, o que permite rodar com milhões de registros mesmo
num container pequeno (Railway).
"""

import glob
import json
import math
import os
import threading
import urllib.request
from functools import lru_cache

import duckdb

PASTA = os.path.dirname(os.path.abspath(__file__))
# Pasta com os .parquet gerados por preparar_dados.py (podem ser vários arquivos)
CAMINHO = os.environ.get("DATA_PATH", os.path.join(PASTA, "data", "ocorrencias"))
DATA_URL = os.environ.get("DATA_URL", "")

# Colunas que aceitam filtro por lista de valores
FILTROS_LISTA = ["reino", "classe", "ordem", "familia", "especie", "uf",
                 "municipio", "base_registro", "conjunto_dados"]

_con = None
_trava = threading.Lock()


def arquivos():
    return sorted(glob.glob(os.path.join(CAMINHO, "*.parquet")))


def baixar_se_preciso():
    """Opcional: se a pasta estiver vazia e DATA_URL apontar para um .parquet, baixa-o."""
    if arquivos() or not DATA_URL:
        return
    os.makedirs(CAMINHO, exist_ok=True)
    print(f"Baixando dados de {DATA_URL} ...", flush=True)
    destino = os.path.join(CAMINHO, "download.parquet")
    urllib.request.urlretrieve(DATA_URL, destino + ".part")
    os.replace(destino + ".part", destino)
    print("Download concluído.", flush=True)


def disponivel():
    return bool(arquivos())


def conexao():
    global _con
    with _trava:
        if _con is None:
            baixar_se_preciso()
            if not disponivel():
                raise FileNotFoundError(
                    f"Arquivo de dados não encontrado: {CAMINHO}. Rode "
                    f"'python preparar_dados.py' ou defina DATA_URL.")
            _con = duckdb.connect()
            _con.execute(f"SET memory_limit='{os.environ.get('DUCKDB_MEMORY', '1GB')}'")
            lista = ", ".join("'" + a.replace("\\", "/").replace("'", "''") + "'"
                              for a in arquivos())
            _con.execute(f"CREATE VIEW oc AS SELECT * FROM read_parquet([{lista}])")
    # Um cursor por chamada: seguro para os vários threads do servidor
    return _con.cursor()


def consulta(sql, params=None):
    cur = conexao()
    return cur.execute(sql, params or []).df()


def montar_where(f):
    """Converte o dicionário de filtros em (cláusula WHERE, parâmetros)."""
    cond, par = [], []
    rec = set(f.get("recorte") or [])
    if rec == {"costeiro"}:
        cond.append("costeiro")
    elif rec == {"marinho"}:
        cond.append("marinho")

    for col in FILTROS_LISTA:
        valores = f.get(col)
        if valores:
            cond.append(f"list_contains(?, {col})")
            par.append(list(valores))

    anos = f.get("anos")
    if anos:
        trecho = "ano BETWEEN ? AND ?"
        if f.get("sem_ano", True):
            trecho = f"({trecho} OR ano IS NULL)"
        cond.append(trecho)
        par += [int(anos[0]), int(anos[1])]
    elif not f.get("sem_ano", True):
        cond.append("ano IS NOT NULL")

    if f.get("so_especie"):
        cond.append("especie IS NOT NULL")

    caixa = f.get("caixa")  # [lon_min, lat_min, lon_max, lat_max] do mapa
    if caixa:
        cond.append("lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?")
        par += [caixa[0], caixa[2], caixa[1], caixa[3]]

    return ("WHERE " + " AND ".join(cond)) if cond else "", par


def _chave(f):
    return json.dumps(f, sort_keys=True, default=str)


# ---------------------------------------------------------------- metadados
@lru_cache(maxsize=1)
def faixa_anos():
    r = consulta("SELECT min(ano) AS a, max(ano) AS b FROM oc")
    return int(r.a[0]), int(r.b[0])


@lru_cache(maxsize=256)
def _opcoes(col, chave, limite):
    where, par = montar_where(json.loads(chave))
    extra = f"{'AND' if where else 'WHERE'} {col} IS NOT NULL"
    return consulta(
        f"SELECT {col} AS v, count(*) AS n FROM oc {where} {extra} "
        f"GROUP BY 1 ORDER BY n DESC LIMIT {int(limite)}", par)


def opcoes(col, filtros=None, limite=500):
    df = _opcoes(col, _chave(filtros or {}), limite)
    return [{"label": f"{v} ({n:,})".replace(",", "."), "value": v}
            for v, n in zip(df.v, df.n)]


@lru_cache(maxsize=256)
def _busca_especie(texto, chave):
    where, par = montar_where(json.loads(chave))
    cond = "especie IS NOT NULL"
    if texto:
        cond += " AND (especie ILIKE ? OR nome_popular ILIKE ?)"
        par = par + [f"%{texto}%", f"%{texto}%"]
    where = f"{where} AND {cond}" if where else f"WHERE {cond}"
    return consulta(f"""
        SELECT especie AS v, any_value(nome_popular) AS pop, count(*) AS n
        FROM oc {where} GROUP BY 1 ORDER BY n DESC LIMIT 60""", par)


def busca_especie(texto, filtros):
    df = _busca_especie((texto or "").strip(), _chave(filtros))
    return [{"label": f"{v} — {p}" if p else v, "value": v}
            for v, p in zip(df.v, df["pop"])]


# ---------------------------------------------------------------- análises
@lru_cache(maxsize=128)
def _kpis(chave):
    where, par = montar_where(json.loads(chave))
    return consulta(f"""
        SELECT count(*) AS registros,
               count(DISTINCT especie) AS especies,
               count(DISTINCT familia) AS familias,
               count(DISTINCT cd_mun) AS municipios,
               min(ano) AS ano_min, max(ano) AS ano_max
        FROM oc {where}""", par).iloc[0].to_dict()


def kpis(f):
    return _kpis(_chave(f))


@lru_cache(maxsize=128)
def _por_ano(chave):
    where, par = montar_where(json.loads(chave))
    extra = f"{'AND' if where else 'WHERE'} ano IS NOT NULL"
    return consulta(f"""
        SELECT ano, count(*) AS registros, count(DISTINCT especie) AS especies
        FROM oc {where} {extra} GROUP BY ano ORDER BY ano""", par)


def por_ano(f):
    return _por_ano(_chave(f))


@lru_cache(maxsize=256)
def _top(col, chave, n):
    where, par = montar_where(json.loads(chave))
    extra = f"{'AND' if where else 'WHERE'} {col} IS NOT NULL"
    pop = ", any_value(nome_popular) AS nome_popular" if col == "especie" else ""
    return consulta(f"""
        SELECT {col} AS categoria, count(*) AS registros {pop}
        FROM oc {where} {extra} GROUP BY 1 ORDER BY registros DESC LIMIT {int(n)}""", par)


def top(col, f, n=15):
    return _top(col, _chave(f), n)


@lru_cache(maxsize=64)
def _tabela_especies(chave):
    where, par = montar_where(json.loads(chave))
    extra = f"{'AND' if where else 'WHERE'} especie IS NOT NULL"
    return consulta(f"""
        SELECT especie AS "Espécie", any_value(nome_popular) AS "Nome popular",
               any_value(classe) AS "Classe", any_value(familia) AS "Família",
               count(*) AS "Registros", count(DISTINCT cd_mun) AS "Municípios",
               min(ano) AS "Primeiro ano", max(ano) AS "Último ano"
        FROM oc {where} {extra} GROUP BY especie ORDER BY "Registros" DESC LIMIT 500""", par)


def tabela_especies(f):
    return _tabela_especies(_chave(f))


def exportar(f, limite=200_000):
    where, par = montar_where(f)
    return consulta(f"SELECT * EXCLUDE (costeiro, marinho), costeiro, marinho "
                    f"FROM oc {where} LIMIT {int(limite)}", par)


# ---------------------------------------------------------------- mapa
@lru_cache(maxsize=64)
def _grade(chave, passo):
    where, par = montar_where(json.loads(chave))
    p = float(passo)
    return consulta(f"""
        SELECT floor(lat / {p}) * {p} + {p / 2} AS lat,
               floor(lon / {p}) * {p} + {p / 2} AS lon,
               count(*) AS registros,
               approx_count_distinct(especie) AS especies
        FROM oc {where}
        GROUP BY 1, 2 ORDER BY registros DESC LIMIT 60000""", par)


def grade(f, passo):
    return _grade(_chave(f), passo)


@lru_cache(maxsize=64)
def _pontos(chave, n):
    where, par = montar_where(json.loads(chave))
    return consulta(f"""
        SELECT * FROM (
            SELECT id, lat, lon, coalesce(especie, taxon) AS especie, nome_popular,
                   ano, municipio, uf, conjunto_dados
            FROM oc {where}
        ) USING SAMPLE reservoir({int(n)} ROWS) REPEATABLE (42)""", par)


def pontos(f, n=8000):
    return _pontos(_chave(f), n)


def detalhe(id_registro):
    df = consulta("SELECT * FROM oc WHERE id = ? LIMIT 1", [id_registro])
    return df.iloc[0].to_dict() if len(df) else None


def celula(f, lat, lon, passo):
    """Resumo de uma célula da grade: espécies mais registradas ali."""
    f = dict(f, caixa=[lon - passo / 2, lat - passo / 2, lon + passo / 2, lat + passo / 2])
    where, par = montar_where(f)
    return consulta(f"""
        SELECT coalesce(especie, taxon) AS especie, any_value(nome_popular) AS pop,
               count(*) AS n
        FROM oc {where} GROUP BY 1 ORDER BY n DESC LIMIT 8""", par)


def limites(f):
    """Centro e zoom que enquadram 98% dos registros filtrados."""
    where, par = montar_where(f)
    r = consulta(f"""
        SELECT quantile_cont(lat, 0.01) AS la0, quantile_cont(lat, 0.99) AS la1,
               quantile_cont(lon, 0.01) AS lo0, quantile_cont(lon, 0.99) AS lo1
        FROM oc {where}""", par).iloc[0]
    if r.isna().any():
        return None
    vao = max(r.la1 - r.la0, (r.lo1 - r.lo0) * 0.75, 0.02)
    zoom = max(2.5, min(13.0, math.log2(360 / vao) - 0.6))
    return {"lat": (r.la0 + r.la1) / 2, "lon": (r.lo0 + r.lo1) / 2}, zoom
