import sys
import fire  # type: ignore

from nuclia.data import get_auth
from nuclia.sdk.accounts import NucliaAccounts
from nuclia.sdk.kb import NucliaKB
from nuclia.sdk.kbs import NucliaKBS
from nuclia.sdk.nua import NucliaNUA
from nuclia.sdk.nuas import NucliaNUAS
from nuclia.sdk.zones import NucliaZones
from nucliadb_sdk import exceptions
from .utils import Colors

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
    try:
        fire.Fire(NucliaCLI)
    except exceptions.AuthError:
        sys.exit(f"{Colors.FAIL}Login required.{Colors.ENDC}\nRun `nuclia auth login` to login.")

