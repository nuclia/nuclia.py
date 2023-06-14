# Conversational use case

## Upload messages

You should craft a JSON file with the information of the conversation for each conversation:

```json
{
    "conversations": [
        {
            "slug": "CONVERSATIONAL_SLUG", 
            "messages":[
                {
                    "who": "ORIGIN_UUID",
                    "to": ["DESTINATION_UUID"],
                    "uuid": "UNIQUE_IDENTIFIER",
                    "timestamp": "MESSAGE_DATETIME",
                    "message": {
                        "text": "MESSAGE",
                        "format": "MESSAGE_TYPE"

                    }
                }
            ]
        }
    ]
}
```

- `CONVERSATIONAL_SLUG`: Identification of the conversation
- `ORIGIN_UUID`: Identification of the user who sent the message
- `DESTIONTION_UUID`: Identification of the users who received the message
- `UNIQUE_IDENTIFIER`: Identification of the message, needs to be unique
- `MESSAGE_DATETIME`: Message date time in ISO format
- `MESSAGE_TYPE`: Format of the message: `PLAIN` or `HTML` or `MARKDOWN` or `RST`

[Example](https://github.com/nuclia/nuclia.py/nuclia/tests/assets/conversation.js)

```bash
nuclia kb upload conversation --path=FILE
```

## Upload files

[Upload documentation](https://github.com/nuclia/nuclia.py/docs/UPLOAD.md)

## Search on it


