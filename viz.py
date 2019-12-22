from typing import *

from collections import deque
import tkinter as tk
from mttkinter import mtTkinter
import time
import random
import numpy as np
from threading import Thread, Lock

import utils
from topology import electrodes

class Panel:
    def update(self):
        raise Exception('Not implemented!')

class VoltageChannel:
    def __init__(self, c, offset, step, H, W, name=None):
        self.H = H
        self.W = W
        self.offset = offset
        self.maxlen = int(W/step)+1
        self.items = deque([])
        self.step = step
        self.last = 0
        self.max = 0.0

        inframe = tk.Frame()
        self.canvas = tk.Canvas(inframe, width=W, height=H,  bg='#dadada')
        self.canvas.pack()
        c.create_window(10, offset, anchor=tk.NW, window=inframe)
        self.name = self.canvas.create_text(20, 10, text=name)


    def update(self, v: float):
        c = self.canvas
        if len(self.items) >= self.maxlen+10:
            for _i in range(10):
                d = self.items.popleft()
                c.delete(d)

        c.move('ln', -self.step, 0)
        color = 'blue'
        a = abs(v)
        half = int(self.H/2)
        if a > self.max:
            self.max = a
            # print('MAX: {:2f}'.format(a))
            color = 'red'
        scaled = -1 if self.max == 0 else -v/self.max # inverted because Y axis is inverted
        pt = int(scaled * (half-1) + half)

        l = c.create_line(self.W-self.step, self.last, self.W, pt, fill=color, tags='ln')
        self.items.append(l)
        self.last = pt

class Voltages(Panel):
    def __init__(self, c, channels, x1, y1, x2, y2):
        self.c = c
        self.channels = [] # type: List[VoltageChannel]
        self.nchannels = len(channels)
        cheight = int(((y2-y1)-10*(self.nchannels+1))/self.nchannels)
        for i in range(self.nchannels):
            offset = y1+10+(cheight+10)*i
            channel = VoltageChannel(
                self.c,
                offset,
                step=5,
                H=cheight,
                W=x2-x1-20, # 10 for gaps on both sides
                name=channels[i]
            )
            self.channels.append(channel)

    def update(self, vec):
        for i in range(self.nchannels):
            self.channels[i].update(vec[i])

class HeadMap(Panel):
    def __init__(self, c, topology, x1, y1, x2, y2):
        self.points = [] # type: List[int]
        self.max = 0.
        self.c = c
        dim = min(abs(x2-x1), abs(y2-y1))
        # nose
        c.create_polygon(
            [
                x1+dim/2-dim/8, y1+dim/10*2,
                x1+dim/2, y1+dim/30,
                x1+dim/2+dim/8, y1+dim/10*2],
            outline='black',
            fill='white',
        )
        # head
        c.create_oval(x1+dim/10, y1+dim/10, x1+dim/10*9, y1+dim/10*9, fill='white')
        x0 = x1+dim/2
        y0 = y1+dim/2
        diameter = int(dim/30)
        for name in topology:
            e = electrodes[name]
            dx,dy = e.x, e.y
            p = c.create_oval(
                x0+dim*dx-diameter,
                y0+dim*dy-diameter,
                x0+dim*dx+diameter,
                y0+dim*dy+diameter,
                fill='white'
            )
            self.points.append(p)
            c.create_text(x0+dim*dx, y0+dim*dy, text=name)

    def update(self, vec):
        for i in range(len(self.points)):
            v = vec[i]
            a = abs(v)
            if a > self.max:
                self.max = a
                # print('MAX: {:2f}'.format(a))
            chanv = 255 - int((1 if self.max == 0 else a/self.max) * 255) % 256
            if v < 0:
                clr = '#{0:02x}{0:02x}ff'.format(chanv)
            else:
                clr = '#ff{0:02x}{0:02x}'.format(chanv)
            self.c.itemconfig(self.points[i], fill=clr)

class FftChannel:
    def __init__(self, c, offset, step, H, W, name, nsamples):
        self.H = H
        self.W = W
        self.offset = offset
        tx = np.fft.fftfreq(nsamples)
        self.mask = tx > 0
        self.x = tx[self.mask]
        self.nfreq = len(self.x)

        inframe = tk.Frame()
        self.canvas = tk.Canvas(inframe, width=W, height=H,  bg='#dadada')
        c.create_window(10, offset, anchor=tk.NW, window=inframe)
        self.name = self.canvas.create_text(20, 10, text=name)

        barw = W/self.nfreq
        self.bars = []  # type: List[Tuple[int, int, int, int]]
        for i in range(self.nfreq):
            l = barw*i
            r = barw*(i+1)
            bid = self.canvas.create_rectangle(l, H-1, r, H, fill='#9999ff')
            self.bars.append((bid,l,r,1)) # 1 as a default value

        self.canvas.pack()

    def update(self, np_array):
        n = len(np_array)
        fft = np.fft.fft(np_array)[self.mask]
        for i in range(self.nfreq):
            bid, l, r, v = self.bars[i]
            nv = int(1000*(np.abs(fft[i]/n)*2))
            if nv != v:
                self.canvas.coords(bid, l, self.H-nv, r, self.H)
                self.bars[i] = (bid, l, r, nv)


