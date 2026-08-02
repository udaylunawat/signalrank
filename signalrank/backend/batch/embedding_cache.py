from collections.abc import Sequence

from api.db_types import gen_uuid
from api.models import Embedding
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession


class PgEmbeddingCache:
    def __init__(self, db: AsyncSession, cfg_fp: str):
        self.db = db
        self.cfg_fp = cfg_fp

    async def fetch(self, text_fps: Sequence[str]) -> dict[str, list[float]]:
        if not text_fps:
            return {}
        fingerprints = list(dict.fromkeys(text_fps))
        vectors: dict[str, list[float]] = {}
        for start in range(0, len(fingerprints), 500):
            result = await self.db.execute(
                select(Embedding.text_fp, Embedding.vector).where(
                    Embedding.text_fp.in_(fingerprints[start : start + 500]),
                    Embedding.cfg_fp == self.cfg_fp,
                )
            )
            vectors.update({row.text_fp: list(row.vector) for row in result.all()})
        return vectors

    async def store_vectors(self, rows: list[tuple[str, list[float]]]) -> None:
        if not rows:
            return
        insert_fn = (
            sqlite_insert
            if self.db.get_bind().dialect.name == "sqlite"
            else postgresql_insert
        )
        for start in range(0, len(rows), 128):
            values = [
                {
                    "id": gen_uuid(),
                    "text_fp": text_fp,
                    "cfg_fp": self.cfg_fp,
                    "vector": vector,
                }
                for text_fp, vector in rows[start : start + 128]
            ]
            statement = insert_fn(Embedding).values(values)
            await self.db.execute(
                statement.on_conflict_do_nothing(
                    index_elements=[Embedding.text_fp, Embedding.cfg_fp]
                )
            )
        await self.db.flush()
