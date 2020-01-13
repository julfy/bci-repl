import pickle
import time
import mne

from typing import List, Optional, Callable, TypeVar, Dict, Any
T = TypeVar('T')

from interfaces import Parameters, SubprocessInterface


class Context:
    def __init__(self, params: Parameters):
        self.params = params
        self.board = None
        self.gui = None # type: Optional[SubprocessInterface]
        self.callback_seq = [] # type: List[Callable[[T], T]]
        self.log = None
        self.session = Session()
        self.annotations = None

    def callback(self, inp: T) -> T:  # returns same type as inp
        res = inp
        for f in self.callback_seq:
            res = f(res)
        return res
        # return reduce(lambda val, f: f(val), G_callback_seq, initial=inp)

    def add_callback(self, f: Callable[[T], T]) -> None:
        self.callback_seq.append(f)

    def load_session(self, fname: str) -> None:
        with open(fname, 'rb') as inp:
            self.session = pickle.load(inp)


class Session:
    def __init__(self, name: str = 'default') -> None:
        self.name = name
        # self.log = []
        self.tstart = 0.0
        self.tstop = 0.0
        self.sd_out_file = None
        self.data = None

    def start(self) -> None:
        self.tstart = time.time()

    def stop(self) -> None:
        self.tstop = time.time()

    def import_data(self, ctx: Context, fname: Optional[str] = None) -> None:
        if fname:
            self.data = ctx.params.Source.convert_txt(fname, ctx.params)
        elif self.sd_out_file:
            self.data = ctx.params.Source.convert_txt(self.sd_out_file, ctx.params)

        if ctx.annotations:
            a = mne.Annotations(**ctx.annotations)
            self.data.set_annotations(a)

    def __str__(self) -> str:
        pass

    def to_json(self) -> Dict[str, Any]:
        pass

    def plot(self, ctx: Context) -> None:
        if self.data:
            self.data.plot(
                n_channels = len(self.data.ch_names),
                duration=self.tstop - self.tstart,
                show=True,
                block=True,
                scalings = 'auto'
            )

    def save(self, fname: Optional[str] = None) -> None:
        if not fname:
            fname = 'sessions/' + self.name + time.strftime("_%Y-%m-%d-%H:%M:%S", time.localtime(self.tstart)) + '.dat'
        with open(fname, 'wb') as out:
            pickle.dump(self, out)
