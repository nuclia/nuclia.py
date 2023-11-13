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
CHUNK_SIZE = 10 * MB
STATUS_CHECK_INTERVAL_S = 3


class NucliaExports:
    """
    Manage Knowledge Box exports.

    To start an export and save it locally, run:

    nuclia kb exports start --path=$HOME/path/to/export
    """

    @kb
    def start(
        self, *args, path: Optional[str] = None, **kwargs
    ) -> Optional[CreateExportResponse]:
        """
        Start an export.

        :param path: if specified, the export contents will be downloaded there.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        resp = ndb.ndb.start_export(kbid=ndb.kbid)
        if path is None:
            return resp
        print(f"Export for KB started. export_id={resp.export_id}")
        self.download(export_id=resp.export_id, path=path, **kwargs)
        return None

    @kb
    def download(self, *, export_id: str, path: str, **kwargs) -> None:
        """
        Download an already generated export.

        :param export_id: id of the export to download
        :param path: file where the export data will be saved
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        wait_for_task_to_finish(ndb, "export", export_id)
        print(f"Export is ready. Will be downloaded to {path}.")
        export_size = ndb.ndb.export_status(kbid=ndb.kbid, export_id=export_id).total
        iterator = ndb.ndb.download_export(kbid=ndb.kbid, export_id=export_id)
        with open(path, "wb") as f:
            with tqdm(
                desc=f"Downloading data",
                total=export_size,
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
        """
        Start an import.

        :param path: path to the file with the export data.
        :param sync: waits for the server import task to finish.
        """
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
            print(f"Import task started.")
            return response
        else:
            import_id = response.import_id
            print(f"Import task started. import_id={import_id}")
            wait_for_task_to_finish(ndb, "import", import_id)
            print(f"Import finished!")
            return None

    @kb
    def status(self, *, import_id: str, **kwargs) -> StatusResponse:
        """
        Check the status of an import.

        :param import_id: id of the import task.
        """
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.import_status(kbid=ndb.kbid, import_id=import_id)


def wait_for_task_to_finish(ndb: NucliaDBClient, task_type: str, id: str):
    if task_type not in ("export", "import"):
        raise ValueError(f"Unknown task_type {task_type}")

    if task_type == "export":
        desc = "Generating export. Status: {status}"
        get_status = partial(ndb.ndb.export_status, kbid=ndb.kbid, export_id=id)
        unit = "resources"
        unit_scale = False

    else:
        desc = "Importing data. Status: {status}"
        get_status = partial(ndb.ndb.import_status, kbid=ndb.kbid, import_id=id)
        unit = "iB"
        unit_scale = True

    resp: StatusResponse = get_status()
    with tqdm(
        desc=desc.format(status=resp.status),
        unit=unit,
        total=resp.total,
        unit_scale=unit_scale,
    ) as pbar:
        status = resp.status
        processed = 0
        while status != Status.FINISHED:
            assert status != Status.ERRORED, f"{task_type} failed"

            # Update progress bar
            pbar.total = resp.total
            pbar.desc = desc.format(status=resp.status)
            delta_processed = max(0, resp.processed - processed)
            pbar.update(delta_processed)
            processed = resp.processed

            time.sleep(STATUS_CHECK_INTERVAL_S)

            resp = get_status()
            status = resp.status
