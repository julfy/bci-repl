import time

import utils

from openbci import cyton as bci
import numpy as np
from viz import Gui
from threading import Thread

SCALE_FACTOR_EEG = (4500000)/24/(2**23-1) #uV/count
SCALE_FACTOR_AUX = 0.002 / (2**4)

def mk_to_csv(out):
    def callback(sample):
        a = np.array(sample.channel_data)*SCALE_FACTOR_EEG
        a = np.array2string(a, max_line_width=999999, separator=',')[1:-1]
        # print('{}\n'.format(a))
        out.write('{}\n'.format(a))
    return callback

# board.ser.write(b'v')
# time.sleep(0.100)

# board.ser_write(b'[')
# time.sleep(0.100)

# need thread
# with open('test.csv', 'w') as out:
#     board.start_streaming(mk_to_csv(out))

# board.ser.write(b'b')
# board.streaming = True

# print(board.streaming)

# board.print_packets_in()
from topology import top_8c_10_20, coords
all = [k for k,v in coords.items()]
print(len(all))
gui = Gui(channel_names=all)
cmds = {}
threads = []
board = None

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


@defcmd(['exit', 'q'], '# - stop everything and exit repl')
def cmd_exit(args):
    utils.should_run = False
    time.sleep(0.5)
    gui.root.quit()

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

@defcmd('file', '<file># - replay file')
@in_thread
def cmd_file(args):
    import csv
    with open(args[0], 'r') as inp:
        for l in csv.reader(inp):
            if not utils.should_run:
                break
            gui.callback(list(map(float,l)))
            time.sleep(0.03)

@defcmd('connect', '[port]# - connect to board')
def cmd_connect(args):
    port = args[0] if args and len(args) > 1 else '/dev/ttyUSB0'
    board = bci.OpenBCICyton(port=port, scaled_output=False, log=True)

@defcmd('stream', '[file]# - start stream; file name for stream record')
def cmd_stream(args):
    pass

@defcmd('c', '<command># - command to send to the board')
def cmd_c(args):
    if not board:
        raise Exception('Board not present!')
    board.ser_write(bytes(' '.join(args)))

@defcmd('rand', '<start|stop># - generate random noise')
@in_thread
def cmd_rand(args):
    from utils import gen_rand
    gen_rand(8, gui.callback)

def repl():
    while utils.should_run:
        full_cmd = input("> ").split(' ')
        cmd = full_cmd[0]  # catch exn
        args = full_cmd[1:]
        if cmd == '':
            pass
        elif cmd in cmds:
            cmds[cmd][1](args)
        else:
            print('Unknown cmd: {}'.format(cmd))

loop = Thread(target=repl)
loop.start()

gui.start()

loop.join()
for t in threads:
    t.join()
