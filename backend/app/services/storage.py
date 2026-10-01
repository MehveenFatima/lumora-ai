import os
from typing import Optional
from backend.app.core.config import settings
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

_LOCAL_ROOT_PARTS = ("backend", "data", "documents")


def _safe_storage_name(filename: str) -> str:
    """
    Reduces a client-supplied filename to a single safe path component, so an upload can never
    be written (or later read) outside its own document folder (e.g. names containing "../").
    """
    name = (filename or "").replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip().lstrip(".")
    return name or "document"


def _within(base_dir: str, path: str) -> bool:
    base = os.path.realpath(base_dir)
    return os.path.realpath(path).startswith(base + os.sep)


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
        filename = _safe_storage_name(filename)
        path = f"workspace/{workspace_id}/documents/{document_id}/{filename}"

        # 1. Always ensure local persistent disk backup exists
        try:
            root_dir = os.path.join(os.getcwd(), *_LOCAL_ROOT_PARTS)
            local_dir = os.path.join(root_dir, workspace_id, document_id)
            local_file = os.path.join(local_dir, filename)
            if not _within(root_dir, local_file):
                raise ValueError("Refusing to write outside the document storage directory.")
            os.makedirs(local_dir, exist_ok=True)
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
                root_dir = os.path.join(os.getcwd(), *_LOCAL_ROOT_PARTS)
                local_file = os.path.join(root_dir, ws_id, doc_id, fname)
                if _within(root_dir, local_file) and os.path.exists(local_file):
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
