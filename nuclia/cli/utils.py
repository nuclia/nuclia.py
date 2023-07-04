import logging
import os


def yes_no(question: str) -> bool:
    if os.environ.get("TESTING") == "True":
        return True
    yes_choices = ["yes", "y"]
    no_choices = ["no", "n"]
    value = None

    while True:
        user_input = input(f"{question} (yes/no): ")
        if user_input.lower() in yes_choices:
            value = True
            break
        elif user_input.lower() in no_choices:
            value = False
            break
        else:
            print("Type yes or no")
            continue
    return value


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_template = "%(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_template + reset,
        logging.INFO: grey + format_template + reset,
        logging.WARNING: yellow + format_template + reset,
        logging.ERROR: red + format_template + reset,
        logging.CRITICAL: bold_red + format_template + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
