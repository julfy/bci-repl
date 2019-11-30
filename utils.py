import random
import time
from threading import Thread
from datetime import datetime
import signal
import os
from collections import deque

from typing import List, Callable

from openbci import cyton as bci
import numpy as np

from topology import get_topology


should_run = True

class Parameters:
    def __init__(self, sampling_rate: int, topology_name: str):
        self.sampling_rate = sampling_rate
        self.topology_name = topology_name
        self.electrode_topology = get_topology(topology_name)
        self.nchannels = len(self.electrode_topology)

def should_stop():
    global should_run
    should_run = False

def make_time_tracker(srate):
    t0 = time.time()
    srate = srate
    ctr = srate
    def f(x=None): #  take and return same value to allow adding to callbeck sequence
        nonlocal ctr, t0, srate
        ctr -= 1
        if ctr <=0:
            end = time.time()
            print('{} samples in: {}'.format(srate, end - t0))
            t0 = end
            ctr = srate
        return x
    return f


def gen_rand(n_channels, callback : Callable[[bci.OpenBCISample], None]):
    cnt = 0
    global should_run
    while should_run:
        sample = bci.OpenBCISample(None, [random.randrange(-255,255)] * n_channels, None)
        callback(sample)
        time.sleep(1.0/250.0)
        cnt+=1
        if cnt >= 1000:
            should_stop()
            break

def gen_sin(n_channels, callback : Callable[[bci.OpenBCISample], None]):
    phase = 0
    cnt = 0
    global should_run
    while should_run:
        sample = bci.OpenBCISample(None, [np.sin(phase+i)*5 for i in range(n_channels)]*n_channels, None)
        phase+=0.005
        callback(sample)
        time.sleep(1.0/250.0)
        cnt+=1
        if cnt > 1000:
            os._exit(0)


class FFTCollector():
    def __init__(self, sampling_rate: int, seq_overlap: float, seq_len: int, nchannels: int):
        self.nchannels = nchannels
        # self.fft_frequencies = int(sampling_rate/2)
        self.num_samples = seq_len
        self.seq_period = int(self.num_samples * (1.0 - seq_overlap))
        self.sample_counter = self.num_samples  # first time full
        self.channel_buffers = []
        for i in range(self.nchannels):
            self.channel_buffers.append(deque(maxlen=self.num_samples))
        tx = np.fft.fftfreq(nsamples)
        self.mask = tx > 0
        self.x = tx[self.mask]
        self.nfreq = len(self.x)

    def fft_channel(self, channel_seq):
        seq = np.array(channel_seq)
        fft = np.fft.fft(seq)[self.mask]
        return np.abs(fft[i] / self.num_samples) * 2

    def tick(self, sample: np.array):
        for i in range(self.nchannels):
            self.channel_buffers[i].append(sample[i])
        self.sample_counter -= 1
        if self.sample_counter > 0:
            return None
        return map(fft_channel, self.channel_buffers)



SCALE_FACTOR_EEG = (4500000)/24/(2**23-1) #uV/count
SCALE_FACTOR_AUX = 0.002 / (2**4)

def simple_scale(sample: bci.OpenBCISample):
    return np.array(sample.channel_data)*SCALE_FACTOR_EEG


def vec_to_csv(out, vec):
    a = np.array2string(vec, max_line_width=999999, separator=',')[1:-1] # skip [ & ]
    out.write('{}\n'.format(a))


def sample_to_csv(out, sample):
    vec_to_csv(out, simple_scale(sample))


def sample_write_raw(out, sample):
    out.write(sample)


def open_record(name=None, srate=0, ext='csv', mode='w'):
    if not name:
        name = '{}_{}.{}'.format(datetime.now().strftime('%Y-%m-%d-%H:%M:%S'), srate, ext)
    name = 'records/' + name
    out = open(name, mode)
    data = deque()

    def record_monitor():
        while should_run:
            time.sleep(1)
        print('INFO: Flushing {}'.format(name))
        for r in data:
            a = np.array2string(r, max_line_width=999999, separator=',')[1:-1]
            out.write('{}\n'.format(a))
        print('INFO: Done')
        out.close()

    Thread(target=record_monitor, name=name+'record_monitor').start()

    def write(vec):
        nonlocal data
        data.append(vec)

    return write
