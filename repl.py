from typing import List, Optional, Any, Callable, Dict, Union, TypeVar, cast
T = TypeVar('T')
TFun = TypeVar('TFun', bound=Callable[..., Any])
Args = List[str]

from multiprocessing import Process
import os
import random
import sys
import time
import traceback
from threading import Thread
from collections import namedtuple

from base import Session
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
def cmd_eval(ssn: Session, *s: str) -> None:
    expr = ' '.join(s)
    exec(expr)


@defcmd(['exit', 'q'], '# - stop everything and exit repl')
def cmd_exit(ssn: Session) -> None:
    utils.should_run = False
    cmd_sstop(ssn) #  stop stream just in case
    if ssn.gui:
        ssn.gui.stop()


@defcmd(['help', 'h'], '[cmd]# - show help')
def cmd_help(ssn: Session, cmd_name: str = None) -> None:
    def fmthelp(cmd: str, v: Cmd) -> str:
        opts, doc = v.help.split('#', maxsplit=1)
        return'{:15} {:30}\t{}'.format(cmd, opts, doc)

    if not cmd_name:
        for c, v in G_cmds.items():
            print(fmthelp(c, v))
    else:
        print(fmthelp(cmd_name, G_cmds[cmd_name]))

@defcmd('sleep', '<seconds># - pause')
def cmd_sleep(ssn: Session, duration: float) -> None:
    time.sleep(float(duration))

@defcmd('gui', '<start|stop># - start/stop GUI; default: start')
def cmd_gui(ssn: Session, action: str = 'start') -> None:
    if ssn.gui is not None and action == 'start':
        raise Exception('GUI already runnng')
    elif ssn.gui is not None and action == 'stop':
        ssn.gui.stop()
        ssn.gui = None
    elif ssn.gui is None and action == 'start':
        gui = SubprocessInterface(TkInterGui, ssn.params)
        ssn.gui = gui
        ssn.add_callback(gui.callback)
    elif ssn.gui is None and action == 'stop':
        raise Exception('No GUI to stop')
    else:
        raise Exception('Expected start|stop')


@defcmd('csv', '<csv># - replay preprocessed csv file')
@in_thread
def cmd_csv(ssn: Session, fname: str) -> None:
    import csv
    with open(fname, 'r') as inp:
        for l in csv.reader(inp):
            if not utils.should_run:
                break
            ssn.callback(list(map(float,l)))
            time.sleep(1.0/ssn.params.sampling_rate) # TODO: save srate in file


@defcmd('connect', '[port]# - connect to board')
def cmd_connect(ssn: Session, port: str = '/dev/ttyUSB0') -> None:
    ssn.board = ssn.params.Source.setup(ssn.params, port)


@defcmd('import', '[fname]# - import EEG data; default: SD card file name')
def cmd_import(ssn: Session, fname: Optional[str] = None) -> None:
    ssn.import_data(fname)


@defcmd('save_session', '[fname]# - save session')
def cmd_save_session(ssn: Session, fname: Optional[str] = None) -> None:
    ssn.save(fname)

@defcmd('plot_session', '# - display session graph')
def cmd_plot_session(ssn: Session) -> None:
    if ssn.data:
        ssn.data.plot(
            n_channels = ssn.params.nchannels,
            duration=ssn.tstop - ssn.tstart,
            show=True,
            block=True,
            scalings = 'auto'
        )


@defcmd('record_local', '<file># - open a new file to save data to')
def cmd_record_local(ssn: Session, fname: str) -> None:
    from utils import open_record

    writer = open_record(name=fname, srate=ssn.params.sampling_rate)
    ssn.add_callback(writer)


@defcmd('record_sd', '<mode:ASFGHJKLa># - open a new file on SD card')
def cmd_record(ssn: Session, mode: str) -> None:
    if mode not in 'ASFGHJKLa':
        raise ArgError('expected mode: A|S|F|G|H|J|K|L|a')
    if not ssn.board:
        raise Exception('Board not present!')
    ssn.board.ser_write(mode.encode())
    time.sleep(0.5)
    if ssn.board.ser.inWaiting():
        line = ''
        c = ''
        while '$$$' not in line:
            c = ssn.board.ser.read().decode('utf-8', errors='replace')
            line += c
        b,e = line.find('OBCI'),line.find('.TXT')
        if b < 0 or e < 0:
            raise Exception('No file open confirmation: {}'.format(line))
        print(line)
        ssn.sd_out_file = line[b:e+4]
    else:
        raise Exception('No answer')


