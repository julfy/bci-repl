import time

import utils

from openbci import cyton as bci
import numpy as np
from viz import Gui
from threading import Thread

NCHANNELS=8

cmds = {}
threads = []
board = None
gui = None

class ArgError(Exception):
    pass

def defcmd(cmdl, help):
    def dec(f):
        def wrap(args):
            try:
                f(args)
            except Exception as exn:
                print('Error during execution: {}\n{}'.format(repr(exn), help))

        v=[help, wrap]
        if isinstance(cmdl, list):
            for c in cmdl:
                if not isinstance(c, str):
                    raise Exception('Bad cmd name: {}'.format(c))
                cmds.update({c: v})
        elif isinstance(cmdl, str):
            cmds.update({cmdl: v})
        else:
            raise Exception('Bad cmd name: {}'.format(cmdl))
        return wrap
    return dec

def in_thread(f):
    def wrap(args):
        t = Thread(target=f, args=(args,))
        t.start()
        threads.append(t)
    return wrap

## COMMANDS ###

@defcmd(['exit', 'q'], '# - stop everything and exit repl')
def cmd_exit(args):
    utils.should_run = False
    time.sleep(0.5)
    if gui:
        gui.quit()

@defcmd(['help', 'h'], '[cmd]# - show help')
def cmd_help(args):
    if not args:
        for c, v in cmds.items():
            opts, doc = v[0].split('#', maxsplit=1)
            print('{:15} {:30}\t{}'.format(c, opts, doc))
    elif len(args) != 1:
        raise ArgError(str(args))
    else:
        print(cmds[args[0]][0])

@defcmd('gui','# - start GUI')
def cmd_gui(args):
    global gui
    from topology import get_topology
    gui = Gui(channels=get_topology(args[0]))
    gui.start()

@defcmd('csv', '<csv># - replay preprocessed csv file')
@in_thread
def cmd_csv(args):
    import csv
    with open(args[0], 'r') as inp:
        for l in csv.reader(inp):
            if not utils.should_run:
                break
            gui.callback(list(map(float,l)))
            time.sleep(0.03)

@defcmd('connect', '[port]# - connect to board')
def cmd_connect(args):
    global board
    port = args[0] if args and len(args) > 1 else '/dev/ttyUSB0'
    board = bci.OpenBCICyton(port=port, scaled_output=False, log=True)

@defcmd('sstart', '[file]# - start stream; file name for stream record')
def cmd_sstart(args):
    from utils import open_record, sample_to_csv

    fname = None if len(args) == 0 else args[0]
    out = open_record(name=fname)
    def cb(sample):
        sample_to_csv(out, sample)
        process_cb(sample)
    if board:
        board.start_streaming(cb)

@defcmd('sstop', '# - stop stream')
def cmd_sstop(args):
    if board and board.streaming:
        board.stop()

@defcmd('c', '<command># - command to send to the board')
def cmd_c(args):
    if not board:
        raise Exception('Board not present!')
    board.ser_write(' '.join(args).encode())

@defcmd('rand', '<start|stop># - generate random noise')
@in_thread
def cmd_rand(_args):
    from utils import gen_rand
    gen_rand(NCHANNELS, process_cb)


# lazy way to define default callback
def process_cb(sample):
    gui.callback(sample)

def repl():
    while utils.should_run:
        # try:
        #     if gui:
        #         gui.update()
        # except Exception:
        #     pass
        full_cmd = input("> ").split(' ')
        cmd = full_cmd[0]  # catch exn
        args = full_cmd[1:]
        if cmd == '':
            pass
        elif cmd in cmds:
            cmds[cmd][1](args)
        else:
            print('Unknown cmd: {}'.format(cmd))

if __name__ == '__main__':
    # cmd_gui(['top_8c_10_20'])
    # cmd_rand([])
    # cmd_sstart([])

    repl()
    for t in threads:
        t.join()
