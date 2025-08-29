import base64
import io
import tempfile
import warnings
from time import sleep

import httpx
import pytest
from nucliadb_models.common import File
from nucliadb_models.file import FileField
from nucliadb_sdk.v2.exceptions import NotFoundError

from nuclia.sdk.resource import NucliaResource


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


def test_resource_get_public_url(testing_config):
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
    content = b"some random data"
    file_binary = io.BytesIO(content)
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

    url = nresource.temporal_download_url(rid=res_id, file_id="file", ttl=60)
    assert "eph-token=" in url
    downloaded = httpx.get(url)
    assert downloaded.status_code == 200
    assert downloaded.content == content


@pytest.mark.asyncio
async def test_resource_get_public_url_async(testing_config):
    from nuclia.sdk.resource import AsyncNucliaResource

    nresource = AsyncNucliaResource()
    slug = "download-file-test-async"

    # Clean up any existing resource with the same slug
    try:
        res = await nresource.get(slug=slug)
    except NotFoundError:
        pass
    else:
        await nresource.delete(rid=res.id)

    # Create a resource with a file
    content = b"some random data"
    file_binary = io.BytesIO(content)
    res_id = await nresource.create(
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

    url = await nresource.temporal_download_url(rid=res_id, file_id="file", ttl=60)
    assert "eph-token=" in url
    async with httpx.AsyncClient() as client:
        downloaded = await client.get(url)
    assert downloaded.status_code == 200
    assert downloaded.content == content
