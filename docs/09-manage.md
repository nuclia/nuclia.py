# Manage Knowledge Box configuration & labels

## Knowledge Box configuration

You can get the current configuration of a Knowledge Box:

```sh
nuclia kb get_configuration

> semantic_model='multilingual-2023-02-21' generative_model='chatgpt-azure' ner_model='multilingual' anonymization_model='disabled' visual_labeling='disabled'
```

You can change the configuration of a Knowledge Box:

```sh
nuclia kb set_configuration --semantic_model=multilingual-2023-02-21 --generative_model=chatgpt-azure --ner_model=multilingual --anonymization_model=disabled --visual_labeling=disabled
```

## Manage labels

You can list all the labels in a Knowledge Box:

- CLI:

  ```sh
  nuclia kb list_labelsets
  ```

- SDK:

  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  labelsets = kb.list_labelsets()
  ```

You can create a labelset in a Knowledge Box:

- CLI:

  ```sh
  nuclia kb add_labelset --labelset="heroes" --labels="['Batman','Catwoman']"
  ```

- SDK:

  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  kb.add_labelset(labelset="heroes", labels=["Batman", "Catwoman"])
  ```

You can get a labelset in a Knowledge Box:

- CLI:

  ```sh
  nuclia kb get_labelset --labelset="heroes"
  ```

- SDK:

  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  labelset = kb.get_labelset(labelset="heroes")
  ```

You can delete a labelset in a Knowledge Box:

- CLI:

  ```sh
  nuclia kb delete_labelset --labelset="heroes"
  ```

- SDK:

  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  kb.delete_labelset(labelset="heroes")
  ```

You can add a new label to a labelset:

- CLI:

  ```sh
  nuclia kb add_label --labelset="heroes" --label="Supergirl"
  ```

- SDK:

  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  kb.add_label(labelset="heroes", label="Supergirl")
  ```

You can delete a label from a labelset:

- CLI:

  ```sh
  nuclia kb del_label --labelset="heroes" --label="Supergirl"
  ```

- SDK:

  ```python
  from nuclia import sdk
  kb = sdk.NucliaKB()
  kb.del_label(labelset="heroes", label="Supergirl")
  ```
