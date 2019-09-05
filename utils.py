from typing import *
from openbci import cyton as bci
from datetime import datetime
from threading import Thread

import numpy as np
import random
import time

should_run = True

def gen_rand(n_channels, callback : Callable[[bci.OpenBCISample], None]):
    while should_run:
        sample = bci.OpenBCISample(None, [random.uniform(-255,255) for i in range(n_channels)], None)
        callback(sample)
        time.sleep(1.0/250.0)

SCALE_FACTOR_EEG = (4500000)/24/(2**23-1) #uV/count
SCALE_FACTOR_AUX = 0.002 / (2**4)

def simple_scale(sample : bci.OpenBCISample):
    return np.array(sample.channel_data)*SCALE_FACTOR_EEG

def sample_to_csv(out, sample):
    a = simple_scale(sample)
    a = np.array2string(a, max_line_width=999999, separator=',')[1:-1]
    # print('{}\n'.format(a))
    out.write('{}\n'.format(a))

def sample_write_raw(out, sample):
    out.write(sample)

def open_record(name=None, ext='csv', mode='w'):
    if not name:
        name = 'records/' + datetime.now().strftime('%Y-%m-%d-%H:%M:%S') + '.' + ext
    out = open(name, mode)

    def f():
        while should_run:
            time.sleep(1)
            out.flush()
        out.close()
    Thread(target=f).start()
    return out
