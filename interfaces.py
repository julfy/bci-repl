from typing import IO, Any, Type, Callable, TypeVar, Generic
T = TypeVar('T')

import multiprocessing as mp
import time
from queue import Empty

import numpy as np

from topology import get_topology
import utils


class Parameters:
    def __init__(self, sampling_rate: int, topology_name: str, source: Type['Source']):
        self.sampling_rate = sampling_rate
        self.topology_name = topology_name
        self.electrode_topology = get_topology(topology_name)
        self.nchannels = len(self.electrode_topology)
        self.Source = source # type: Type['Source']


class Source(Generic[T]):
    @classmethod
    def setup(self, params: Parameters, port: str) -> T:
        raise NotImplemented

    @classmethod
    def default_callback(self, sample: Any) -> np.ndarray:
        raise NotImplemented

    @classmethod
    def sample_to_csv(self, out: IO, sample: Any) -> None:
        raise NotImplemented

    @classmethod
    def sample_write_raw(self, out: IO, sample: Any) -> None:
        raise NotImplemented

    @classmethod
    def gen_rand(self, params: Parameters, callback : Callable) -> None:
        raise NotImplemented

    @classmethod
    def gen_sin(self, params: Parameters, callback : Callable) -> None:
        raise NotImplemented

    @classmethod
    def import_data(self, name: str, params:Parameters) -> Any:
        raise NotImplemented


class SubprocessInterface:
    # Possible TODO: replace Class with enum selector for moar separation
    def __init__(self, Class: Type, params: Parameters):
        self.queue = mp.Queue(100)  # type: ignore
        self.should_run = mp.Value('b', True)
        # self.period = utils.period_function(1.0, lambda: print(self.queue.qsize()))
        self.process = mp.Process(target=self._run, args=(Class, params, self.queue, self.should_run,))
        self.process.start()

    def _run(self, Class: Type, params: Parameters, queue: mp.Queue, should_run: mp.Value) -> None:
        kwargs = Class.get_params(params)
        instance = Class(**kwargs)
        while should_run.value:
            try:
                instance.consume(queue.get(block=False))
            except Empty:
                time.sleep(0.1)
        instance.stop()

    def callback(self, val: Any) -> None:
        # self.period()
        if not self.queue.full():
            self.queue.put(val)

    def stop(self) -> None:
        self.should_run.value = False
        self.process.join()
