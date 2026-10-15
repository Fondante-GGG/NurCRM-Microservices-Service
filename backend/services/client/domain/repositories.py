from typing import Optional, List, Protocol
import uuid
from backend.services.client.domain.models import Client, ClientDocument


class ClientRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, client_id: uuid.UUID) -> Optional[Client]:
        ...

    def get_by_phone(self, company_id: uuid.UUID, phone: str) -> Optional[Client]:
        ...

    def list_by_company(self, company_id: uuid.UUID, search: Optional[str] = None) -> List[Client]:
        ...

    def save(self, client: Client) -> None:
        ...

    def delete(self, company_id: uuid.UUID, client_id: uuid.UUID) -> None:
        ...


class ClientDocumentRepository(Protocol):
    def get_by_id(self, company_id: uuid.UUID, doc_id: uuid.UUID) -> Optional[ClientDocument]:
        ...

    def list_by_client(self, company_id: uuid.UUID, client_id: uuid.UUID) -> List[ClientDocument]:
        ...

    def save(self, doc: ClientDocument) -> None:
        ...

    def delete(self, company_id: uuid.UUID, doc_id: uuid.UUID) -> None:
        ...
