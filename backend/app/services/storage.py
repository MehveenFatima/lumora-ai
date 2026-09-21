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

        # 1. Always ensure local persistent disk backup exists
        try:
            local_dir = os.path.join(os.getcwd(), "backend", "data", "documents", workspace_id, document_id)
            os.makedirs(local_dir, exist_ok=True)
            local_file = os.path.join(local_dir, filename)
            with open(local_file, "wb") as f:
                f.write(file_bytes)
        except Exception as err:
            logger.warning(f"Could not write local document backup: {err}")

        # 2. Upload to Supabase Storage if configured
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
        # 1. Check local persistent disk cache first
        try:
            parts = storage_path.split("/")
            if len(parts) >= 5 and parts[0] == "workspace" and parts[2] == "documents":
                ws_id = parts[1]
                doc_id = parts[3]
                fname = "/".join(parts[4:])
                local_file = os.path.join(os.getcwd(), "backend", "data", "documents", ws_id, doc_id, fname)
                if os.path.exists(local_file):
                    with open(local_file, "rb") as f:
                        return f.read()
        except Exception as err:
            logger.warning(f"Local storage cache read error: {err}")

        # 2. Fall back to Supabase Storage download
        if self._client:
            try:
                res = self._client.storage.from_(self.bucket_name).download(storage_path)
                return res
            except Exception as e:
                logger.error(f"Error downloading from Supabase storage: {e}")
        return None


storage_service = StorageService()
