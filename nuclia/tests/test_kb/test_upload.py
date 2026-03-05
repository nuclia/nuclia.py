import os
from typing import Type, Union

import pytest
from nucliadb_models.resource import FileFieldData
from nucliadb_sdk.v2.exceptions import NotFoundError

from nuclia.sdk.kb import AsyncNucliaUpload, NucliaUpload
from nuclia.sdk.resource import NucliaResource
from nuclia.tests.utils import maybe_await


@pytest.mark.parametrize(
    "nupload_klass",
    [NucliaUpload, AsyncNucliaUpload],
)
async def test_upload_without_payload(
    testing_config,
    nupload_klass: Union[Type[NucliaUpload], Type[AsyncNucliaUpload]],
):
    nupload = nupload_klass()
    nresource = NucliaResource()
    slug = "upload_without_payload"

    try:
        nresource.delete(slug=slug)
    except NotFoundError:
        pass

    rid = await maybe_await(
        nupload.file(
            path=f"{os.path.dirname(__file__)}/test_upload.py",
            slug=slug,
        )
    )
    res = nresource.get(rid=rid)
    assert res.title == slug


@pytest.mark.parametrize(
    "nupload_klass",
    [NucliaUpload, AsyncNucliaUpload],
)
async def test_upload_with_labels(
    testing_config,
    nupload_klass: Union[Type[NucliaUpload], Type[AsyncNucliaUpload]],
):
    nupload = nupload_klass()
    nresource = NucliaResource()
    slug = "upload_with_labels"

    try:
        nresource.delete(slug=slug)
    except NotFoundError:
        pass

    rid = await maybe_await(
        nupload.file(
            path=f"{os.path.dirname(__file__)}/test_upload.py",
            slug=slug,
            usermetadata={"classifications": [{"labelset": "a", "label": "b"}]},
        )
    )
    res = nresource.get(rid=rid)
    assert res.title == slug
    labels = res.usermetadata.classifications
    assert labels
    assert labels[0].labelset == "a"
    assert labels[0].label == "b"


@pytest.mark.parametrize(
    "nupload_klass",
    [NucliaUpload, AsyncNucliaUpload],
)
async def test_upload_with_language(
    testing_config,
    nupload_klass: Union[Type[NucliaUpload], Type[AsyncNucliaUpload]],
):
    nupload = nupload_klass()
    nresource = NucliaResource()
    slug = "upload_with_language"

    try:
        nresource.delete(slug=slug)
    except NotFoundError:
        pass

    rid = await maybe_await(
        nupload.file(
            path=f"{os.path.dirname(__file__)}/test_upload.py",
            slug=slug,
            language="en",
        )
    )
    res = nresource.get(rid=rid, show=["values"])
    assert res.title == slug
    file: FileFieldData = res.data.files.popitem()[1]
    assert file.value.language == "en"
