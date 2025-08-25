import warnings

from time import sleep
import io
from nucliadb_sdk.v2.exceptions import NotFoundError
import base64
import tempfile
from nuclia.sdk.resource import NucliaResource
from nucliadb_models.file import FileField
from nucliadb_models.common import File


def test_resource(testing_config):
    nresource = NucliaResource()
    try:
        res = nresource.get(slug="res1")
        nresource.delete(rid=res.id)
    except NotFoundError:
        pass

    res_id = nresource.create(slug="res1")

    res = nresource.get(rid=res_id)
    assert res

    res = nresource.get(slug="res1")
    assert res
    assert res.id == res_id

    assert res.title == "res1"

    nresource.update(
        rid=res_id,
        title="My great resource",
        texts={"text1": {"body": "Hello here"}},
    )
    res = nresource.get(slug="res1", show=["basic", "values"])

    assert res
    assert res.title in ["My great resource", "res1"]
    if res.data.texts:
        assert res.data.texts["text1"]
    else:
        warnings.warn("No texts found in resource")

    nresource.delete(rid=res_id)

    try:
        sleep(0.5)
        nresource.get(slug="res1")
        assert False
    except NotFoundError:
        assert True


def test_resource_download(testing_config):
    nresource = NucliaResource()
    slug = "download-file-test"

    # Clean up any existing resource with the same slug
    try:
        res = nresource.get(slug=slug)
    except NotFoundError:
        pass
    else:
        nresource.delete(rid=res.id)

    # Create a resource with a file
    file_binary = io.BytesIO(b"some random data")
    res_id = nresource.create(
        slug=slug,
        files={
            "file": FileField(
                file=File(
                    filename="image.png",
                    content_type="image/png",
                    payload=base64.b64encode(file_binary.getvalue()).decode("utf-8"),
                )
            )
        },
    )

    # Now download the file
    with tempfile.TemporaryDirectory() as tmpdir:
        output = f"{tmpdir}/image.png"
        nresource.download_file(rid=res_id, file_id="file", output=output)
