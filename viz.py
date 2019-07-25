from typing import *

from collections import deque
import tkinter as tk
from mttkinter import mtTkinter
import time
import random

# inframe = tk.Frame()
# innercanvas = tk.Canvas(inframe, width=100, height=100, bg='green')
# innercanvas.pack()
# c.create_window(200, 200, window=inframe)
# p=c.coords(ol)

class Channel:
    def __init__(self, c, offset, color, step, H, W):
        self.H = H
        self.W = W
        self.offset = offset
        self.color = color
        self.maxlen = int(W/step)+1
        self.items = deque([]) # type: Deque[int]
        self.step = step
        self.last = 0

        inframe = tk.Frame()
        self.canvas = tk.Canvas(inframe, width=W, height=H,  bg='#aaaaaa')
        self.canvas.pack()
        c.create_window(0, offset, anchor=tk.NW, window=inframe)

    def update(self, v):
        c = self.canvas
        if len(self.items) >= self.maxlen:
            d = self.items.popleft()
            c.delete(d)
        c.move(tk.ALL, -self.step, 0)
        l = c.create_line(self.W-self.step, self.last, self.W, v, fill=self.color)
        self.items.append(l)
        self.last = v

class Gui:
    # NB: neeer to be carefull with high refresh rates
    H=1000
    W=1000
    started = False

    def __init__(self, nchannels):
        self.root = tk.Tk()
        self.nchannels = nchannels
        self.channels = [] # type: List[Channel]

    def start(self):
        if self.started:
            return
        self.started = True
        self.c = tk.Canvas(self.root, height=self.H, width=self.W, bg='#aaffaa')
        cheight = int((self.H-10*(self.nchannels+1))/self.nchannels)
        for i in range(self.nchannels):
            offset = 10+(cheight+10)*i
            self.channels.append(Channel(self.c, offset, 'red', step=5, H=cheight, W=self.W-5))
        self.c.pack()
        self.root.call('wm', 'attributes', '.', '-topmost', '1')
        self.root.mainloop()

    def callback(self, vec : List[float]):
        for i in range(self.nchannels):
            self.channels[i].update(vec[i])
