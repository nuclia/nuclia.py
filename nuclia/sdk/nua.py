from nuclia.sdk.agent import NucliaAgent
from nuclia.sdk.predict import NucliaPredict
from nuclia.sdk.process import NucliaProcessing


class NucliaNUA:
    def __init__(self):
        self.predict = NucliaPredict()
        self.process = NucliaProcessing()
        self.agent = NucliaAgent()
