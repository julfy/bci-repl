from typing import *

from collections import deque
import tkinter as tk
from mttkinter import mtTkinter
import time
import random

from topology import coords

# inframe = tk.Frame()
# innercanvas = tk.Canvas(inframe, width=100, height=100, bg='green')
# innercanvas.pack()
# c.create_window(200, 200, window=inframe)
# p=c.coords(ol)

class Channel:
    def __init__(self, c, offset, step, H, W, name=None):
        self.H = H
        self.W = W
        self.offset = offset
        self.maxlen = int(W/step)+1
        self.items = deque([]) # type: Deque[int]
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
        if len(self.items) >= self.maxlen:
            d = self.items.popleft()
            c.delete(d)
        c.move('ln', -self.step, 0)
        # TODO: color coded style?
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

class Map:
    def __init__(self, c, topology, x1, y1, x2, y2):
        self.points = []
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
            # print('{} {} {}'.format(n, dx, y0+dim*dy))
            dx,dy = coords[name]
            p = c.create_oval(
                x0+dim*dx-diameter,
                y0+dim*dy-diameter,
                x0+dim*dx+diameter,
                y0+dim*dy+diameter,
                fill='white'
            )
            self.points.append(p)
            c.create_text(x0+dim*dx, y0+dim*dy, text=name)

    def update_points(self, vec):
        for i in range(len(self.points)):
            v = vec[i]
            a = abs(v)
            if a > self.max:
                self.max = a
                # print('MAX: {:2f}'.format(a))
            chanv = 255 - int((1 if self.max == 0 else a/self.max) * 255) % 256
            if v < 0:
                clr = '#{:02x}{:02x}ff'.format(chanv,chanv)
            else:
                clr = '#ff{:02x}{:02x}'.format(chanv,chanv)
            self.c.itemconfig(self.points[i], fill=clr)


class Gui:
    # NB: need to be careful with high refresh rates
    H=600
    W=1400
    started = False

    def __init__(self, channel_names: List[str]):
        self.root = tk.Tk()
        self.nchannels = len(channel_names)
        self.channels = [] # type: List[Channel]
        self.c = tk.Canvas(self.root, height=self.H, width=self.W, bg='#ddffdd')
        self.c.pack()
        # Init EEG
        cheight = int((self.H-10*(self.nchannels+1))/self.nchannels)
        for i in range(self.nchannels):
            offset = 10+(cheight+10)*i
            channel = Channel(
                self.c,
                offset,
                step=5,
                H=cheight,
                W=self.W-self.H-20, # 10 for gaps on both sides
                name=channel_names[i]
            )
            self.channels.append(channel)
        # Init Map
        self.map = Map(self.c, channel_names, x1=self.W-self.H, y1=0, x2=self.W, y2=self.H)

    def start(self):
        self.root.call('wm', 'attributes', '.', '-topmost', '1')
        self.root.mainloop()

    def callback(self, vec : List[float]):
        for i in range(self.nchannels):
            self.channels[i].update(vec[i])
        self.map.update_points(vec)
