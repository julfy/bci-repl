from typing import List, Optional, Any, Callable, Dict, Union, TypeVar, cast
T = TypeVar('T')

import sys
import json
import time
import argparse

from base import Context
from cyton_source import CytonSource
from interfaces import Parameters
import repl
import utils


class Scenario:
    def __init__(self) -> None:
        self.name = 'default'
        self.topology_name = 'top_8c_10_20'
        self.sampling_rate = 250
        self.commands = [] # type: List[str]
        self.annotations = None
        self.cstep = 0
        self.start = -1
        self.stop = -1

    def load(self, fname: str) -> None:
        with open(fname, 'r') as inp:
            scn = json.load(inp)
            self.name = scn['name']
            self.topology_name = scn['topology']
            self.sampling_rate = int(scn['sampling_rate'])
            self.commands = scn['commands']
            self.annotations = scn['annotations']
            self.cstep = 0
            self.start = -1
            self.stop = -1

    def step(self, ctx: Context) -> bool:
        if self.cstep < len(self.commands):
            cmd, *args = self.commands[self.cstep].split(' ')
            print('>>>', cmd, *args)
            repl.exec_cmd(cmd, ctx, args)
            self.cstep+=1
            return True
        else:
            return False

    def run(self, ctx: Context) -> None:
        print('Running scenario {}'.format(self.name))
        self.start = int(time.time())
        while self.step(ctx):
            pass
        self.stop = int(time.time())
        print('Finished scenario in {}'.format(utils.compact_duration(self.stop-self.start)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--scenario', help = 'Run scenario')
    group.add_argument('--session', help = 'Import session')

    args = parser.parse_args()

    scenario = Scenario() # default settings
    if args.scenario:
        scenario.load(args.scenario)

    # Setup
    params = Parameters(sampling_rate=scenario.sampling_rate, topology_name=scenario.topology_name, source=CytonSource)
    ctx = Context(params)
    ctx.add_callback(params.Source.default_callback)
    ctx.annotations = scenario.annotations
    ctx.session.name = scenario.name

    if args.session:
        ctx.load_session(args.session)

    if args.scenario:
        scenario.run(ctx)

    # from pyinstrument import Profiler
    # profiler = Profiler()
    # profiler.start()

    # import yappi
    # yappi.start()

    repl.repl(ctx)

    # print('========')
    # profiler.stop()
    # print(profiler.output_text(unicode=True, color=True, show_all=True))

    # yappi.get_func_stats().print_all()
    # yappi.get_thread_stats().print_all()
