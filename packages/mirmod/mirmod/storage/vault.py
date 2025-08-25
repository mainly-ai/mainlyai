from io import BytesIO, SEEK_SET, SEEK_END
import re
import pathlib
from typing import Optional
import urllib
import requests
import mimetypes

from mirmod import miranda
from mirmod.storage import StorageInterface


class ResponseStream(object):
    def __init__(self, request_iterator):
        self._bytes = BytesIO()
        self._iterator = request_iterator

    def _load_all(self):
        self._bytes.seek(0, SEEK_END)
        for chunk in self._iterator:
            self._bytes.write(chunk)

    def _load_until(self, goal_position):
        current_position = self._bytes.seek(0, SEEK_END)
        while current_position < goal_position:
            try:
                current_position += self._bytes.write(next(self._iterator))
            except StopIteration:
                break

    def tell(self):
        return self._bytes.tell()

    def read(self, size=None):
        left_off_at = self._bytes.tell()
        if size is None:
            self._load_all()
        else:
            goal_position = left_off_at + size
            self._load_until(goal_position)

        self._bytes.seek(left_off_at)
        return self._bytes.read(size)

    def seek(self, position, whence=SEEK_SET):
        if whence == SEEK_END:
            self._load_all()
        else:
            self._bytes.seek(position, whence)


class VaultStorageInterface(StorageInterface):
    def __init__(
        self,
        sctx: miranda.Security_context,
        storage_policy: miranda.Storage_policy,
        api_base_url: Optional[str] = None,
        verify_ssl: bool = True,
    ):
        super().__init__(sctx, storage_policy)
        if api_base_url is not None:
            self.api_base_url = api_base_url
        else:
            if "api_base" in self.details and self.details["api_base"] != "":
                self.api_base_url = self.details["api_base"]
            else:
                self.api_base_url = "https://miranda.localhost/api/vault/v1"

        self.verify_ssl = verify_ssl
        if (
            "access_key_id" not in self.details
            or "secret_access_key" not in self.details
        ):
            raise ValueError(
                "Vault storage policy must have access_key_id and secret_access_key set"
            )

    def _api_url(self, path: str, query: Optional[dict[str, str]] = None) -> str:
        if query is None:
            return f"{self.api_base_url}{path}"
        else:
            return f"{self.api_base_url}{path}?{urllib.parse.urlencode(query)}"

    def _api_token(self) -> str:
        return f"{self.sctx.database_user}.{self.sctx.database_password}"

    def get_vaults(self) -> list[dict[str, str]]:
        resp = requests.get(
            self._api_url("/"), cookies={"miranda_auth": self._api_token()}
        )
        resp.raise_for_status()
        return resp.json()

    def get_file_url(self, identifier: str | int) -> str:
        # TODO: add "public" flag to get public URL without secret_access_key
        return f"{self.api_base_url}/{self.details['access_key_id']}/objects/{identifier}?secret_access_key={self.details['secret_access_key']}"

    def metadata(self, identifier: str | int) -> dict[str, str]:
        resp = requests.get(
            self._api_url(
                f"/{self.details['access_key_id']}/objects/{identifier}/metadata",
                {"secret_access_key": self.details["secret_access_key"]},
            ),
            cookies={"miranda_auth": self._api_token()},
        )
        resp.raise_for_status()
        return resp.json()

    # default stream in 512kb chunks
    def download(
        self,
        identifier: str | int,
        output_filename: Optional[pathlib.Path] = None,
        to_buffer: bool = False,
        overwrite: bool = False,
        stream_chunk_size: int = 1024 * 512,
    ) -> pathlib.Path | ResponseStream:
        # if output is None, return a BytesIO
        if isinstance(identifier, str):
            object_url = self._api_url(
                f"/{self.details['access_key_id']}/objects/0",
                {
                    "secret_access_key": self.details["secret_access_key"],
                    "tag": identifier,
                },
            )
        else:
            object_url = self._api_url(
                f"/{self.details['access_key_id']}/objects/{identifier}",
                {"secret_access_key": self.details["secret_access_key"]},
            )
        cookies = {"miranda_auth": self._api_token()}
        if to_buffer:
            resp = requests.get(
                object_url, cookies=cookies, stream=True, verify=self.verify_ssl
            )
            return ResponseStream(resp.iter_content(chunk_size=stream_chunk_size))
        else:
            resp = requests.get(
                object_url, cookies=cookies, stream=True, verify=self.verify_ssl
            )
            resp.raise_for_status()

            if output_filename is not None:
                output = output_filename
            elif "Content-Disposition" in resp.headers:
                output = re.findall(
                    r'filename="(.+)"', resp.headers["Content-Disposition"]
                )[0]
            else:
                output = identifier

            output = pathlib.Path(self.storage_policy.mount_point).joinpath(output)
            output.parent.mkdir(
                parents=True, exist_ok=True
            )  # create parent directories if they don't exist

            if output.exists() and overwrite is False:
                raise FileExistsError(
                    f"File {output} already exists. Pass overwrite=True to overwrite it."
                )
            with output.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=stream_chunk_size):
                    f.write(chunk)
            return output

    def upload(
        self,
        file: pathlib.Path | BytesIO,
        filename: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> int | str:
        if filename is None:
            filename = file.name
        query = {"secret_access_key": self.details["secret_access_key"]}
        if tag is not None:
            query["tag"] = tag
        object_url = self._api_url(f"/{self.details['access_key_id']}/objects", query)
        cookies = {"miranda_auth": self._api_token()}

        if isinstance(file, BytesIO):
            file.seek(0)
            if filename is None:
                filename = "file"
            stream = file
            mime = "application/octet-stream"
        else:
            stream = file.open("rb")
            mime = mimetypes.guess_type(file)[0]
        # upload with body byte stream
        resp = requests.post(
            object_url,
            cookies=cookies,
            data=stream,
            headers={"Content-Type": mime, "x-filename": filename},
            verify=self.verify_ssl,
        )
        resp.raise_for_status()
        return resp.json()["oid"]
