import Quartz
import Quartz.CoreGraphics as CG
import time
import math

class MacMouse:
    def __init__(self, ema_alpha=0.3):
        """
        Interfaccia super-veloce per mouse su macOS.
        Usa Exponential Moving Average (EMA) per evitare il jitter.
        """
        self.screen_width = CG.CGDisplayPixelsWide(CG.CGMainDisplayID())
        self.screen_height = CG.CGDisplayPixelsHigh(CG.CGMainDisplayID())
        
        # Filtro EMA per stabilizzare il puntatore
        self.alpha = ema_alpha
        self.current_x = self.screen_width / 2
        self.current_y = self.screen_height / 2
        
        self.is_left_down = False

    def move_to(self, target_x, target_y):
        """
        Sposta fluidamente il mouse utilizzando il filtro EMA
        """
        # Applica EMA
        self.current_x = self.alpha * target_x + (1 - self.alpha) * self.current_x
        self.current_y = self.alpha * target_y + (1 - self.alpha) * self.current_y
        
        # Bound limits
        self.current_x = max(0, min(self.screen_width, self.current_x))
        self.current_y = max(0, min(self.screen_height, self.current_y))

        # Emetti evento macOS
        event = CG.CGEventCreateMouseEvent(
            None, 
            CG.kCGEventMouseMoved, 
            (self.current_x, self.current_y), 
            CG.kCGMouseButtonLeft
        )
        CG.CGEventPost(CG.kCGHIDEventTap, event)

    def left_click(self):
        """Esegue un click sinistro istantaneo"""
        pos = (self.current_x, self.current_y)
        
        # Mouse Down
        down_event = CG.CGEventCreateMouseEvent(None, CG.kCGEventLeftMouseDown, pos, CG.kCGMouseButtonLeft)
        CG.CGEventPost(CG.kCGHIDEventTap, down_event)
        
        # Mouse Up
        up_event = CG.CGEventCreateMouseEvent(None, CG.kCGEventLeftMouseUp, pos, CG.kCGMouseButtonLeft)
        CG.CGEventPost(CG.kCGHIDEventTap, up_event)
        
        # Logging e delay per evitare doppi click accidentali per frames multipli
        print("Left Click!")
        
    def right_click(self):
        """Esegue un click destro istantaneo"""
        pos = (self.current_x, self.current_y)
        down_event = CG.CGEventCreateMouseEvent(None, CG.kCGEventRightMouseDown, pos, CG.kCGMouseButtonRight)
        CG.CGEventPost(CG.kCGHIDEventTap, down_event)
        
        up_event = CG.CGEventCreateMouseEvent(None, CG.kCGEventRightMouseUp, pos, CG.kCGMouseButtonRight)
        CG.CGEventPost(CG.kCGHIDEventTap, up_event)
        print("Right Click!")
