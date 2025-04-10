import asyncio
from datetime import datetime
from deprecated import deprecated
import os
import tempfile
import time
from typing import Any, List, Optional, Union

from nucliadb_models import Notification
from nucliadb_models.labels import KnowledgeBoxLabels, Label, LabelSet, LabelSetKind
from nucliadb_models.resource import ResourceList
from nucliadb_models.search import SummarizeRequest, SummaryKind
from nucliadb_sdk import exceptions

from nuclia.data import get_async_auth, get_async_client, get_auth, get_client
from nuclia.decorators import kb
from nuclia.lib.kb import AsyncNucliaDBClient, NucliaDBClient
from nuclia.lib.models import GraphRelation, get_relation
from nuclia.lib.nua_responses import SummarizedModel
from nuclia.sdk.logger import logger
from nuclia.sdk.auth import AsyncNucliaAuth, NucliaAuth
from nuclia.sdk.export_import import (
    AsyncNucliaExports,
    AsyncNucliaImports,
    NucliaExports,
    NucliaImports,
)
from nuclia.sdk.logs import NucliaLogs, AsyncNucliaLogs
from nuclia.sdk.remi import NucliaRemi, AsyncNucliaRemi
from nuclia.sdk.resource import AsyncNucliaResource, NucliaResource
from nuclia.sdk.search import AsyncNucliaSearch, NucliaSearch
from nuclia.sdk.task import NucliaTask, AsyncNucliaTask
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
        self.task = NucliaTask()
        self.remi = NucliaRemi()

    @kb
    def list(
        self, page: Optional[int] = None, size: Optional[int] = None, **kwargs
    ) -> ResourceList:
        ndb: NucliaDBClient = kwargs["ndb"]
        query_params = {}
        if page:
            query_params["page"] = f"{page}"
        if size:
            query_params["size"] = f"{size}"
        data: ResourceList = ndb.ndb.list_resources(
            kbid=ndb.kbid, query_params=query_params
        )
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
    @deprecated(version="5.0.0", reason="You should use set_labelset")
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
        self.set_labelset(
            labelset=labelset,
            kind=kind,
            multiple=multiple,
            title=title,
            color=color,
            labels=labels,
            **kwargs,
        )

    @kb
    def set_labelset(
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
        labelset_kind: Optional[LabelSetKind] = None,
        **kwargs,
    ):
        self.add_labels(
            labelset=labelset,
            labels=[label],
            labelset_kind=labelset_kind,
            **kwargs,
        )

    @kb
    def add_labels(
        self,
        *,
        labelset: str,
        labels: List[str],
        labelset_kind: Optional[LabelSetKind] = None,
        **kwargs,
    ):
        ndb: NucliaDBClient = kwargs["ndb"]
        existing = False
        try:
            labelset_obj: LabelSet = ndb.ndb.get_labelset(
                kbid=ndb.kbid, labelset=labelset
            )
            existing = True
        except exceptions.NotFoundError:
            pass
        if not existing:
            if labelset_kind is None:
                raise ValueError("Labelset kind must be defined for a new labelset")
            else:
                labelset_obj = LabelSet(
                    title=labelset,
                    color="blue",
                    labels=[],
                    kind=[labelset_kind],
                    multiple=True,
                )
        existing_labels = [x.title for x in labelset_obj.labels]
        for label in labels:
            if label in existing_labels:
                continue
            label_obj = Label(title=label)
            labelset_obj.labels.append(label_obj)
        ndb.ndb.set_labelset(
            kbid=ndb.kbid,
            labelset=labelset,
            content=labelset_obj,
        )

    @kb
    def del_label(self, *, labelset: str, label: str, **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]
        labelset_obj: LabelSet = ndb.ndb.get_labelset(kbid=ndb.kbid, labelset=labelset)
        label_to_delete = next(x for x in labelset_obj.labels if x.title == label)
        labelset_obj.labels.remove(label_to_delete)
        ndb.ndb.set_labelset(kbid=ndb.kbid, labelset=labelset, content=labelset_obj)

    @kb
    def get_graph(
        self,
        uid: Optional[str] = None,
        slug: Optional[str] = None,
        **kwargs,
    ):
        res = self.resource.get(
            ndb=kwargs["ndb"], rid=uid, slug=slug, show=["basic", "relations"]
        )
        return res.usermetadata.relations

    @kb
    def add_graph(
        self,
        graph: List[Union[GraphRelation, dict]],
        slug: Optional[str] = None,
        **kwargs,
    ):
        kw = {
            "ndb": kwargs["ndb"],
            "usermetadata": {
                "relations": [
                    get_relation(relation).to_relation() for relation in graph
                ]
            },
        }
        if slug:
            kw["slug"] = slug
        self.resource.create(**kw)

    @kb
    def update_graph(
        self,
        graph: List[Union[GraphRelation, dict]],
        uid: Optional[str] = None,
        slug: Optional[str] = None,
        override: Optional[bool] = False,
        **kwargs,
    ):
        new_relations = [get_relation(relation).to_relation() for relation in graph]
        if not override:
            relations = self.get_graph(uid=uid, slug=slug, **kwargs)
            relations.extend(new_relations)
        else:
            relations = new_relations
        self.resource.update(
            ndb=kwargs["ndb"], rid=uid, slug=slug, usermetadata={"relations": relations}
        )

    @kb
    def delete_graph(
        self,
        uid: Optional[str] = None,
        slug: Optional[str] = None,
        **kwargs,
    ):
        self.resource.delete(ndb=kwargs["ndb"], rid=uid, slug=slug)

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
    def get_configuration(
        self,
        **kwargs,
    ) -> Any:
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.get_configuration(
            kbid=ndb.kbid,
        )

    @kb
    def summarize(self, *, resources: List[str], **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]
        return ndb.ndb.summarize(kbid=ndb.kbid, resources=resources)

    @kb
    def notifications(self, **kwargs):
        ndb: NucliaDBClient = kwargs["ndb"]
        response = ndb.notifications()
        for notification in response.iter_lines():
            yield Notification.model_validate_json(notification)

    @kb
    def copy(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        destination: str,
        override: Optional[bool] = False,
        **kwargs,
    ):
        ndb = kwargs["ndb"]
        if rid:
            res = ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid,
                rid=rid,
                query_params={
                    "show": ["basic", "origin", "extra", "values", "security"]
                },
            )
        elif slug:
            res = ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid,
                slug=slug,
                query_params={
                    "show": ["basic", "origin", "extra", "values", "security"]
                },
            )
        else:
            raise ValueError("Either rid or slug must be provided")
        data = {
            "kbid": destination,
            "slug": res.slug,
            "title": res.title,
            "summary": res.summary,
            "icon": res.icon,
            "origin": res.origin,
            "extra": res.extra,
            "usermetadata": res.usermetadata,
            "fieldmetadata": res.fieldmetadata,
            "security": res.security,
        }
        files_to_upload = []
        if res.data.conversations:
            data["conversations"] = dict(
                zip(
                    res.data.conversations.keys(),
                    [dict(v.value) for v in res.data.conversations.values()],
                )
            )
        if res.data.links:
            data["links"] = dict(
                zip(
                    res.data.links.keys(),
                    [dict(v.value) for v in res.data.links.values()],
                )
            )
        if res.data.texts:
            data["texts"] = dict(
                zip(
                    res.data.texts.keys(),
                    [dict(v.value) for v in res.data.texts.values()],
                )
            )
        if res.data.files:
            remote_files = {}
            for file_id, file in res.data.files.items():
                if file.value.external:
                    remote_files[file_id] = file.value
                else:
                    files_to_upload.append({"id": file_id, "data": file.value})
        destination_kb = get_client(destination)
        if override:
            try:
                self.resource.delete(
                    ndb=destination_kb,
                    slug=res.slug,
                )
            except exceptions.NotFoundError:
                pass
        failed = False
        try:
            uuid = self.resource.create(ndb=destination_kb, **data)
        except exceptions.RateLimitError as e:
            failed = True
            delay = 5
            if e.try_after:
                delay = round(e.try_after - datetime.utcnow().timestamp())
            logger.warning(
                f"Backpressure error while copying resource, retrying in {delay} seconds"
            )
            time.sleep(delay)
            self.copy(
                rid=rid, slug=slug, destination=destination, override=override, **kwargs
            )

        if not failed:
            with tempfile.TemporaryDirectory() as tmpdirname:
                for file_data in files_to_upload:
                    file_path = os.path.join(
                        tmpdirname, file_data["data"].file.filename
                    )
                    self.resource.download_file(
                        rid=res.id, file_id=file_data["id"], output=file_path, **kwargs
                    )
                    self.upload.file(path=file_path, ndb=destination_kb, rid=uuid)

    @kb
    def copy_all(
        self,
        *,
        destination: str,
        page=0,
        override: Optional[bool] = False,
        filters: Optional[List[str]] = None,
        **kwargs,
    ):
        ndb = kwargs["ndb"]
        if filters is None:
            batch = self.list(ndb=ndb, page=page)
            resources = batch.resources
            is_last = batch.pagination.last
        else:
            batch = self.search.find(
                ndb=ndb, filters=filters, page=page, fields=["a/title"]
            )
            resources = batch.resources.values()
            is_last = batch.next_page
        for res in resources:
            try:
                logger.info(f"Copying resource {res.id}")
                self.copy(
                    rid=res.id, destination=destination, override=override, **kwargs
                )
            except exceptions.ConflictError:
                logger.info(f"Resource {res.id} already exists in destination KB")
        if not is_last:
            self.copy_all(
                destination=destination, page=page + 1, override=override, **kwargs
            )


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
        self.logs = AsyncNucliaLogs()
        self.task = AsyncNucliaTask()
        self.remi = AsyncNucliaRemi()

    @kb
    async def list(self, **kwargs) -> ResourceList:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        del kwargs["ndb"]
        data: ResourceList = await ndb.ndb.list_resources(
            kbid=ndb.kbid, query_params=kwargs
        )
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
    @deprecated(version="5.0.0", reason="You should use set_labelset")
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
        await self.set_labelset(
            labelset=labelset,
            kind=kind,
            multiple=multiple,
            title=title,
            color=color,
            labels=labels,
            **kwargs,
        )

    @kb
    async def set_labelset(
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
        labelset_kind: Optional[LabelSetKind] = None,
        **kwargs,
    ):
        await self.add_labels(
            labelset=labelset,
            labels=[label],
            labelset_kind=labelset_kind,
            **kwargs,
        )

    @kb
    async def add_labels(
        self,
        *,
        labelset: str,
        labels: List[str],
        labelset_kind: Optional[LabelSetKind] = None,
        **kwargs,
    ):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        existing = False
        try:
            labelset_obj: LabelSet = await ndb.ndb.get_labelset(
                kbid=ndb.kbid, labelset=labelset
            )
            existing = True
        except exceptions.NotFoundError:
            pass
        if not existing:
            if labelset_kind is None:
                raise ValueError("Labelset kind must be defined for a new labelset")
            else:
                labelset_obj = LabelSet(
                    title=labelset,
                    color="blue",
                    labels=[],
                    kind=[labelset_kind],
                    multiple=True,
                )
        existing_labels = [x.title for x in labelset_obj.labels]
        for label in labels:
            if label in existing_labels:
                continue
            label_obj = Label(title=label)
            labelset_obj.labels.append(label_obj)
        await ndb.ndb.set_labelset(
            kbid=ndb.kbid,
            labelset=labelset,
            content=labelset_obj,
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
    async def get_graph(
        self,
        uid: Optional[str] = None,
        slug: Optional[str] = None,
        **kwargs,
    ):
        res = await self.resource.get(
            ndb=kwargs["ndb"], rid=uid, slug=slug, show=["basic", "relations"]
        )
        return res.usermetadata.relations

    @kb
    async def add_graph(
        self,
        graph: List[Union[GraphRelation, dict]],
        slug: Optional[str] = None,
        **kwargs,
    ):
        kw = {
            "ndb": kwargs["ndb"],
            "usermetadata": {
                "relations": [
                    get_relation(relation).to_relation() for relation in graph
                ]
            },
        }
        if slug:
            kw["slug"] = slug
        await self.resource.create(**kw)

    @kb
    async def update_graph(
        self,
        graph: List[Union[GraphRelation, dict]],
        uid: Optional[str] = None,
        slug: Optional[str] = None,
        override: Optional[bool] = False,
        **kwargs,
    ):
        new_relations = [get_relation(relation).to_relation() for relation in graph]
        if not override:
            relations = await self.get_graph(uid=uid, slug=slug, **kwargs)
            relations.extend(new_relations)
        else:
            relations = new_relations
        await self.resource.update(
            ndb=kwargs["ndb"], rid=uid, slug=slug, usermetadata={"relations": relations}
        )

    @kb
    async def delete_graph(
        self,
        uid: Optional[str] = None,
        slug: Optional[str] = None,
        **kwargs,
    ):
        await self.resource.delete(ndb=kwargs["ndb"], rid=uid, slug=slug)

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
    async def get_configuration(
        self,
        **kwargs,
    ) -> Any:
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        return await ndb.ndb.get_configuration(
            kbid=ndb.kbid,
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
        return SummarizedModel.model_validate(resp.json())

    @kb
    async def notifications(self, **kwargs):
        ndb: AsyncNucliaDBClient = kwargs["ndb"]
        response = await ndb.notifications()
        async for notification in response.aiter_lines():
            yield Notification.model_validate_json(notification)

    @kb
    async def copy(
        self,
        *,
        rid: Optional[str] = None,
        slug: Optional[str] = None,
        destination: str,
        **kwargs,
    ):
        ndb = kwargs["ndb"]
        if rid:
            res = await ndb.ndb.get_resource_by_id(
                kbid=ndb.kbid,
                rid=rid,
                query_params={
                    "show": ["basic", "origin", "extra", "values", "security"]
                },
            )
        elif slug:
            res = await ndb.ndb.get_resource_by_slug(
                kbid=ndb.kbid,
                slug=slug,
                query_params={
                    "show": ["basic", "origin", "extra", "values", "security"]
                },
            )
        else:
            raise ValueError("Either rid or slug must be provided")
        data = {
            "kbid": destination,
            "slug": res.slug,
            "title": res.title,
            "summary": res.summary,
            "icon": res.icon,
            "origin": res.origin,
            "extra": res.extra,
            "usermetadata": res.usermetadata,
            "fieldmetadata": res.fieldmetadata,
            "security": res.security,
        }
        files_to_upload = []
        if res.data.conversations:
            data["conversations"] = dict(
                zip(
                    res.data.conversations.keys(),
                    [dict(v.value) for v in res.data.conversations.values()],
                )
            )
        if res.data.links:
            data["links"] = dict(
                zip(
                    res.data.links.keys(),
                    [dict(v.value) for v in res.data.links.values()],
                )
            )
        if res.data.texts:
            data["texts"] = dict(
                zip(
                    res.data.texts.keys(),
                    [dict(v.value) for v in res.data.texts.values()],
                )
            )
        if res.data.files:
            remote_files = {}
            for file_id, file in res.data.files.items():
                if file.value.external:
                    remote_files[file_id] = file.value
                else:
                    files_to_upload.append({"id": file_id, "data": file.value})
        destination_kb = await get_async_client(destination)
        failed = False
        try:
            uuid = await self.resource.create(ndb=destination_kb, **data)
        except exceptions.RateLimitError as e:
            failed = True
            delay = 5
            if e.try_after:
                delay = round(e.try_after - datetime.utcnow().timestamp())
            logger.warning(
                f"Backpressure error while copying resource, retrying in {delay} seconds"
            )
            await asyncio.sleep(delay)
            await self.copy(rid=rid, slug=slug, destination=destination, **kwargs)

        if not failed:
            with tempfile.TemporaryDirectory() as tmpdirname:
                for file_data in files_to_upload:
                    file_path = os.path.join(
                        tmpdirname, file_data["data"].file.filename
                    )
                    await self.resource.download_file(
                        rid=res.id, file_id=file_data["id"], output=file_path, **kwargs
                    )
                    await self.upload.file(path=file_path, ndb=destination_kb, rid=uuid)

    @kb
    async def copy_all(
        self, *, destination: str, page=0, filters: Optional[List[str]] = None, **kwargs
    ):
        ndb = kwargs["ndb"]
        if filters is None:
            batch = await self.list(ndb=ndb, page=page)
            resources = batch.resources
            is_last = batch.pagination.last
        else:
            batch = await self.search.find(
                ndb=ndb, filters=filters, page=page, fields=["a/title"]
            )
            resources = batch.resources.values()
            is_last = batch.next_page
        for res in resources:
            try:
                logger.info(f"Copying resource {res.id}")
                await self.copy(rid=res.id, destination=destination, **kwargs)
            except exceptions.ConflictError:
                logger.info(f"Resource {res.id} already exists in destination KB")
        if not is_last:
            await self.copy_all(destination=destination, page=page + 1, **kwargs)
