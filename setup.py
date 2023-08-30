# -*- coding: utf-8 -*-
import re
from pathlib import Path

from setuptools import find_packages, setup

_dir = Path(__file__).resolve().parent
VERSION = _dir.joinpath("VERSION").open().read().strip()
README = _dir.joinpath("README.md").open().read()


def load_reqs(filename):
    with open(filename) as reqs_file:
        return [
            # pin nucliadb-xxx to the same version as nucliadb
            line.strip() + f"=={VERSION}"
            if line.startswith("nucliadb-") and "=" not in line
            else line.strip()
            for line in reqs_file.readlines()
            if not (
                re.match(r"\s*#", line) or re.match("-e", line) or re.match("-r", line)
            )
        ]


requirements = load_reqs("requirements.txt")

setup(
    name="nuclia",
    version=VERSION,
    long_description=README,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    url="https://nuclia.com",
    author="Nuclia",
    keywords="search, semantic, AI",
    author_email="info@nuclia.com",
    python_requires=">=3.8, <4",
    license="BSD",
    zip_safe=True,
    include_package_data=True,
    package_data={"": ["*.txt", "*.md"], "nucliadb": ["py.typed"]},
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            # Service commands
            # Standalone
            "nuclia = nuclia.cli.run:run",
        ]
    },
    project_urls={
        "Nuclia": "https://nuclia.com",
        "Github": "https://github.com/nuclia/nucliadb",
        "Discord": "https://discord.gg/8EvQwmsbzf",
    },
)
