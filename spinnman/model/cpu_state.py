from enum import Enum


class CPUState(Enum):
    """ SARK CPU States
    """
    DEAD = 0
    POWERED_DOWN = 1
    RUN_TIME_EXCEPTION = 2
    WATCHDOG = 3
    INITIALISING = 4
    READY = 5
    C_MAIN = 6
    RUNNING = 7
    SYNC0 = 8
    SYNC1 = 9
    PAUSED = 10
    FINSHED = 11
    IDLE = 15
    
    def __init__(self, value, doc=""):
        self._value_ = value
        self.__doc__ = doc
