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
        board.ser_write(sampling_rate_string(params.sampling_rate))
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
    def gen_sin(self, params: Parameters, callback : Callable[[bci.OpenBCISample], None]) -> None:
        phase = 0.0
        cnt = 0
        while utils.should_run:
            sample = bci.OpenBCISample(None, [np.sin(phase+i)*4500 for i in range(params.nchannels)], None)
            phase+=0.05
            callback(sample)
            time.sleep(1.0/20)
            # cnt+=1
            # if cnt > 1000:
                # should_stop()
                # break

    @classmethod
    def convert_txt(self, name: str, params:Parameters) -> RawArray:
        samples = list(convert_openbci_input(name, params.nchannels))
        arr = np.array(samples).transpose()
        scale = 1.0 / np.amax(arr) * 3
        info = mne.create_info(
            ch_names=params.electrode_topology,
            sfreq = params.sampling_rate,
            ch_types = 'eeg',
            verbose = None
        )
        raw = RawArray(arr * scale, info)
        return raw
