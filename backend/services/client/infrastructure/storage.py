import os
from typing import Optional
from pathlib import Path
import uuid
from backend.services.client.application.use_cases import FileStorage


class LocalDiskFileStorage(FileStorage):
    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            default_path = Path("/var/lib/crm/media")
            if default_path.exists() and os.access(str(default_path), os.W_OK):
                self.base_dir = default_path
            else:
                self.base_dir = Path("/tmp/nurcrm/media")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_target_dir(self, company_id: uuid.UUID, client_id: uuid.UUID) -> Path:
        target = self.base_dir / "clients" / str(company_id) / str(client_id)
        target.mkdir(parents=True, exist_ok=True)
        return target

    def save(self, company_id: uuid.UUID, client_id: uuid.UUID, file_id: uuid.UUID, content: bytes) -> str:
        target_dir = self._get_target_dir(company_id, client_id)
        file_path = target_dir / str(file_id)
        with open(file_path, "wb") as f:
            f.write(content)
        return str(file_path)

    def get_path(self, company_id: uuid.UUID, client_id: uuid.UUID, file_id: uuid.UUID) -> str:
        return str(self._get_target_dir(company_id, client_id) / str(file_id))
