import tempfile
import time

import pytest

from nuclia.sdk.export_import import NucliaExports, NucliaImports


@pytest.mark.skip(reason="To avoid duplicating data in the test KB")
def test_sync(testing_config):
    exports = NucliaExports()
    imports = NucliaImports()

    with tempfile.TemporaryDirectory() as tempdir:
        path = f"{tempdir}/kb.export"
        exports.start(path=path)
        imports.start(path=path, sync=True)


@pytest.mark.skip(reason="To avoid duplicating data in the test KB")
def test_manual(testing_config):
    exports = NucliaExports()
    imports = NucliaImports()
    with tempfile.TemporaryDirectory() as tempdir:
        path = f"{tempdir}/kb.export"
        resp = exports.start(path=path)
        exports.download(resp.export_id, path=path)
        imports.start(path=path)
        while True:
            status = imports.status(resp.import_id).status
            if status == "finished":
                break
            assert status != "failed"
            time.sleep(5)
