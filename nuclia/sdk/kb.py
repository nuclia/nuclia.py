from typing import List, Optional
from warnings import warn

from nucliadb_models.labels import KnowledgeBoxLabels, Label, LabelSet, LabelSetKind
from nucliadb_models.resource import Resource, ResourceList
from nucliadb_models.search import SummarizeRequest, SummaryKind

from nuclia.data import get_async_auth, get_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.lib.nua_responses import SummarizedModel
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth
from nuclia.sdk.export_import import (
    AsyncNucliaExports,
    AsyncNucliaImports,
    NucliaExports,
    NucliaImports,
)
from nuclia.sdk.logger import logger
from nuclia.sdk.logs import NucliaLogs
from nuclia.sdk.resource import AsyncNucliaResource, NucliaResource
from nuclia.sdk.search import AsyncNucliaSearch, NucliaSearch
from nuclia.sdk.upload import AsyncNucliaUpload, NucliaUpload


class NucliaKB:
    @property
    def _auth(self) -> NucliaAuth:
        auth = get_auth()
        return auth

    def __init__(self):
        self.upload = NucliaUpload()
        self.search = NucliaSearch()
        self.resource = NucliaResource()
        self.exports = NucliaExports()
        self.imports = NucliaImports()
        self.logs = NucliaLogs()

    @kb
    def list(self, *, interactive: bool = True, **kwargs) -> Optional[ResourceList]:
        ndb: NucliaDBClient = kwargs["ndb"]
        data: ResourceList = ndb.ndb.list_resources(kbid=ndb.kbid)
        if interactive:
            for resource in data.resources:
                status = (
                    resource.metadata.status if resource.metadata is not None else ""
                )
                print(f"{resource.id} {resource.icon:30} {resource.title} - {status}")
            return None
        else:
            return data

    @kb
    def get_labelset(
        self,
        *,
        labelset: str,
        **kwargs,
    ) -> LabelSet:
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.get_labelset(kbid=ndb.kbid, labelset=labelset)

    @kb
    def add_labelset(
        self,
        *,
        labelset: str,
        kind: LabelSetKind = LabelSetKind.RESOURCES,
        multiple: bool = True,
        title: Optional[str] = None,
        color: Optional[str] = None,
        labels: Optional[List[str]] = None,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        if labels is None:
            labels_list = []
        else:
            labels_list = [Label(title=label) for label in labels]

        labelset_obj = LabelSet(
            title=title if title is not None else labelset,
            color=color if color is not None else "blue",
            labels=labels_list,
            kind=[kind],
            multiple=multiple,
        )

        ndb.ndb.set_labelset(kbid=ndb.kbid, labelset=labelset, content=labelset_obj)

    @kb
    def list_labelsets(self, **kwargs) -> KnowledgeBoxLabels:
        ndb: NucliaDBClient = kwargs["ndb"]
        data: KnowledgeBoxLabels = ndb.ndb.get_labelsets(kbid=ndb.kbid)
        return data

    @kb
    def del_labelset(self, *, labelset: str, **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.ndb.delete_labelset(kbid=ndb.kbid, labelset=labelset)

    @kb
    def add_label(
        self,
        *,
        labelset: str,
        label: str,
        text: Optional[str] = None,
        uri: Optional[str] = None,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        labelset_obj: LabelSet = ndb.ndb.get_labelset(kbid=ndb.kbid, labelset=labelset)
        label_obj = Label(title=label, text=text, uri=uri)
        labelset_obj.labels.append(label_obj)
        ndb.ndb.set_labelset(kbid=ndb.kbid, labelset=labelset, content=labelset_obj)

    @kb
    def del_label(self, *, labelset: str, label: str, **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]
        labelset_obj: LabelSet = ndb.ndb.get_labelset(kbid=ndb.kbid, labelset=labelset)
        label_to_delete = next(x for x in labelset_obj.labels if x.title == label)
        labelset_obj.labels.remove(label_to_delete)
        ndb.ndb.set_labelset(kbid=ndb.kbid, labelset=labelset, content=labelset_obj)

    @kb
    def set_configuration(
        self,
        *,
        semantic_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        ner_model: Optional[str] = None,
        anonymization_model: Optional[str] = None,
        visual_labeling: Optional[str] = None,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.ndb.set_configuration(
            kbid=ndb.kbid,
            semantic_model=semantic_model,
            generative_model=generative_model,
            ner_model=ner_model,
            anonymization_model=anonymization_model,
            visual_labeling=visual_labeling,
        )

    @kb
    @pretty
    def get_resource_by_id(self, *, rid: str, **kwargs) -> Resource:
        warn(
            "get_resource_by_id is deprecated, use resource.get instead",
            DeprecationWarning,
        )
        logger.warning("get_resource_by_slug is deprecated, use resource.get instead")
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.get_resource_by_id(
            kbid=ndb.kbid, rid=rid, query_params={"show": "values"}
        )

    @kb
    @pretty
    def get_resource_by_slug(self, *, slug: str, **kwargs) -> Resource:
        warn(
            "get_resource_by_slug is deprecated, use resource.get instead",
            DeprecationWarning,
        )
        logger.warning("get_resource_by_slug is deprecated, use resource.get instead")
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.get_resource_by_slug(
            kbid=ndb.kbid, slug=slug, query_params={"show": "values"}
        )

    @kb
    def delete(self, *, rid: str, **kwargs):
        warn("delete is deprecated, use resource.delete instead", DeprecationWarning)
        logger.warning("delete is deprecated, use resource.delete instead")
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.ndb.delete_resource(kbid=ndb.kbid, rid=rid)

    @kb
    def summarize(self, *, resources: List[str], **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.summarize(kbid=ndb.kbid, resources=resources)


class AsyncNucliaKB:
    @property
    def _auth(self) -> AsyncNucliaAuth:
        auth = get_async_auth()
        return auth

    def __init__(self):
        self.upload = AsyncNucliaUpload()
        self.search = AsyncNucliaSearch()
        self.resource = AsyncNucliaResource()
        self.exports = AsyncNucliaExports()
        self.imports = AsyncNucliaImports()

    @kb
    async def list(
        self, *, interactive: bool = True, **kwargs
    ) -> Optional[ResourceList]:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        del kwargs["ndb"]
        data: ResourceList = await ndb.ndb.list_resources(
            kbid=ndb.kbid, query_params=kwargs
        )
        if interactive:
            for resource in data.resources:
                status = (
                    resource.metadata.status if resource.metadata is not None else ""
                )
                print(f"{resource.id} {resource.icon:30} {resource.title} - {status}")
            return None
        else:
            return data

    @kb
    async def get_labelset(
        self,
        *,
        labelset: str,
        **kwargs,
    ) -> LabelSet:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        return await ndb.ndb.get_labelset(kbid=ndb.kbid, labelset=labelset)

    @kb
    async def add_labelset(
        self,
        *,
        labelset: str,
        kind: LabelSetKind = LabelSetKind.RESOURCES,
        multiple: bool = True,
        title: Optional[str] = None,
        color: Optional[str] = None,
        labels: Optional[List[str]] = None,
        **kwargs,
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        if labels is None:
            labels_list = []
        else:
            labels_list = [Label(title=label) for label in labels]

        labelset_obj = LabelSet(
            title=title if title is not None else labelset,
            color=color if color is not None else "blue",
            labels=labels_list,
            kind=[kind],
            multiple=multiple,
        )

        await ndb.ndb.set_labelset(
            kbid=ndb.kbid, labelset=labelset, content=labelset_obj
        )

    @kb
    async def list_labelsets(self, **kwargs) -> KnowledgeBoxLabels:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        data: KnowledgeBoxLabels = await ndb.ndb.get_labelsets(kbid=ndb.kbid)
        return data

    @kb
    async def del_labelset(self, *, labelset: str, **kwargs):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        await ndb.ndb.delete_labelset(kbid=ndb.kbid, labelset=labelset)

    @kb
    async def add_label(
        self,
        *,
        labelset: str,
        label: str,
        text: Optional[str] = None,
        uri: Optional[str] = None,
        **kwargs,
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        labelset_obj: LabelSet = await ndb.ndb.get_labelset(
            kbid=ndb.kbid, labelset=labelset
        )
        label_obj = Label(title=label, text=text, uri=uri)
        labelset_obj.labels.append(label_obj)
        await ndb.ndb.set_labelset(
            kbid=ndb.kbid, labelset=labelset, content=labelset_obj
        )

    @kb
    async def del_label(self, *, labelset: str, label: str, **kwargs):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        labelset_obj: LabelSet = await ndb.ndb.get_labelset(
            kbid=ndb.kbid, labelset=labelset
        )
        label_to_delete = next(x for x in labelset_obj.labels if x.title == label)
        labelset_obj.labels.remove(label_to_delete)
        await ndb.ndb.set_labelset(
            kbid=ndb.kbid, labelset=labelset, content=labelset_obj
        )

    @kb
    async def set_configuration(
        self,
        *,
        semantic_model: Optional[str] = None,
        generative_model: Optional[str] = None,
        ner_model: Optional[str] = None,
        anonymization_model: Optional[str] = None,
        visual_labeling: Optional[str] = None,
        **kwargs,
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        await ndb.ndb.set_configuration(
            kbid=ndb.kbid,
            semantic_model=semantic_model,
            generative_model=generative_model,
            ner_model=ner_model,
            anonymization_model=anonymization_model,
            visual_labeling=visual_labeling,
        )

    @kb
    async def summarize(
        self,
        *,
        resources: List[str],
        generative_model: Optional[str] = None,
        summary_kind: Optional[str] = None,
        timeout: int = 1000,
        **kwargs,
    ) -> SummarizedModel:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        resp = await ndb.summarize(
            SummarizeRequest(
                resources=resources,
                generative_model=generative_model,
                summary_kind=SummaryKind(summary_kind),
            ),
            timeout=timeout,
        )
        return SummarizedModel.parse_obj(resp.json())
