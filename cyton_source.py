import struct
from typing import List, Iterator, Callable, IO

import mne
from mne.io import RawArray
import numpy as np
from openbci import cyton as bci
import random
import time

import utils
from utils import vec_to_csv
from interfaces import Parameters, Source

# https://docs.openbci.com/docs/02Cyton/CytonSDK

# https://docs.openbci.com/docs/02Cyton/CytonDataFormat
# microvolts per 'count': ref voltage for ADS1299. set by its hardware / gain (empirical value for chip) / because ADS1299 :shrug:
SCALE_FACTOR_EEG = (4500000.0)/24/(2**23-1)
SCALE_FACTOR_AUX = 0.002 / (2**4)

def convert_int(s: str) -> int:
    if int(s[:2], 16) > 127:
        pfx = 'ff'
    else:
        pfx = '00'
    return struct.unpack('>i', int(pfx+s, 16).to_bytes(4, 'big'))[0]


def convert_openbci_input(name: str, nc: int) -> Iterator[List[int]]:
    with open(name, 'r') as inp:
        for line in inp:
            try:
                l = line[:-1].split(',')
            except:
                continue
            if len(l) >= nc+1 and len(l) <= nc+4:
                if len(l[nc]) != 6: # skip a specific case when file ends on the packet end
                    continue
                yield list(map(convert_int,l[1:nc+1])) # skip timestamp ... skip non-eeg data


def sampling_rate_string(sr: int) -> bytes:
    if sr == 250:
        return b'~6'
    elif sr == 500:
        return b'~5'
    elif sr == 1000:
        return b'~4'
    elif sr == 2000:
        return b'~3'
    elif sr == 4000:
        return b'~2'
    elif sr == 8000:
        return b'~1'
    elif sr == 16000:
        return b'~0'
    else:
        raise Exception('Unexpected sampling rate')

class CytonSource(Source[bci.OpenBCICyton]):
    @classmethod
    def setup(self, params: Parameters, port: str) -> bci.OpenBCICyton:
        # timeout to handle case when board will not stream because of SPS > 250 (v3.1.2-freeSD)
        board = bci.OpenBCICyton(port=port, scaled_output=False, log=True, timeout=3)
        # board = FakeBoard(params.sampling_rate)
        time.sleep(0.5)
        board.ser_write(sampling_rate_string(params.sampling_rate))
        time.sleep(0.5)
        board.print_incoming_text()
        return board

    @classmethod
    def default_callback(self, sample: bci.OpenBCISample) -> np.ndarray:
        return np.array(sample.channel_data)*SCALE_FACTOR_EEG

    @classmethod
    def sample_to_csv(self, out: IO, sample: bci.OpenBCISample) -> None:
        vec_to_csv(out, self.default_callback(sample))

    @classmethod
    def sample_write_raw(self, out: IO, sample: bci.OpenBCISample) -> None:
        out.write(sample)

    @classmethod
    def gen_rand(self, params: Parameters, callback : Callable[[bci.OpenBCISample], None]) -> None:
        while utils.should_run:
            sample = bci.OpenBCISample(None, [random.randrange(-255,255)] * params.nchannels, None)
            callback(sample)
            time.sleep(1.0/params.sampling_rate)

    @classmethod
    def convert_csv(self, name: str, params: Parameters) -> RawArray:
        with open(name, 'r') as inp:
            samples = [[float(s) for s in l.split(',')] for l in inp]
        arr = np.array(samples).transpose()  # group by channel
        scaled = np.divide(arr, np.amax(arr, axis=1)[:, np.newaxis])
        info = mne.create_info(
            ch_names=params.electrode_topology,
            sfreq = params.sampling_rate,
            ch_types = 'eeg',
            verbose = None
        )
        raw = RawArray(scaled, info)
        return raw

    @classmethod
    def convert_txt(self, name: str, params:Parameters) -> RawArray:
        samples = list(convert_openbci_input(name, params.nchannels))
        arr = np.array(samples).transpose()
        scaled = np.divide(arr, np.amax(arr, axis=1)[:, np.newaxis])
        info = mne.create_info(
            ch_names=params.electrode_topology,
            sfreq = params.sampling_rate,
            ch_types = 'eeg',
            verbose = None
        )
        raw = RawArray(scaled, info)
        return raw

    @classmethod
    def import_data(self, name: str, params:Parameters) -> RawArray:
        if name.lower().endswith('.txt'):
            return self.convert_txt(name, params)
        elif name.lower().endswith('.csv'):
            return self.convert_csv(name, params)
        else:
            raise Exception('Unsupported format; txt or csv expected')


class FakeBoard:
    class Ser:
        def __init__(self):
            self.buf = b''

        def write(self, s):
            self.buf = self.buf + s

        def inWaiting(self):
            return len(self.buf) > 0

        def read(self):
            t = self.buf
            self.buf = b''
            return t

    def __init__(self, sr, *args, **kwargs):
        self.ser = FakeBoard.Ser()
        self.streaming = False
        self.sampling_rate = sr

    def ser_write(self, cmd):
        self.ser.write(b'|cmd: '+ cmd + b'|')

    def print_incoming_text(self):
        print(self.ser.read().decode('utf-8'))

    def start_streaming(self, cb):
        self.streaming = True
        self.gen_sin(cb)

    def stop(self):
        self.streaming = False

    def gen_sin(self, callback : Callable[[bci.OpenBCISample], None]) -> None:
        phase = 0.0
        step = 1.0/self.sampling_rate
        while self.streaming:
            sample = bci.OpenBCISample(None, [(np.sin(phase) + (np.sin(10*phase)/5 if i > 4 else (np.sin(phase*60) if i == 3 else 0)))*4500 for i in range(8)], None)
            phase += step * 2 * np.pi
            callback(sample)
            time.sleep(1.0/self.sampling_rate)
