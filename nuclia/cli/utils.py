def yes_no(question: str) -> bool:
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
