import os
import time
from functools import partial
from typing import Optional

from nucliadb_models.export_import import (
    CreateExportResponse,
    CreateImportResponse,
    Status,
    StatusResponse,
)
from tqdm import tqdm

from nuclia.decorators import kb
from nuclia.lib.kb import NucliaDBClient

MB = 1024 * 1024
CHUNK_SIZE = 5 * MB
STATUS_CHECK_INTERVAL_S = 3


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
        print(f"Export for KB started. export_id={resp.export_id}")
        self.download(export_id=resp.export_id, path=path, **kwargs)
        return None

    @kb
    def download(self, *, export_id: str, path: str, **kwargs) -> None:
        ndb: NucliaDBClient = kwargs["ndb"]
        wait_for_finished(ndb, "export", export_id)
        print(f"Export ready! Will be downloaded to {path}.")
        iterator = ndb.ndb.download_export(kbid=ndb.kbid, export_id=export_id)
        with open(path, "wb") as f:
            with tqdm(
                desc=f"Downloading data",
                unit="iB",
                unit_scale=True,
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
            total_size = os.path.getsize(path)
            with tqdm(
                desc=f"Uploading data",
                total=total_size,
                unit="iB",
                unit_scale=True,
            ) as pbar:
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        pbar.update(len(chunk))
                        yield chunk

        print(f"Importing from {path}")
        response = ndb.ndb.start_import(kbid=ndb.kbid, content=iterator(path))

        if not sync:
            return response
        else:
            import_id = response.import_id
            print(f"Import task started. import_id={import_id}")
            wait_for_finished(ndb, "import", import_id)
            print(f"Import finished!")
            return None

    @kb
    def status(self, *, import_id: str, **kwargs) -> StatusResponse:
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.import_status(kbid=ndb.kbid, import_id=import_id)


def wait_for_finished(ndb: NucliaDBClient, type: str, id: str):
    if type not in ("export", "import"):
        raise ValueError(f"Unknown type {type}")

    if type == "export":
        desc = f"Generating export"
        get_status = partial(ndb.ndb.export_status, kbid=ndb.kbid, export_id=id)
    else:
        desc = f"Importing data"
        get_status = partial(ndb.ndb.import_status, kbid=ndb.kbid, import_id=id)

    resp: StatusResponse = get_status()
    with tqdm(
        desc=desc,
        unit="resources",
        total=0,
    ) as pbar:
        status = resp.status
        processed = 0
        while status != Status.FINISHED:
            assert status != Status.ERRORED, f"{type} failed"

            pbar.total = resp.total
            delta_processed = max(0, resp.processed - processed)
            pbar.update(delta_processed)
            processed = resp.processed

            time.sleep(STATUS_CHECK_INTERVAL_S)

            resp = get_status()
            status = resp.status
