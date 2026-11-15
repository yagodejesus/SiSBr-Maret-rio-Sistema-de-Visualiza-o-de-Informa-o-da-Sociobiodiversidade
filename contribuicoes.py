"""
Armazenamento das contribuições dos usuários (novas características no mapa).

- Local: SQLite em data/contribuicoes.db
- Railway: defina DATABASE_URL (plugin PostgreSQL) para que as contribuições
  sobrevivam a novos deploys.
"""

import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (Column, DateTime, Float, Integer, MetaData, String, Table,
                        Text, create_engine, delete, insert, select)

PASTA = os.path.dirname(os.path.abspath(__file__))

CATEGORIAS = [
    "Avistamento de espécie",
    "Área de reprodução / desova",
    "Encalhe ou animal ferido",
    "Ameaça / impacto ambiental",
    "Poluição / lixo",
    "Habitat (recife, mangue, banco de algas...)",
    "Outra característica",
]


def _url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        os.makedirs(os.path.join(PASTA, "data"), exist_ok=True)
        return "sqlite:///" + os.path.join(PASTA, "data", "contribuicoes.db")
    # O Railway entrega postgres://...; o SQLAlchemy usa o driver psycopg 3
    for antigo in ("postgres://", "postgresql://"):
        if url.startswith(antigo):
            return "postgresql+psycopg://" + url[len(antigo):]
    return url


engine = create_engine(_url(), pool_pre_ping=True)
meta = MetaData()
tabela = Table(
    "contribuicoes", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("criado_em", DateTime(timezone=True), nullable=False),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("categoria", String(120), nullable=False),
    Column("caracteristica", String(200), nullable=False),
    Column("valor", String(200)),
    Column("especie", String(200)),
    Column("descricao", Text),
    Column("autor", String(120)),
    Column("data_observacao", String(10)),
)
meta.create_all(engine)

COLUNAS = [c.name for c in tabela.columns]


def adicionar(**dados):
    dados["criado_em"] = datetime.now(timezone.utc)
    with engine.begin() as con:
        con.execute(insert(tabela).values(**dados))


def listar():
    with engine.connect() as con:
        df = pd.read_sql(select(tabela).order_by(tabela.c.id.desc()), con)
    return df if len(df) else pd.DataFrame(columns=COLUNAS)


def excluir(ids):
    with engine.begin() as con:
        con.execute(delete(tabela).where(tabela.c.id.in_(list(ids))))
