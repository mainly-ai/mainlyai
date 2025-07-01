import json
from typing import Optional
from mirmod import miranda
from mirmod.utils import logger
from io import BytesIO
import pathlib


class StorageInterface:
    def __init__(
        self, sctx: miranda.Security_context, storage_policy: miranda.Storage_policy
    ):
        self.sctx = sctx
        self.storage_policy = storage_policy
        try:
            self.details = json.loads(storage_policy.details)
        except Exception as e:
            logger.error(f"storage_policy.details is not valid JSON: {e}")
            raise ValueError("storage_policy.details is not valid JSON")

    def download(
        self,
        identifier: str | int,
        output_filename: Optional[pathlib.Path] = None,
        to_buffer: bool = False,
        overwrite: bool = False,
        stream_chunk_size: int = 1024 * 512,
    ) -> pathlib.Path | BytesIO:
        raise NotImplementedError

    def upload(self, input: pathlib.Path | BytesIO) -> int | str:
        raise NotImplementedError
