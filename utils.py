from typing import MutableSequence, List, Callable, TypeVar, IO, Type, Optional, Any
T = TypeVar('T')

import time
from threading import Thread
from datetime import datetime
from collections import deque

import numpy as np


should_run = True

def should_stop() -> None:
    global should_run
    should_run = False

def period_function(period: float, target: Callable) -> Callable:
    last = time.time()
    period = period
    def f() -> Any:
        nonlocal last, period
        if time.time() - last >= period:
            last = time.time()
            return target()
    return f

def make_time_tracker(srate: int) -> Callable[[T], T]:
    t0 = time.time()
    srate = srate
    ctr = srate
    def f(x: T) -> T:
        nonlocal ctr, t0, srate
        ctr -= 1
        if ctr <=0:
            end = time.time()
            print('{} samples in: {}'.format(srate, end - t0))
            t0 = end
            ctr = srate
        return x
    return f


class FFTCollector():
    def __init__(self, sampling_rate: int, seq_overlap: float, seq_len: int, nchannels: int):
        self.nchannels = nchannels
        # self.fft_frequencies = int(sampling_rate/2)
        self.num_samples = seq_len
        self.seq_period = int(self.num_samples * (1.0 - seq_overlap))
        self.sample_counter = self.num_samples  # first time full
        self.channel_buffers = [] # type: List[deque]
        for i in range(self.nchannels):
            self.channel_buffers.append(deque(maxlen=self.num_samples))
        tx = np.fft.fftfreq(self.num_samples)
        self.mask = tx > 0
        self.x = tx[self.mask]
        self.nfreq = len(self.x)

    def fft_channel(self, channel_seq: deque) -> np.array:
        seq = np.array(channel_seq)
        fft = np.fft.fft(seq)[self.mask]
        return np.abs(fft / self.num_samples) * 2

    def tick(self, sample: np.array) -> Optional[List[np.array]]:
        for i in range(self.nchannels):
            self.channel_buffers[i].append(sample[i])
        self.sample_counter -= 1
        if self.sample_counter > 0:
            return None
        return list(map(self.fft_channel, self.channel_buffers))


def vec_to_csv(out: IO, vec: np.ndarray) -> None:
    a = np.array2string(vec, max_line_width=999999, separator=',')[1:-1] # skip [ & ]
    out.write('{}\n'.format(a))


def open_record(name: str = None, srate: int = 0, ext: str = 'csv', mode: str = 'w') -> Callable[[T], T]:
    if not name:
        name = '{}_{}.{}'.format(datetime.now().strftime('%Y-%m-%d-%H:%M:%S'), srate, ext)
    name = 'records/' + name
    out = open(name, mode)
    data = deque() # type: deque

    def record_monitor() -> None:
        while should_run:
            time.sleep(1)
        print('INFO: Flushing {}'.format(name))
        for r in data:
            if isinstance(r, np.ndarray):
                a = np.array2string(r, max_line_width=999999, separator=',')[1:-1]
                out.write('{}\n'.format(a))
            else:
                print('{} is not a np.array'.format(r))
        print('INFO: Done')
        out.close()

    Thread(target=record_monitor, name=name+'record_monitor').start()

    def write(vec: T) -> T:
        nonlocal data
        data.append(vec)
        return vec

    return write

def compact_duration(n: int) -> str:
    hours = n // 3600
    minutes = (n - hours * 3600) // 60
    seconds = n - hours * 3600 - minutes * 60
    if hours == 0:
        if minutes == 0:
            return '{}s'.format(seconds)
        else:
            return '{}m{}s'.format(minutes, seconds)
    else:
        return '{}h{}m{}s'.format(hours, minutes, seconds)
