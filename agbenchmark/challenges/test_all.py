import glob
import importlib
import json
import os
import pkgutil
import sys
import types
from pathlib import Path
from typing import Any, Dict

import pytest
from dotenv import load_dotenv

from agbenchmark.challenge import Challenge
from agbenchmark.start_benchmark import CURRENT_DIRECTORY

load_dotenv()

IMPROVE = os.getenv("IMPROVE", "False")


json_files = glob.glob(f"{CURRENT_DIRECTORY}/challenges/**/data.json", recursive=True)


def get_test_path(json_file: str) -> str:
    abs_location = os.path.dirname(os.path.abspath(json_file))

    path = Path(abs_location)

    # Find the index of "agbenchmark" in the path parts
    try:
        agbenchmark_index = path.parts.index("agbenchmark")
    except ValueError:
        raise ValueError("Invalid challenge location.")

    # Create the path from "agbenchmark" onwards
    challenge_location = Path(*path.parts[agbenchmark_index:])

    return str(challenge_location)


def generate_tests() -> None:
    print("Generating tests...")
    # Dynamic class creation
    for json_file in json_files:
        with open(json_file, "r") as f:
            data = json.load(f)

            class_name = data.get("name", "")

        challenge_location = get_test_path(json_file)
        if data["ground"]["type"] == "custom_python":
            custom_python_location = (
                f"{CURRENT_DIRECTORY}/../{challenge_location}/custom_python"
            )
            sys.path.append(str(custom_python_location))

            for (module_loader, name, ispkg) in pkgutil.iter_modules(
                [str(custom_python_location)]
            ):
                module = importlib.import_module(name)

                if hasattr(module, "make_assertion"):
                    make_assertion = getattr(module, "make_assertion")

        # Define test class dynamically
        challenge_class = types.new_class(class_name, (Challenge,))

        setattr(challenge_class, "CHALLENGE_LOCATION", challenge_location)

        # Define test method within the dynamically created class
        def test_method(self, config: Dict[str, Any]) -> None:  # type: ignore
            self.setup_challenge(config)

            scores = self.get_scores(config)

            # Check if make_assertion is defined and use it
            if "make_assertion" in locals():
                try:
                    make_assertion()
                except AssertionError as error:
                    print(error)  # Or handle this in another way
            else:
                assert 1 in scores

        # Parametrize the method here
        test_method = pytest.mark.parametrize(
            "challenge_data",
            [data],
            indirect=True,
        )(test_method)

        setattr(challenge_class, "test_method", test_method)

        # Attach the new class to a module so it can be discovered by pytest
        module = importlib.import_module(__name__)
        setattr(module, class_name, challenge_class)

        print(f"Generated test for {class_name}.")


generate_tests()
