"""Bounded vector cleanup keeps SQLite source records and citation snapshots intact."""
import asyncio
import json

from .db import now
from .errors import ApiError


class Reconciler:
    def __init__(self, db, vectors):
        self.db, self.vectors = db, vectors
        self.suspended = False
        self._task = None
        self._closing = False
        self._busy = False

    def start(self):
        self._task = asyncio.create_task(self.loop())

    def pinned(self):
        queries = {generation for row in self.db.rows("SELECT snapshot_json FROM query_runs WHERE state IN ('queued','running')")
                   for generation in json.loads(row["snapshot_json"]).get("generations", [])}
        writers = {row["generation_id"] for row in self.db.rows("SELECT generation_id FROM jobs WHERE generation_id IS NOT NULL AND state IN ('extracting','indexing','running','pausing','cancelling')")}
        return queries | writers

    def inspect(self, limit=20):
        # Staged work is not automatically discarded: a manually resumed job may own it.
        return self.db.rows("SELECT g.id,g.state,g.expected_chunks,count(c.id) AS stored_chunks,j.id AS job_id,j.state AS job_state FROM index_generations g LEFT JOIN chunks c ON c.generation_id=g.id LEFT JOIN jobs j ON j.generation_id=g.id WHERE g.state='staging' GROUP BY g.id ORDER BY g.created_at LIMIT ?", (limit,))

    async def run_once(self, limit=10):
        pinned = self.pinned()
        records = self.db.rows("SELECT * FROM vector_cleanup WHERE state='pending' ORDER BY created_at LIMIT ?", (limit,))
        completed = []
        for record in records:
            generation = record["generation_id"]
            if generation in pinned or self.suspended:
                continue
            # Publication may reactivate a historical generation while cleanup waits.
            active = self.db.one("SELECT 1 AS n FROM documents WHERE active_generation_id=? AND deleted_at IS NULL", (generation,))
            if active:
                self.db.execute("UPDATE vector_cleanup SET state='retained',updated_at=? WHERE generation_id=?", (now(), generation))
                continue
            try:
                await self.vectors.delete_generation(generation)
                with self.db.transaction() as connection:
                    if record["reason"] == "deleted":
                        connection.execute("DELETE FROM identifiers WHERE chunk_uuid IN (SELECT chunk_uuid FROM chunks WHERE generation_id=?)", (generation,))
                        connection.execute("DELETE FROM chunk_sources WHERE chunk_uuid IN (SELECT chunk_uuid FROM chunks WHERE generation_id=?)", (generation,))
                        connection.execute("DELETE FROM chunks WHERE generation_id=?", (generation,))
                    connection.execute("UPDATE vector_cleanup SET state='complete',error_code=NULL,updated_at=? WHERE generation_id=?", (now(), generation))
                completed.append(generation)
            except Exception as error:
                self.db.execute("UPDATE vector_cleanup SET error_code=?,updated_at=? WHERE generation_id=?", (error.code if isinstance(error, ApiError) else "cleanup_failed", now(), generation))
        return {"completed": completed, "pinned": sorted(pinned), "staged": self.inspect()}

    async def loop(self):
        while not self._closing:
            if not self.suspended:
                self._busy = True
                try:
                    await self.run_once()
                finally:
                    self._busy = False
            await asyncio.sleep(1)

    async def quiesce(self):
        self.suspended = True
        while self._busy:
            await asyncio.sleep(0.1)

    async def close(self):
        self._closing = True
        if self._task:
            await self._task
