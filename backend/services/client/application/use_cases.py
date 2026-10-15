from __future__ import annotations
import uuid
import os
from typing import Protocol, List, Optional
from datetime import datetime, timezone

from libs.common.domain import Phone
from libs.common.events import EventEnvelope, EventTypes
from libs.common.exceptions import NotFoundError, ClientExistsError, VersionConflictError, ValidationError
from backend.services.client.domain.models import Client, ClientDocument
from backend.services.client.domain.repositories import ClientRepository, ClientDocumentRepository
from backend.services.client.application.dto import (
    CreateClientDTO,
    UpdateClientDTO,
    ClientDTO,
    ClientDocumentDTO,
)


class ClientUnitOfWork(Protocol):
    clients: ClientRepository
    documents: ClientDocumentRepository

    def __enter__(self) -> "ClientUnitOfWork":
        ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        ...

    def commit(self) -> None:
        ...

    def record_outbox(self, event: EventEnvelope) -> None:
        ...


class FileStorage(Protocol):
    def save(self, company_id: uuid.UUID, client_id: uuid.UUID, file_id: uuid.UUID, content: bytes) -> str:
        ...

    def get_path(self, company_id: uuid.UUID, client_id: uuid.UUID, file_id: uuid.UUID) -> str:
        ...


class CreateClientUseCase:
    def __init__(self, uow: ClientUnitOfWork):
        self.uow = uow

    def execute(self, dto: CreateClientDTO) -> ClientDTO:
        with self.uow:
            phone_vo = Phone(dto.phone)
            existing = self.uow.clients.get_by_phone(dto.company_id, phone_vo.value)
            if existing:
                raise ClientExistsError(
                    message=f"Client with phone {phone_vo.value} already exists in this company",
                    details={"existing_client_id": str(existing.id)},
                )

            client = Client(
                id=uuid.uuid4(),
                company_id=dto.company_id,
                full_name=dto.full_name,
                phone=phone_vo,
                birth_date=dto.birth_date,
                status=dto.status,
                notes=dto.notes,
            )
            self.uow.clients.save(client)

            event = EventEnvelope(
                type=EventTypes.CLIENT_CLIENT_CREATED,
                company_id=str(dto.company_id),
                data={
                    "client_id": str(client.id),
                    "full_name": client.full_name,
                    "phone": str(client.phone),
                    "status": client.status,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return ClientDTO(
                id=str(client.id),
                company_id=str(client.company_id),
                full_name=client.full_name,
                phone=str(client.phone),
                birth_date=str(client.birth_date) if client.birth_date else None,
                status=client.status,
                notes=client.notes,
                version=client.version,
            )


class FindOrCreateClientUseCase:
    """Used by booking-service during saga orchestration."""

    def __init__(self, uow: ClientUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, full_name: str, phone: str) -> ClientDTO:
        with self.uow:
            phone_vo = Phone(phone)
            existing = self.uow.clients.get_by_phone(company_id, phone_vo.value)
            if existing:
                return ClientDTO(
                    id=str(existing.id),
                    company_id=str(existing.company_id),
                    full_name=existing.full_name,
                    phone=str(existing.phone),
                    birth_date=str(existing.birth_date) if existing.birth_date else None,
                    status=existing.status,
                    notes=existing.notes,
                    version=existing.version,
                )

            client = Client(
                id=uuid.uuid4(),
                company_id=company_id,
                full_name=full_name,
                phone=phone_vo,
            )
            self.uow.clients.save(client)

            event = EventEnvelope(
                type=EventTypes.CLIENT_CLIENT_CREATED,
                company_id=str(company_id),
                data={
                    "client_id": str(client.id),
                    "full_name": client.full_name,
                    "phone": str(client.phone),
                    "status": client.status,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return ClientDTO(
                id=str(client.id),
                company_id=str(client.company_id),
                full_name=client.full_name,
                phone=str(client.phone),
                birth_date=None,
                status=client.status,
                notes=client.notes,
                version=client.version,
            )


class UpdateClientUseCase:
    def __init__(self, uow: ClientUnitOfWork):
        self.uow = uow

    def execute(self, company_id: uuid.UUID, client_id: uuid.UUID, dto: UpdateClientDTO) -> ClientDTO:
        with self.uow:
            client = self.uow.clients.get_by_id(company_id, client_id)
            if not client:
                raise NotFoundError(f"Client {client_id} not found")

            if dto.expected_version is not None and dto.expected_version != client.version:
                raise VersionConflictError(current_version=client.version)

            if dto.phone is not None:
                new_phone = Phone(dto.phone)
                if new_phone.value != client.phone.value:
                    existing = self.uow.clients.get_by_phone(company_id, new_phone.value)
                    if existing and existing.id != client.id:
                        raise ClientExistsError(f"Phone {new_phone.value} already taken by another client")
                    client.phone = new_phone

            if dto.full_name is not None:
                client.full_name = dto.full_name
            if dto.birth_date is not None:
                client.birth_date = dto.birth_date
            if dto.status is not None:
                client.status = dto.status
            if dto.notes is not None:
                client.notes = dto.notes

            client.increment_version()
            self.uow.clients.save(client)

            event = EventEnvelope(
                type=EventTypes.CLIENT_CLIENT_UPDATED,
                company_id=str(company_id),
                data={
                    "client_id": str(client.id),
                    "full_name": client.full_name,
                    "phone": str(client.phone),
                    "status": client.status,
                },
            )
            self.uow.record_outbox(event)
            self.uow.commit()

            return ClientDTO(
                id=str(client.id),
                company_id=str(client.company_id),
                full_name=client.full_name,
                phone=str(client.phone),
                birth_date=str(client.birth_date) if client.birth_date else None,
                status=client.status,
                notes=client.notes,
                version=client.version,
            )


class UploadDocumentUseCase:
    def __init__(self, uow: ClientUnitOfWork, storage: FileStorage):
        self.uow = uow
        self.storage = storage

    def execute(
        self,
        company_id: uuid.UUID,
        client_id: uuid.UUID,
        file_name: str,
        content: bytes,
        file_comment: Optional[str] = None,
    ) -> ClientDocumentDTO:
        with self.uow:
            client = self.uow.clients.get_by_id(company_id, client_id)
            if not client:
                raise NotFoundError(f"Client {client_id} not found")

            doc_id = uuid.uuid4()
            saved_path = self.storage.save(company_id, client_id, doc_id, content)

            doc = ClientDocument(
                id=doc_id,
                company_id=company_id,
                client_id=client_id,
                file_path=saved_path,
                file_name=file_name,
                file_size=len(content),
                file_comment=file_comment,
            )
            self.uow.documents.save(doc)
            self.uow.commit()

            return ClientDocumentDTO(
                id=str(doc.id),
                company_id=str(doc.company_id),
                client_id=str(doc.client_id),
                file_name=doc.file_name,
                file_size=doc.file_size,
                file_comment=doc.file_comment,
                created_at=doc.created_at.isoformat(),
            )
