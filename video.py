import numpy as np
import cv2

class Video:
    def __init__(self, fname: str):
        self.video = cv2.VideoCapture(fname)
        fps = self.video.get(cv2.CAP_PROP_FPS)
        self.wait = int(1000.0 / fps)

    def run(self) -> None:
        if self.video is None:
            return
        while(self.video.isOpened()):
            ret, frame = self.video.read()
            if ret == True:
                fr = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)
                cv2.imshow('frame', fr)
                # & 0xFF is required for a 64-bit system
                if cv2.waitKey(self.wait) & 0xFF == ord('q'):
                    break
            else:
                break
        self.video.release()
        self.video = None
        cv2.destroyAllWindows()
