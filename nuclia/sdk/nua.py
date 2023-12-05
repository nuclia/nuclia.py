from nuclia.sdk.agent import NucliaAgent
from nuclia.sdk.predict import NucliaPredict
from nuclia.sdk.process import NucliaProcessing
from nuclia.sdk.train import NucliaTrain


class NucliaNUA:
    def __init__(self):
        self.predict = NucliaPredict()
        self.process = NucliaProcessing()
        self.train = NucliaTrain()
        self.agent = NucliaAgent()
