from typing import *

import random
import time

should_run = True

def gen_rand(callback : Callable[[List[float]], None]):
    while should_run:
        vec = [random.uniform(0,90) for i in range(16)]
        callback(vec)
        time.sleep(1.0/250.0)
