from time import clock
import threading

class RRBucketCounter(list):
    def __init__(self, size):
        for x in range(size):
            self.append(0)
        self.last_bucket = int((clock()%1)*len(self))
        self.lock = threading.Lock()
    
    def increment(self, n=1):
        bucket = int((clock()%1)*len(self))
        self[bucket] += n
        with self.lock:
            while self.last_bucket != bucket:
                self[self.last_bucket] = 0
                self.last_bucket = (self.last_bucket + 1) % len(self)
        
    def value(self):
        return sum(self)

    def clear(self):
        for i in range(len(self)):
            self[i] = 0

