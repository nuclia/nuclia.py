import time
from functools import partial
from typing import Optional

from nucliadb_models.export_import import (
    CreateExportResponse,
    CreateImportResponse,
    Status,
)
from tqdm import tqdm

from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient

MB = 1024 * 1024
CHUNK_SIZE = 5 * MB


class NucliaExports:
    """
    Manage Knowledge Box exports.

    """

    @kb
    def start(
        self, *args, path: Optional[str] = None, **kwargs
    ) -> Optional[CreateExportResponse]:
        ndb: NucliaDBClient = kwargs["ndb"]
        resp = ndb.ndb.start_export(kbid=ndb.kbid)
        if path is None:
            return resp
        self.download(export_id=resp.export_id, path=path, **kwargs)
        return None

    @kb
    def download(self, *, export_id: str, path: str, **kwargs) -> None:
        ndb: NucliaDBClient = kwargs["ndb"]
        wait_for_finished(ndb, "export", export_id)
        print(f"Export is ready to be downloaded.")
        iterator = ndb.ndb.download_export(kbid=ndb.kbid, export_id=export_id)
        with open(path, "wb") as f:
            with tqdm(
                desc=f"Downloading export {export_id} to {path}",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
            ) as pbar:
                for chunk in iterator(chunk_size=CHUNK_SIZE):
                    pbar.update(len(chunk))
                    f.write(chunk)


class NucliaImports:
    """
    Manage Knowledge Box imports.

    """

    @kb
    def start(
        self, *, path: str, sync: bool = False, **kwargs
    ) -> Optional[CreateImportResponse]:
        ndb: NucliaDBClient = kwargs["ndb"]

        def iterator(path: str):
            with tqdm(
                desc=f"Uploading from {path} to import",
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                miniters=1,
            ) as pbar:
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        pbar.update(len(chunk))
                        yield chunk

        response = ndb.ndb.start_import(kbid=ndb.kbid, content=iterator(path))
        if not sync:
            return response
        else:
            wait_for_finished(ndb, "import", response.import_id)
            print(f"Import finished!")
            return None

    @kb
    def status(self, *, import_id: str, **kwargs) -> Status:
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.import_status(kbid=ndb.kbid, import_id=import_id)


def wait_for_finished(ndb: NucliaDBClient, type: str, id: str):
    if type not in ("export", "import"):
        raise ValueError(f"Unknown type {type}")
    if type == "export":
        get_status = partial(ndb.ndb.export_status, kbid=ndb.kbid, export_id=id)
    else:
        get_status = partial(ndb.ndb.import_status, kbid=ndb.kbid, import_id=id)
    status = get_status().status
    pbar = tqdm(
        unit="it", desc=f"Waiting for {type} {id} to finish", miniters=1, delay=1
    )
    while status != Status.FINISHED:
        assert status != Status.ERRORED, f"{type} failed"
        pbar.update()
        time.sleep(1)
        status = get_status()