class FFT(Panel):

    def __init__(self, c, topology, x1, y1, x2, y2, sampling_rate):
        self.nchannels = len(topology)
        # self.fft_frequencies = int(sampling_rate/2)
        sample_overlap = 0.1
        self.num_samples = int(sampling_rate/2)
        self.sample_period = int(self.num_samples * (1.0 - sample_overlap))
        self.update_countdown = self.num_samples  # first time full
        self.c = c
        self.channels = []
        self.channel_buffers = []

        cheight = int(((y2-y1)-10*(self.nchannels+1))/self.nchannels)
        for i in range(self.nchannels):
            self.channel_buffers.append(deque(maxlen=self.num_samples))
            offset = y1+10+(cheight+10)*i
            channel = FftChannel(
                self.c,
                offset,
                step=5,
                H=cheight,
                W=x2-x1-20, # 10 for gaps on both sides
                name=topology[i],
                nsamples=self.num_samples,
            )
            self.channels.append(channel)

        self.last = time.time()

    def update(self, vec):
        self.update_countdown -= 1
        # if self.update_countdown <=0:
        #     end = time.time()
        #     print('fft update: {}'.format(end - self.last))
        #     self.last = end
        for i in range(self.nchannels):
            self.channel_buffers[i].append(vec[i])
            if self.update_countdown <= 0:
                # if i == 0:
                #     import matplotlib.pyplot as plt
                #     a = np.array(self.channel_buffers[i])
                #     x = np.fft.fftfreq(len(a))
                #     mask = x > 0 # filter out negatives
                #     x = x[mask]
                #     fft = np.fft.fft(a)
                #     fft = fft[mask]

                #     plt.figure(1)
                #     plt.plot(range(len(a)),a)

                #     plt.figure(2)
                #     plt.plot(x,np.abs(fft/len(a))*2) # /n to compensate fft algo, *2 because half is neg and we ignore it but still need to account for it
                #     plt.show()

                self.channels[i].update(np.array(self.channel_buffers[i]))
        # reset counter
        if self.update_countdown <= 0:
            self.update_countdown = self.sample_period


class Gui:
    # NB: need to be careful with high refresh rates
    H=800
    W=1400
    started = False

    def __init__(self, channels: List[str], sampling_rate: int):
        self.vec = None
        self.mtx = Lock()
        self.last_update = 0.
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.nchannels = len(channels)
        self.panels = [] # type: List[Panel]
        self.root = None
        self.c = None

    def update(self):
        if self.root:
            self.root.update_idletasks()
            self.root.update()

    def quit(self):
        if self.root:
            self.update()
            self.root.quit()

    def _on_wheel_up(self, event):
        self.c.yview_scroll(-1, "units")
    def _on_wheel_down(self, event):
        self.c.yview_scroll(1, "units")

    def start(self):
        self.root = tk.Tk()
        self.c = tk.Canvas(self.root, height=self.H, width=self.W, bg='#ddffdd')
        self.c.pack()
        self.root.bind_all("<Button-4>", self._on_wheel_up)
        self.root.bind_all("<Button-5>", self._on_wheel_down)
        self.panels.append(Voltages(
            self.c,
            self.channels,
            x1=0,
            y1=0,
            x2=self.W-self.H,
            y2=self.H
        ))
        # Init Map
        self.panels.append(HeadMap(
            self.c,
            self.channels,
            x1=self.W-self.H,
            y1=0,
            x2=self.W,
            y2=self.H
        ))
        # Init FFT
        # self.panels.append(FFT(
        #     self.c,
        #     self.channels,
        #     x1=0,
        #     y1=self.H,
        #     x2=self.W,
        #     y2=self.H*(len(self.channels)+1)/3, # /n screen per channel
        #     sampling_rate = 250,
        # ))

        self.root.call('wm', 'attributes', '.', '-topmost', '1') # always on fg
        self.root.title('O-BCI')
        self.root.update()
        from threading import Thread
        t = Thread(target=self.refresh_canvas, name = 'gui_refresh_canvas')
        t.start()

    # def start(self):
    #     import sys
    #     from PyQt5.QtWidgets import QWidget, QApplication
    #     from PyQt5.QtGui import QPainter, QColor, QFont
    #     from PyQt5.QtCore import Qt

    def refresh_canvas(self):
        while utils.should_run:
            self.mtx.acquire(blocking=True)
            cvec = self.vec
            self.mtx.release()
            if cvec is None:
                continue
            for p in self.panels:
                p.update(cvec)
            # self.root.update()

    def callback(self, vec):
        # loose visual data for the sake of speed
        if self.mtx.acquire(blocking=False):
            self.vec = vec
            self.mtx.release()
