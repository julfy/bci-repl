import pickle
import random
import time
import mne

from typing import List, Optional, Callable, TypeVar, Dict, Any
T = TypeVar('T')

import utils
from interfaces import Parameters, SubprocessInterface
from cyton_source import CytonSource


class Scenario:
    def __init__(self) -> None:
        self.name = 'default'
        self.topology_name = 'top_8c_10_20'
        self.sampling_rate = 250
        self.commands = [] # type: List[str]
        self.initial_annotations = {'onset': [], 'duration': [], 'description':[]} # type: Dict
        self.cstep = 0
        self.start = -1
        self.stop = -1
        self.random_seed = random.randint(1, 1000000)

    @classmethod
    def load(cls, fname: str) -> None:
        with open(fname, 'r') as inp:
            jsons = inp.read()
        json_clean = re.sub('//.*\n', '\n', jsons)
        scn = json.loads(json_clean)
        self = Scenario()
        self.name = scn['name']
        self.topology_name = scn['topology']
        self.sampling_rate = int(scn['sampling_rate'])
        self.commands = scn['commands']
        self.initial_annotations = scn['annotations']
        self.random_seed = scn.get('random_seed', self.random_seed)
        self.cstep = 0
        self.start = -1
        self.stop = -1
        return self

    def step(self, ssn: 'Session', executor: Callable) -> bool:
        if self.cstep < len(self.commands):
            cmd, *args = self.commands[self.cstep].split(' ')
            print('>>>', cmd, *args)
            executor(cmd, ssn, args)
            self.cstep+=1
            return True
        else:
            return False

    def run(self, ssn: 'Session', executor: Callable) -> None:
        print('Running scenario {}'.format(self.name))
        self.start = int(time.time())
        while self.step(ssn):
            pass
        self.stop = int(time.time())
        print('Finished scenario in {}'.format(utils.compact_duration(self.stop-self.start)))


class Session:
    def __init__(self, scenario: Scenario) -> None:
        self.name = scenario.name
        self.params = Parameters(sampling_rate=scenario.sampling_rate, topology_name=scenario.topology_name, source=CytonSource)

        self.random_seed = scenario.random_seed
        self.log = []
        self.tstart = 0.0
        self.tstop = 0.0
        self.sd_out_file = None

        # Runtime
        self.board = None
        self.gui = None # type: Optional[SubprocessInterface]
        self.callback_seq = [self.params.Source.default_callback] # type: List[Callable[[T], T]]

        self.data = None # type: Optional[mne.io.RawArray]
        self.annotations = scenario.initial_annotations # type: Dict

    def start(self) -> None:
        self.tstart = time.time()

    def stop(self) -> None:
        self.tstop = time.time()

    def add_callback(self, f: Callable[[T], T]) -> None:
        self.callback_seq.append(f)

    def callback(self, inp: T) -> T:  # returns same type as inp
        res = inp
        for f in self.callback_seq:
            res = f(res)
            print(res)
        return res
        # return reduce(lambda val, f: f(val), G_callback_seq, initial=inp)

    def import_data(self, fname: Optional[str] = None) -> None:
        if fname:
            self.data = self.params.Source.import_data(fname, self.params)
        elif self.sd_out_file:
            self.data = self.params.Source.import_data(self.sd_out_file, self.params)

        if self.annotations:
            a = mne.Annotations(**self.annotations)
            self.data.set_annotations(a)  # type: ignore

        if self.tstop == 0.0 and self.data is not None:
            self.tstop = self.tstart + (self.data.n_times / self.sampling_rate)

    def __str__(self) -> str:
        pretty = """Session: {} ({} - {})
    Duration: {}
    Sampling rate: {}
    SD file name: {}
    Data: {}"""
        data_shape = None
        if self.data is not None:
            data_shape = "{} x {}".format(self.data.ch_names, self.data.n_times)
        return pretty.format(
            self.name, self._strtime(self.tstart), self._strtime(self.tstop),
            utils.compact_duration(int(self.tstop - self.tstart)),
            self.params.sampling_rate,
            self.sd_out_file,
            data_shape
        )

    def to_json(self) -> Dict[str, Any]:
        pass

    def _strtime(self, timestamp: float) -> str:
        return time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime(timestamp))

    def save(self, fname: Optional[str] = None) -> None:
        if not fname:
            fname = 'sessions/' + self.name + '_' + self._strtime(self.tstart) + '.dat'
        with open(fname, 'wb') as out:
            pickle.dump(self, out)

    @classmethod
    def load(cls, fname: str) -> 'Session':
        with open(fname, 'rb') as inp:
             tmp = pickle.load(inp)
             tmp.board = None
             tmp.gui = None
             return tmp
