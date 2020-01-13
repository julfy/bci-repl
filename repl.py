from typing import List, Optional, Any, Callable, Dict, Union, TypeVar, cast
T = TypeVar('T')
TFun = TypeVar('TFun', bound=Callable[..., Any])
Args = List[str]

import time
import traceback
from threading import Thread
from collections import namedtuple

from base import Context, Session
from interfaces import SubprocessInterface
from tkinter_gui import TkInterGui
import utils

Cmd = namedtuple('Cmd', ['func', 'help'])
G_cmds = {} # type: Dict[str, Cmd]
G_threads = [] # type: List[Thread]


class ArgError(Exception):
    pass


def get_arg(args: Args, i: int, strict: bool = False) -> Optional[str]:
    if len(args) < i+1:
        if strict:
            raise ArgError('no {} arg'.format(i))
        else:
            return None
    else:
        return args [i]


class defcmd:
    def __init__(self, cmdl: Union[List[str], str], help: str):
        self.cmdl = cmdl
        self.help = help

    def __call__(self, f: TFun) -> TFun:
        from functools import wraps
        @wraps(f)
        def wrap(*args: Any) -> None:
            try:
                f(*args) # type: ignore
            except Exception:
                print('Error during execution: {}\n{}'.format(traceback.format_exc(), self.help))

        v = Cmd(func=wrap, help=self.help)
        if isinstance(self.cmdl, list):
            for c in self.cmdl:
                if isinstance(c, str):
                    G_cmds.update({c: v})
                else:
                    raise Exception('Bad cmd name: {}'.format(c))
        elif isinstance(self.cmdl, str):
            G_cmds.update({self.cmdl: v})
        else:
            raise Exception('Bad cmd name: {}'.format(self.cmdl))
        return cast(TFun, wrap)


def in_thread(f: T) -> T:
    def wrap(*args: Any) -> None:
        t = Thread(target=f, args=tuple(args), name=f.__name__) # type: ignore
        t.start()
        G_threads.append(t)
    return cast(T, wrap)


## COMMANDS ###

@defcmd('e', '<expr># - evaluate string as a code')
def cmd_eval(ctx: Context, *s: str) -> None:
    eval(' '.join(s))


@defcmd(['exit', 'q'], '# - stop everything and exit repl')
def cmd_exit(ctx: Context) -> None:
    utils.should_run = False
    cmd_sstop(ctx) #  stop stream just in case
    if ctx.gui:
        ctx.gui.stop()


@defcmd(['help', 'h'], '[cmd]# - show help')
def cmd_help(ctx: Context, cmd_name: str = None) -> None:
    def fmthelp(cmd: str, v: Cmd) -> str:
        opts, doc = v.help.split('#', maxsplit=1)
        return'{:15} {:30}\t{}'.format(cmd, opts, doc)

    if not cmd_name:
        for c, v in G_cmds.items():
            print(fmthelp(c, v))
    else:
        print(fmthelp(cmd_name, G_cmds[cmd_name]))

@defcmd('sleep', '<seconds># - pause')
def cmd_sleep(ctx: Context, duration: float) -> None:
    time.sleep(float(duration))

@defcmd('gui', '<start|stop># - start/stop GUI; default: start')
def cmd_gui(ctx: Context, action: str = 'start') -> None:
    if ctx.gui is not None and action == 'start':
        raise Exception('GUI already runnng')
    elif ctx.gui is not None and action == 'stop':
        ctx.gui.stop()
        ctx.gui = None
    elif ctx.gui is None and action == 'start':
        gui = SubprocessInterface(TkInterGui, ctx.params)
        ctx.gui = gui
        ctx.add_callback(gui.callback)
    elif ctx.gui is None and action == 'stop':
        raise Exception('No GUI to stop')
    else:
        raise Exception('Expected start|stop')


@defcmd('csv', '<csv># - replay preprocessed csv file')
@in_thread
def cmd_csv(ctx: Context, fname: str) -> None:
    import csv
    with open(fname, 'r') as inp:
        for l in csv.reader(inp):
            if not utils.should_run:
                break
            ctx.callback(list(map(float,l)))
            time.sleep(1.0/ctx.params.sampling_rate) # TODO: save srate in file


@defcmd('connect', '[port]# - connect to board')
def cmd_connect(ctx: Context, port: str = '/dev/ttyUSB0') -> None:
    ctx.board = ctx.params.Source.setup(ctx.params, port)


