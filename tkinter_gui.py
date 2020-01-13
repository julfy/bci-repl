from typing import *

from collections import deque
from mttkinter import mtTkinter
import numpy as np
import time
import tkinter as tk
from sortedcontainers import SortedList

from topology import electrodes
from interfaces import Parameters
import utils


class Panel:
    def update(self, v: Any) -> None:
        raise Exception('Not implemented!')

class VoltageChannel:
    def __init__(self, c, offset, step, H, W, name=None):
        self.H = H
        self.W = W
        self.offset = offset
        self.maxlen = int(W/step)+1
        self.items = deque([]) # type: ignore
        self.step = step
        self.last_pt = 0
        self.amp_hist = deque([100.0], maxlen = 10)
        self.amp = 0.0
        self.avg = 0.0
        self.name = name

        self.avg_amp_period = utils.period_function(0.3, lambda: True)
        self.redraw_period = utils.period_function(1.0/100, lambda: True)

        inframe = tk.Frame()
        self.sub_canvas = tk.Canvas(inframe, width=W, height=H,  bg='#dadada')
        self.sub_canvas.pack()
        c.create_window(10, offset, anchor=tk.NW, window=inframe)
        self.sub_canvas.create_line(0, H/2, W, H/2, fill='#aaaaaa') # middle
        self.header = self.sub_canvas.create_text(20, 10, text=self.name)

    def _update_header(self, avg, amplitude):
        self.sub_canvas.delete(self.header)
        self.header = self.sub_canvas.create_text(5, 5, anchor='nw', text='{}: {} +-{}'.format(self.name,  int(avg), int(amplitude)))

    def _get_amp_avg(self):
        amp = 0.0
        avg = 0.0
        l = len(self.items)
        for _, a in self.items:
            avg += a
        avg = avg / l if l > 0 else 0

        for _, a in self.items:
            k = abs(avg - a)
            if amp < k:
                amp = k
        self.amp_hist.append(amp * 1.3 if amp > 100 else 100) # a bit of margin
        self.amp = sum(self.amp_hist)/len(self.amp_hist)
        self.avg = avg

    def update(self, v: float) -> None:
        c = self.sub_canvas
        if len(self.items) >= self.maxlen:
            for _i in range(10):
                d, _ = self.items.popleft()
                c.delete(d)

        c.move('ln', -self.step, 0)

        middle = int(self.H/2)
        if self.period():
            self._get_amp_avg()
            self._update_header(self.avg, self.amp)

        scaled = 0 if self.amp == 0 else -(v-self.avg)/self.amp # inverted because Y axis is inverted
        pt = int(scaled * (middle-1) + middle)
        l = c.create_line(self.W-self.step, self.last_pt, self.W, pt, fill='blue', tags='ln')

        self.items.append((l, v))
        self.last_pt = pt

class Voltages(Panel):
    def __init__(self, c, topology, x1, y1, x2, y2):
        self.c = c
        self.channels = [] # type: List[VoltageChannel]
        self.nchannels = len(topology)
        cheight = int(((y2-y1)-10*(self.nchannels+1))/self.nchannels)
        for i in range(self.nchannels):
            offset = y1+10+(cheight+10)*i
            channel = VoltageChannel(
                self.c,
                offset,
                step=5,
                H=cheight,
                W=x2-x1-20, # 10 for gaps on both sides
                name=topology[i]
            )
            self.channels.append(channel)

        self.period = utils.period_function(1.0, lambda: True)

    def update(self, vec: Sequence[float]) -> None:
        if self.period():
            print(vec)
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

    def update(self, vec: Sequence[float]) -> None:
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

    def update(self, vec: np.array) -> None:
        n = len(vec)
        fft = np.fft.fft(vec)[self.mask]
        for i in range(self.nfreq):
            bid, l, r, v = self.bars[i]
            nv = int(100*(np.abs(fft[i]/n)*2))
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
        self.channel_buffers = [] # type: ignore

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

    def update(self, vec: Sequence[float]) -> None:
        self.update_countdown -= 1
        # if self.update_countdown <=0:
        #     end = time.time()
        #     print('fft update: {}'.format(end - self.last))
        #     self.last = end
        for i in range(self.nchannels):
            self.channel_buffers[i].append(vec[i])
            if self.update_countdown <= 0:
                self.channels[i].update(np.array(self.channel_buffers[i]))
        # reset counter
        if self.update_countdown <= 0:
            self.update_countdown = self.sample_period


class TkInterGui:
    # NB: need to be careful with high refresh rates
    H=800
    W=1400
    started = False

    def __init__(self, topology: List[str], sampling_rate: int):
        self.last_update = 0.
        self.sampling_rate = sampling_rate
        self.topology = topology
        self.nchannels = len(topology)
        self.panels = [] # type: List[Panel]
        self.root = tk.Tk()
        self.c = tk.Canvas(self.root, height=self.H, width=self.W, bg='#999999')

        self.c.pack()
        self.root.bind_all("<Button-4>", self._on_wheel_up)
        self.root.bind_all("<Button-5>", self._on_wheel_down)
        # Init Squiglies
        self.panels.append(Voltages(
            self.c,
            self.topology,
            x1=0,
            y1=0,
            x2=self.W-self.H,
            y2=self.H
        ))
        # Init Map
        self.panels.append(HeadMap(
            self.c,
            self.topology,
            x1=self.W-self.H,
            y1=0,
            x2=self.W,
            y2=self.H
        ))
        # Init FFT
        # self.panels.append(FFT(
        #     self.c,
        #     self.topology,
        #     x1=0,
        #     y1=self.H,
        #     x2=self.W,
        #     y2=self.H*(len(self.topology)+1)/3, # /n screen per channel
        #     sampling_rate = self.sampling_rate,
        # ))
        self.root.call('wm', 'attributes', '.', '-topmost', '1') # always on fg
        self.root.title('O-BCI GUI')
        self.root.update()

    def _on_wheel_up(self, _event: Any) -> None:
        self.c.yview_scroll(-1, "units")

    def _on_wheel_down(self, _event: Any) -> None:
        self.c.yview_scroll(1, "units")

    def update(self) -> None:
        self.root.update_idletasks()
        self.root.update()

    def stop(self) -> None:
        self.update()
        self.root.destroy()

    def consume(self, vec: Sequence[float]) -> None:
        for p in self.panels:
            p.update(vec)
        self.root.update()

    @classmethod
    def get_params(self, params: Parameters) -> Dict[str, Any]:
        return {
            'topology': params.electrode_topology,
            'sampling_rate': params.sampling_rate
        }
