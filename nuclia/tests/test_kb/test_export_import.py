import tempfile
import time

from nuclia.sdk.export_import import NucliaExports, NucliaImports


def test_sync(testing_config):
    exports = NucliaExports()
    imports = NucliaImports()

    with tempfile.TemporaryDirectory() as tempdir:
        path = f"{tempdir}/kb.export"
        exports.start(path=path)
        imports.start(path=path, sync=True)


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
