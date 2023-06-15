import fire  # type: ignore

from nuclia.cli.accounts import NucliaAccounts
from nuclia.cli.kb import NucliaKB
from nuclia.cli.kbs import NucliaKBS
from nuclia.cli.nua import NucliaNUA
from nuclia.cli.nuas import NucliaNUAS
from nuclia.cli.zones import NucliaZones
from nuclia.data import get_auth


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
    fire.Fire(NucliaCLI)
