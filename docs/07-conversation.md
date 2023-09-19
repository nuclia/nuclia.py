# Conversational use case

All examples has assumed you [authenticated](02-auth.md) and defined a [default](03-default.md) knowledgebox. In case you want to overwrite or define a one time knowledgebox you should add on any command/function the `url` and `api_key` parameter.

## Upload messages

You should craft a JSON file with the information of the conversation:

```json
[
  {
    "who": "ORIGIN_UUID",
    "to": ["DESTINATION_UUID"],
    "ident": "UNIQUE_IDENTIFIER",
    "timestamp": "MESSAGE_DATETIME",
    "content": {
      "text": "MESSAGE",
      "format": "MESSAGE_TYPE"
    }
  }
]
```

- `ORIGIN_UUID`: Identification of the user who sent the message
- `DESTINATION_UUID`: Identification of the users who received the message
- `UNIQUE_IDENTIFIER`: Identification of the message, needs to be unique in the conversation
- `MESSAGE_DATETIME`: Message date time in ISO format
- `MESSAGE_TYPE`: Format of the message: `0` for `PLAIN` or `1` for `HTML` or `MARKDOWN` or `RST`

[Example](https://github.com/nuclia/nuclia.py/nuclia/tests/assets/conversation.json)

```bash
nuclia kb upload conversation --path=FILE
```

## Upload files

[Upload documentation](04-upload.md)

## Search on it

[Search documentation](06-search.md)
