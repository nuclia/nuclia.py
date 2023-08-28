from nuclia.sdk.predict import NucliaPredict
from nuclia.sdk.process import NucliaProcess
from nuclia.sdk.train import NucliaTrain


class NucliaNUA:
    def __init__(self):
        self.predict = NucliaPredict()
        self.process = NucliaProcess()
        self.train = NucliaTrain()
