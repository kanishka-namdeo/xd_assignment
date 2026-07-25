"""Audit trail and processing queue data access."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.audit import AuditLog, ProcessingQueue


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _compute_hash(self, audit_log: AuditLog) -> str:
        """Compute SHA-256 hash chaining with previous hash."""
        payload = json.dumps(
            {
                "id": str(audit_log.id),
                "document_id": str(audit_log.document_id),
                "action": audit_log.action,
                "performed_by": audit_log.performed_by,
                "timestamp": audit_log.timestamp.isoformat() if audit_log.timestamp else None,
                "changes": audit_log.changes,
                "previous_hash": audit_log.previous_hash,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    async def create(self, **kwargs) -> AuditLog:
        # Remove hash from kwargs - we compute it after setting id/timestamp
        kwargs.pop("hash", None)
        audit_log = AuditLog(**kwargs)
        # Generate id and timestamp client-side so we can include them in the hash
        if audit_log.id is None:
            audit_log.id = uuid.uuid4()
        if audit_log.timestamp is None:
            audit_log.timestamp = datetime.now(timezone.utc)
        audit_log.hash = self._compute_hash(audit_log)
        self.session.add(audit_log)
        await self.session.flush()
        await self.session.refresh(audit_log)
        return audit_log

    async def get_by_id(self, audit_id: UUID) -> AuditLog | None:
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.id == audit_id)
        )
        return result.scalar_one_or_none()

    async def get_by_document(self, document_id: UUID) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.document_id == document_id)
            .order_by(AuditLog.timestamp.desc())
        )
        return list(result.scalars().all())

    async def verify_chain(self, document_id: UUID) -> bool:
        """Verify the hash chain integrity for a document's audit log."""
        logs = await self.get_by_document(document_id)
        if not logs:
            return True
        # Verify in reverse chronological order (oldest first for chain verification)
        logs_sorted = sorted(logs, key=lambda x: x.timestamp)
        prev_hash = None
        for log in logs_sorted:
            expected_hash = hashlib.sha256(
                json.dumps(
                    {
                        "id": str(log.id),
                        "document_id": str(log.document_id),
                        "action": log.action,
                        "performed_by": log.performed_by,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "changes": log.changes,
                        "previous_hash": prev_hash,
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            if log.hash != expected_hash:
                return False
            prev_hash = log.hash
        return True


class ProcessingQueueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> ProcessingQueue:
        entry = ProcessingQueue(**kwargs)
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def get_by_id(self, queue_id: UUID) -> ProcessingQueue | None:
        result = await self.session.execute(
            select(ProcessingQueue).where(ProcessingQueue.id == queue_id)
        )
        return result.scalar_one_or_none()

    async def get_by_document(self, document_id: UUID) -> list[ProcessingQueue]:
        result = await self.session.execute(
            select(ProcessingQueue).where(ProcessingQueue.document_id == document_id)
        )
        return list(result.scalars().all())

    async def get_pending_queue_items(self) -> list[ProcessingQueue]:
        result = await self.session.execute(
            select(ProcessingQueue)
            .where(ProcessingQueue.status == "pending")
            .order_by(ProcessingQueue.priority.desc(), ProcessingQueue.created_at)
        )
        return list(result.scalars().all())

    async def update(self, entry: ProcessingQueue) -> ProcessingQueue:
        await self.session.merge(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry
