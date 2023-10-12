from typing import List, Optional
from warnings import warn

from nucliadb_models.configuration import KBConfiguration
from nucliadb_models.labels import KnowledgeBoxLabels, Label, LabelSet, LabelSetKind
from nucliadb_models.resource import Resource, ResourceList

from nuclia.data import get_auth
from nuclia.decorators import kb, pretty
from nuclia.lib.kb import NucliaDBClient
from nuclia.sdk.auth import NucliaAuth
from nuclia.sdk.export_import import NucliaExports, NucliaImports
from nuclia.sdk.logger import logger
from nuclia.sdk.resource import NucliaResource
from nuclia.sdk.search import NucliaSearch
from nuclia.sdk.upload import NucliaUpload


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
    def del_configuration(self, **kwargs) -> None:
        ndb: NucliaDBClient = kwargs["ndb"]
        ndb.ndb.delete_configuration(kbid=ndb.kbid)

    @kb
    def get_configuration(self, **kwargs) -> KBConfiguration:
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.get_configuration(kbid=ndb.kbid)

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
