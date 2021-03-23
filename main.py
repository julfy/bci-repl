from typing import List, Optional, Any, Callable, Dict, Union, TypeVar, cast
T = TypeVar('T')

import sys
import argparse

from base import Scenario, Session
from interfaces import Parameters
import repl
import utils


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--scenario', help = 'Run scenario')
    group.add_argument('--session', help = 'Import session')
    args = parser.parse_args()

    scenario = Scenario.load(args.scenario) if args.scenario else Scenario()
    session = Session.load(args.session) if args.session else Session(scenario)

    if args.scenario:
        scenario.run(session, repl.exec_cmd)

    # from pyinstrument import Profiler
    # profiler = Profiler()
    # profiler.start()

    # import yappi
    # yappi.start()

    repl.repl(session)

    # print('========')
    # profiler.stop()
    # print(profiler.output_text(unicode=True, color=True, show_all=True))

    # yappi.get_func_stats().print_all()
    # yappi.get_thread_stats().print_all()
