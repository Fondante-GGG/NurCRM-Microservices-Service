from typing import Optional, List
import uuid

from libs.common.domain import Phone
from backend.services.client.domain.models import Client, ClientDocument
from backend.services.client.domain.repositories import ClientRepository, ClientDocumentRepository
from backend.services.client.infrastructure.models import ClientModel, ClientDocumentModel


class DjangoClientRepository(ClientRepository):
    def _to_domain(self, m: ClientModel) -> Client:
        return Client(
            id=m.id,
            company_id=m.company_id,
            full_name=m.full_name,
            phone=Phone(m.phone),
            birth_date=m.birth_date,
            status=m.status,
            notes=m.notes,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

    def get_by_id(self, company_id: uuid.UUID, client_id: uuid.UUID) -> Optional[Client]:
        try:
            m = ClientModel.objects.get(company_id=company_id, id=client_id)
            return self._to_domain(m)
        except ClientModel.DoesNotExist:
            return None

    def get_by_phone(self, company_id: uuid.UUID, phone: str) -> Optional[Client]:
        try:
            phone_vo = Phone(phone)
            m = ClientModel.objects.filter(company_id=company_id, phone=phone_vo.value).first()
            if m:
                return self._to_domain(m)
            return None
        except Exception:
            return None

    def list_by_company(self, company_id: uuid.UUID, search: Optional[str] = None) -> List[Client]:
        qs = ClientModel.objects.filter(company_id=company_id)
        if search:
            qs = qs.filter(full_name__icontains=search) | qs.filter(phone__icontains=search)
        return [self._to_domain(m) for m in qs]

    def save(self, client: Client) -> None:
        ClientModel.objects.update_or_create(
            id=client.id,
            defaults={
                "company_id": client.company_id,
                "full_name": client.full_name,
                "phone": str(client.phone),
                "birth_date": client.birth_date,
                "status": client.status,
                "notes": client.notes,
                "version": client.version,
            },
        )

    def delete(self, company_id: uuid.UUID, client_id: uuid.UUID) -> None:
        ClientModel.objects.filter(company_id=company_id, id=client_id).delete()


class DjangoClientDocumentRepository(ClientDocumentRepository):
    def _to_domain(self, m: ClientDocumentModel) -> ClientDocument:
        return ClientDocument(
            id=m.id,
            company_id=m.company_id,
            client_id=m.client_id,
            file_path=m.file_path,
            file_name=m.file_name,
            file_size=m.file_size,
            file_comment=m.file_comment,
            created_at=m.created_at,
        )

    def get_by_id(self, company_id: uuid.UUID, doc_id: uuid.UUID) -> Optional[ClientDocument]:
        try:
            m = ClientDocumentModel.objects.get(company_id=company_id, id=doc_id)
            return self._to_domain(m)
        except ClientDocumentModel.DoesNotExist:
            return None

    def list_by_client(self, company_id: uuid.UUID, client_id: uuid.UUID) -> List[ClientDocument]:
        qs = ClientDocumentModel.objects.filter(company_id=company_id, client_id=client_id)
        return [self._to_domain(m) for m in qs]

    def save(self, doc: ClientDocument) -> None:
        ClientDocumentModel.objects.update_or_create(
            id=doc.id,
            defaults={
                "company_id": doc.company_id,
                "client_id": doc.client_id,
                "file_path": doc.file_path,
                "file_name": doc.file_name,
                "file_size": doc.file_size,
                "file_comment": doc.file_comment,
            },
        )

    def delete(self, company_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        ClientDocumentModel.objects.filter(company_id=company_id, id=doc_id).delete()
