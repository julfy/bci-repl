import time
import traceback
from threading import Thread
from functools import reduce

from typing import Optional

from openbci import cyton as bci
import numpy as np

import utils
from viz import Gui

G_params = None
G_cmds = {}
G_threads = []
G_board = None
G_gui = None
G_callback_seq = [utils.simple_scale]

def G_callback(inp):
    res = inp
    for f in G_callback_seq:
        res = f(res)
    return res
    # return reduce(lambda val, f: f(val), G_callback_seq, initial=inp)


def G_add_callback(f):
    global G_callback_seq
    G_callback_seq.append(f)


class ArgError(Exception):
    pass


def get_arg (args, i, strict=False):
    if len(args) < i+1:
        if strict:
            raise ArgError('no {} arg'.format(i))
        else:
            return None
    else:
        return args [i]


def defcmd(cmdl, help):
    def dec(f):
        def wrap(args):
            try:
                f(args)
            except Exception:
                print('Error during execution: {}\n{}'.format(traceback.format_exc(), help))

        v=[help, wrap]
        if isinstance(cmdl, list):
            for c in cmdl:
                if not isinstance(c, str):
                    raise Exception('Bad cmd name: {}'.format(c))
                G_cmds.update({c: v})
        elif isinstance(cmdl, str):
            G_cmds.update({cmdl: v})
        else:
            raise Exception('Bad cmd name: {}'.format(cmdl))
        return wrap
    return dec


def in_thread(f):
    def wrap(args):
        t = Thread(target=f, args=(args,), name=f.__name__)
        t.start()
        G_threads.append(t)
    return wrap


## COMMANDS ###


@defcmd(['exit', 'q'], '# - stop everything and exit repl')
def cmd_exit(args):
    utils.should_run = False
    time.sleep(0.5)
    if G_gui:
        G_gui.quit()


@defcmd(['help', 'h'], '[cmd]# - show help')
def cmd_help(args):
    if not args:
        for c, v in G_cmds.items():
            opts, doc = v[0].split('#', maxsplit=1)
            print('{:15} {:30}\t{}'.format(c, opts, doc))
    elif len(args) != 1:
        raise ArgError(str(args))
    else:
        print(G_cmds[args[0]][0])


@defcmd('gui','# - start GUI')
def cmd_gui(args):
    global G_gui, G_params
    G_gui = Gui(G_params.electrode_topology, sampling_rate=G_params.sampling_rate)
    G_add_callback(G_gui.callback)
    G_gui.start()


@defcmd('csv', '<csv># - replay preprocessed csv file')
@in_thread
def cmd_csv(args):
    import csv
    with open(args[0], 'r') as inp:
        for l in csv.reader(inp):
            if not utils.should_run:
                break
            G_callback(list(map(float,l)))
            time.sleep(1.0/G_params.sampling_rate) # TODO: save srate in file


@defcmd('connect', '[port]# - connect to board')
def cmd_connect(args):
    global G_board
    port = args[0] if args and len(args) > 1 else '/dev/ttyUSB0'
    G_board = bci.OpenBCICyton(port=port, scaled_output=False, log=True)

@defcmd('record', '<file># - open a new file to save data to')
def cmd_record(args):
    from utils import open_record

    fname = None if len(args) < 1 else args[0]
    writer = open_record(name=fname, srate=G_params.sampling_rate)
    G_add_callback(writer)


@defcmd('sstart', '# - start streaming from the board')
def cmd_sstart(args):
    if G_board:
        G_board.start_streaming(G_callback)
    else:
        raise Exception('No board connected')


@defcmd('sstop', '# - stop stream')
def cmd_sstop(args):
    if G_board and G_board.streaming:
        G_board.stop()


@defcmd('vstart', '<file># - start video with data collection')
@in_thread
def cmd_vstart(args):
    import video

    inp_file = get_arg(args, 0)
    if not inp_file or len(inp_file) <= 0:
        raise ArgError('Video file name expected')
    v = video.Video(inp_file)
    cmd_sstart(args[1:])
    v.run()
    cmd_sstop([])


@defcmd('c', '<command># - command to send to the board')
def cmd_c(args):
    if not G_board:
        raise Exception('Board not present!')
    G_board.ser_write(' '.join(args).encode())


@defcmd('rand', '<start|stop># - generate random noise')
@in_thread
def cmd_rand(_args):
    from utils import gen_rand, gen_sin
    gen_rand(G_params.sampling_rate, G_callback)


# track_time = lambda _: 0
# def process_cb(sample, out=None):
#     from utils import simple_scale, vec_to_csv
#     vec = simple_scale(sample)
#     track_time()
#     if out:
#         vec_to_csv(out, vec)
#     G_callback(vec)


def repl():
    while utils.should_run:
        full_cmd = input(">>> ").split(' ') # TODO: escape chars
        # def read_cmd():
        #     nonlocal full_cmd
        #     G_gui.update()
        #     full_cmd = input(">>> ").split(' ')
        # inp_thread = Thread(target = read_cmd, name = 'prompt_input')
        # inp_thread.start()
        # while utils.should_run and inp_thread.is_alive():
        #     inp_thread.join(1.0)
        if not full_cmd or len(full_cmd) <= 0:
            continue
        cmd = full_cmd[0]  # catch exn
        args = full_cmd[1:]
        if cmd == '':
            pass
        elif cmd in G_cmds:
            G_cmds[cmd][1](args)
        else:
            print('Unknown cmd: {}'.format(cmd))

if __name__ == '__main__':
    # from pyinstrument import Profiler
    # profiler = Profiler()
    # profiler.start()

    import yappi
    yappi.start()

    G_params = utils.Parameters(sampling_rate=250, topology_name='top_8c_10_20')
    G_add_callback(utils.make_time_tracker(G_params.sampling_rate))
    # cmd_vstart(['sample.mp4'])
    cmd_record([])
    cmd_gui([])
    cmd_rand([])
    # cmd_sstart([])

    repl()

    for t in G_threads:
        t.join()

    print('========')
    # profiler.stop()
    # print(profiler.output_text(unicode=True, color=True, show_all=True))

    yappi.get_func_stats().print_all()
    yappi.get_thread_stats().print_all()
