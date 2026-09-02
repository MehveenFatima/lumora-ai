import os
from typing import Optional
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    def __init__(
        self,
        supabase_url: Optional[str] = settings.supabase_url,
        supabase_key: Optional[str] = settings.supabase_service_role_key,
        bucket_name: str = settings.supabase_storage_bucket,
    ):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.bucket_name = bucket_name
        self._client = None
        self._init_supabase()

    def _init_supabase(self):
        if self.supabase_url and self.supabase_key:
            try:
                from supabase import create_client
                self._client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                logger.warning(f"Could not initialize Supabase Storage client: {e}")

    async def upload_file(
        self,
        workspace_id: str,
        document_id: str,
        filename: str,
        file_bytes: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Stores file under workspace-scoped path:
        workspace/{workspace_id}/documents/{document_id}/{filename}
        """
        path = f"workspace/{workspace_id}/documents/{document_id}/{filename}"

        if self._client:
            try:
                self._client.storage.from_(self.bucket_name).upload(
                    path=path,
                    file=file_bytes,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
                return path
            except Exception as e:
                logger.warning(f"Supabase storage upload failed ({e}). Storing reference path.")

        return path

    async def get_file_bytes(self, storage_path: str) -> Optional[bytes]:
        if self._client:
            try:
                res = self._client.storage.from_(self.bucket_name).download(storage_path)
                return res
            except Exception as e:
                logger.error(f"Error downloading from Supabase storage: {e}")
        return None


storage_service = StorageService()
