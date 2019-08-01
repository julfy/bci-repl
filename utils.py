from typing import *

import random
import time

should_run = True

def gen_rand(n_channels, callback : Callable[[List[float]], None]):
    while should_run:
        vec = [random.uniform(-255,255) for i in range(n_channels)]
        callback(vec)
        time.sleep(1.0/250.0)
