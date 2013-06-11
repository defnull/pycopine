from time import clock
import threading

class RRBucketCounter(list):
    def __init__(self, millis=1000, buckets=10):
        self.buckets = buckets
        self.clockfunc = lambda: int(clock()*buckets*millis/1000)
        self.last_ts = 0
        self.lock = threading.Lock()
    
    def increment(self, n=1):
        with self.lock:
            t = self.clockfunc()
            off = t - len(self.buckets)
            while self and self[0][0] < off:
                self.pop(0)
            if self and self[-1][0] == t:
                self[-1][1] += n
            else:
                self.append([t,n])
        
    def value(self):
        return sum(v, for t,v in self)

    def clear(self):
        del self[:]

