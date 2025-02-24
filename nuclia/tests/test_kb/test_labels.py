from nuclia.sdk.kb import NucliaKB

import pytest


def test_labels(testing_config):
    nkb = NucliaKB()
    nkb.set_labelset(labelset="labelset1")
    nkb.add_label(labelset="labelset1", label="label1")
    nkb.add_labels(labelset="labelset1", labels=["label1", "label2"])
    with pytest.raises(ValueError):
        nkb.add_labels(labelset="whatever", labels=["label1", "label2"])
    nkb.del_labelset(labelset="labelset2")
    labelset = nkb.get_labelset(labelset="labelset1")
    assert len(labelset.labels) == 2

    nkb.del_label(labelset="labelset1", label="label2")

    labelset = nkb.get_labelset(labelset="labelset1")
    assert len(labelset.labels) == 1
    assert labelset.labels[0].title == "label1"

    labelsets = nkb.list_labelsets()
    assert len(labelsets.labelsets) == 1
    assert "labelset1" in labelsets.labelsets
    nkb.del_labelset(labelset="labelset1")
    labelsets = nkb.list_labelsets()
    assert len(labelsets.labelsets) == 0
