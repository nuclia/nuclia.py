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

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'