@defcmd('sstart', '# - start streaming from the board')
@in_thread
def cmd_sstart(ssn: Session) -> None:
    if ssn.board and not ssn.board.streaming:
        ssn.start()
        ssn.board.start_streaming(ssn.callback)
    else:
        raise Exception('No board connected')


@defcmd('sstop', '# - stop stream')
def cmd_sstop(ssn: Session) -> None:
    if ssn.board and ssn.board.streaming:
        ssn.board.stop()
    ssn.stop()


@defcmd('video', '<file># - start video with data collection; board should be preconfigured')
def cmd_vstart(ssn: Session, inp_file: str) -> None:
    import subprocess
    from vlc_ctrl.player import Player

    if not inp_file or len(inp_file) <= 0:
        raise ArgError('Video file name expected')

    input('Press Enter to start...')
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


@defcmd('slideshow', '<dir> <delay> <duration> <rest> [bg]# - start presentation of pictures in directory; board should be preconfigured')
def cmd_pstart(ssn: Session, dirname: str, delay: float, duration: float, rest: float, bg: str = '#000000') -> None:
    from slideshow import Slideshow

    dirname, delay, duration, rest, bg = (dirname, float(delay), float(duration), float(rest), bg)
    def f(dir: str, delay: float, duration: float, rest: float, bg: str, seed: int) -> None:
        oldstd = sys.stderr
        with open(os.devnull, "w") as out:
            sys.stderr = out
            slideshow = Slideshow(dir, delay, duration, rest, bg, seed)
            slideshow.start()
        sys.stderr = oldstd

    # generate annotations
    files = [f.split('.')[0] for f in os.listdir(dirname)]
    random.Random(ssn.random_seed).shuffle(files)
    onset = [delay+i*(duration + rest) for i in range(len(files))]
    durations = [duration] * len(files)
    ssn.annotations['onset'] = ssn.annotations['onset'] + onset
    ssn.annotations['duration'] = ssn.annotations['duration'] + durations
    ssn.annotations['description'] = ssn.annotations['description'] + files

    # Confirmation
    print ('Slideshow:\n  Files: {} ({})\n  Estimated duration: {}\n'.format(
        dirname, len(files),
        delay+len(files)*(duration+rest)
    ))
    input('Press Enter to start...')
    # start recording
    cmd_sstart(ssn)

    p = Process(target=f, args=(dirname, delay, duration, rest, bg, ssn.random_seed))
    p.start()
    p.join()

    # stop recording
    cmd_sstop(ssn)

@defcmd('c', '<command># - command to send to the board')
def cmd_c(ssn: Session, *args: str) -> None:
    if not ssn.board:
        raise Exception('Board not present!')
    ssn.board.ser_write(' '.join(args).encode())
    time.sleep(0.5)
    ssn.board.print_incoming_text()


@defcmd('rand', '<start|stop># - generate random noise')
@in_thread
def cmd_rand(ssn: Session) -> None:
    ssn.params.Source.gen_rand(ssn.params, ssn.callback)


def exec_cmd(cmd: str, ssn: Session, args: List) -> None:
    G_cmds[cmd].func(ssn, *args)


def repl(ssn: Session) -> None:
    while utils.should_run:
        full_cmd = input(">>> ").split(' ') # TODO: escape chars
        if not full_cmd or len(full_cmd) <= 0:
            continue
        cmd = full_cmd[0]  # catch exn
        args = full_cmd[1:]
        if cmd == '':
            pass
        elif cmd in G_cmds:
            exec_cmd(cmd, ssn, args)
        else:
            print('Unknown cmd: {}'.format(cmd))

    for t in G_threads:
        print('waiting for {}'.format(t))
        t.join()
