import logging
import sys

import fire  # type: ignore
from nucliadb_sdk import exceptions

from nuclia.data import get_auth
from nuclia.exceptions import NeedUserToken, UserTokenExpired
from nuclia.sdk.accounts import NucliaAccounts
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.kbs import NucliaKBS
from nuclia.sdk.logger import logger
from nuclia.sdk.nua import NucliaNUA
from nuclia.sdk.nuas import NucliaNUAS
from nuclia.sdk.zones import NucliaZones

from .utils import CustomFormatter


class NucliaCLI(object):
    def __init__(self):
        self.auth = get_auth()
        self.accounts = NucliaAccounts()
        self.zones = NucliaZones()
        self.kbs = self.knowledgeboxes = NucliaKBS()
        self.kb = self.knowledgebox = NucliaKB()
        self.nuas = NucliaNUAS()
        self.nua = NucliaNUA()


def run():
    logging.basicConfig(level=logging.INFO, handlers=[])
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(CustomFormatter())
    logger.addHandler(ch)

    try:
        fire.Fire(NucliaCLI)
    except exceptions.AuthError:
        handleAuthError()
    except NeedUserToken:
        handleAuthError()
    except UserTokenExpired:
        handleAuthError()


def handleAuthError():
    logger.error("Login required.")
    logger.info("Run `nuclia auth login` to login.")
    sys.exit(1)
