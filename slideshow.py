from os import listdir
import random
import time

import tkinter as tk
from PIL import Image, ImageTk


class Slideshow(tk.Tk):
    def __init__(self, directory: str, delay: float, duration: float, rest: float, bg: str = '#000000', seed: int = 0):
        tk.Tk.__init__(self)
        #hackish way, essentially makes root window
        #as small as possible but still "focused"
        #enabling us to use the binding on <esc>
        # self.wm_geometry("0x0+0+0")

        self.directory = directory if directory[-1] == '/' else directory + '/'
        self.delay = delay
        self.duration = duration
        self.rest = rest
        self.bg = bg
        self.seed = seed

    def start(self):
        self.bind_all("<Escape>", lambda e: self.destroy())
        self.window = Window(self.bg, self)
        self.window.attributes('-fullscreen', True)
        self.window.attributes('-topmost', True)
        self.cycle()

    def cycle(self):
        self.window.show_blank()
        time.sleep(self.delay)
        files = listdir(self.directory)
        random.Random(self.seed).shuffle(files)
        for iname in files:
            img = Image.open(self.directory+ iname)
            self.window.show_image(img)
            time.sleep(self.duration)
            self.window.show_blank()
            time.sleep(self.rest)
        self.destroy()


class Window(tk.Toplevel):
    def __init__(self, bg, *args, **kwargs):
        tk.Toplevel.__init__(self, *args, **kwargs)

        # remove window decorations
        # self.overrideredirect(True)

        self.bg = bg
        self.label = tk.Label(self)
        self.label.pack(side="top", fill="both", expand=True)


    def show_image(self, image):
        img_w, img_h = image.size
        width = min(self.winfo_screenwidth(), img_w)
        height = min(self.winfo_screenheight(), img_h)
        image.thumbnail((width, height), Image.ANTIALIAS)

        # create new image
        persistent_image = ImageTk.PhotoImage(image)
        self.label.configure(image=persistent_image, bg=self.bg)
        self.update()

    def show_blank(self):
        self.label.configure(image='', bg=self.bg)
        self.update()