@defcmd('import', '[fname]# - import EEG data; default: SD card file name')
def cmd_import(ctx: Context, fname: Optional[str] = None) -> None:
    if ctx.session:
        ctx.session.import_data(ctx, fname)


@defcmd('save_session', '[fname]# - save session')
def cmd_save_session(ctx: Context, fname: Optional[str] = None) -> None:
    if ctx.session:
        ctx.session.save(fname)

@defcmd('plot_session', '# - display session graph')
def cmd_plot_session(ctx: Context) -> None:
    if ctx.session:
        ctx.session.plot(ctx)


@defcmd('record_local', '<file># - open a new file to save data to')
def cmd_record_local(ctx: Context, fname: str) -> None:
    from utils import open_record

    writer = open_record(name=fname, srate=ctx.params.sampling_rate)
    ctx.add_callback(writer)


@defcmd('record_sd', '<mode:ASFGHJKLa># - open a new file on SD card')
def cmd_record(ctx: Context, mode: str) -> None:
    if mode not in 'ASFGHJKLa':
        raise ArgError('expected mode: A|S|F|G|H|J|K|L|a')
    if not ctx.board:
        raise Exception('Board not present!')
    ctx.board.ser_write(mode.encode())
    time.sleep(0.5)
    if ctx.board.ser.inWaiting():
        line = ''
        c = ''
        while '$$$' not in line:
            c = ctx.board.ser.read().decode('utf-8', errors='replace')
            line += c
        b,e = line.find('OBCI'),line.find('.TXT')
        if b < 0 or e < 0:
            raise Exception('No file open confirmation: {}'.format(line))
        print(line)
        ctx.session.sd_out_file = line[b:e+4]
    else:
        raise Exception('No answer')


@defcmd('sstart', '# - start streaming from the board')
@in_thread
def cmd_sstart(ctx: Context) -> None:
    if ctx.board and not ctx.board.streaming:
        if ctx.session:
            ctx.session.start()
        ctx.board.start_streaming(ctx.callback)
    else:
        raise Exception('No board connected')


@defcmd('sstop', '# - stop stream')
def cmd_sstop(ctx: Context) -> None:
    if ctx.board and ctx.board.streaming:
        ctx.board.stop()
    if ctx.session:
        ctx.session.stop()


@defcmd('vrun', '<file># - start video with data collection; board should be preconfigured')
def cmd_vstart(ctx: Context, inp_file: str) -> None:
    import subprocess
    import os
    from vlc_ctrl.player import Player

    if not inp_file or len(inp_file) <= 0:
        raise ArgError('Video file name expected')

    with open(os.devnull,"w") as out:
        p = Player()
        subprocess.Popen(['vlc', inp_file], stderr=out)
        time.sleep(0.5) # give some time to launch
        p.get_dbus_interface()
        duration = float(p.track_info()['length'])+1
        p.pause()
        time.sleep(0.5)
        # do the board setup
        p.prev() # reset the timing
        print('Running video sequence')
        time.sleep(duration)
        # stop recording
        p.quit(None, None, 0)


@defcmd('c', '<command># - command to send to the board')
def cmd_c(ctx: Context, *args: str) -> None:
    if not ctx.board:
        raise Exception('Board not present!')
    ctx.board.ser_write(' '.join(args).encode())
    time.sleep(0.5)
    ctx.board.print_incoming_text()


@defcmd('rand', '<start|stop># - generate random noise')
@in_thread
def cmd_rand(ctx: Context) -> None:
    ctx.params.Source.gen_rand(ctx.params, ctx.callback)


def exec_cmd(cmd: str, ctx: Context, args: List) -> None:
    G_cmds[cmd].func(ctx, *args)


def repl(ctx: Context) -> None:
    while utils.should_run:
        full_cmd = input(">>> ").split(' ') # TODO: escape chars
        if not full_cmd or len(full_cmd) <= 0:
            continue
        cmd = full_cmd[0]  # catch exn
        args = full_cmd[1:]
        if cmd == '':
            pass
        elif cmd in G_cmds:
            exec_cmd(cmd, ctx, args)
        else:
            print('Unknown cmd: {}'.format(cmd))

    for t in G_threads:
        print('waiting for {}'.format(t))
        t.join()
