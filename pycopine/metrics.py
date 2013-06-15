from collections import deque
from time import time as now
import threading
 
class HistogramCounter(object):
    ''' Histogram to measure events over time in a rolling time window.

        Example: If 10 buckets are used to measure a time window of one second,
            each buckets covers 1/10 seconds (100ms). A new bucket is added and
            an old one removed every 100ms.
 
        This data structure is optimized for fast updates as well as constant
        and low memory usage. Read performance and memory usage depend on the
        number of buckets used.        
    '''

    def __init__(self, window=1, buckets=10):
        self.window = window
        self.buckets = buckets
        self.dt = window / buckets
        self.bucket_list = deque([0]*buckets, maxlen=buckets)
        self.bucket_value = 0
        self.bucket_lifetime = now() + self.dt 
        self.lock = threading.Lock()

    def increment(self, value=1):
        if now() <= self.bucket_lifetime:
            self.bucket_value += value
            return

        with self.lock:
            age = now() - self.bucket_lifetime
            if age > 0:
                self.bucket_list.append(self.bucket_value)
                self.bucket_value = value
                self.bucket_lifetime += self.dt
                if age > self.dt:
                    skipped = int(age / self.dt)
                    zeros = (0 for _ in range(min(skipped, self.buckets-1)))
                    self.bucket_list.extend(zeros)
                    self.bucket_lifetime += skipped * self.dt

    def sync(self):
        ''' Make sure that the histogram is up to date. This is basically 
            an update that does not change the current bucket. '''
        self.increment(0)

    def freeze(self):
        ''' Return a synced copy of the counter. This can be used to recieve
            statistics while the original counter may be updated in a background
            thread. '''
        obj = self.__class__(self.window, self.buckets)
        with self.lock:
            obj.bucket_list = deque(self.bucket_list, maxlen=self.buckets)
            obj.bucket_value = self.bucket_value
            obj.bucket_lifetime = self.bucket_lifetime
        obj.sync()
        return obj

    def sum(self):
        ''' Return the total number of events during the observed time window.
           (equals: sum(buckets)) '''
        return sum(self.bucket_list)
 
    def rate(self):
        ''' Return the number of events per seconds. If the time window is
           shorter than a second, the rate is interpolated. If it is longer,
           than an average is returned. (equals: sum(buckets) / window) '''
        return self.sum() / self.window
 
    def rate_max(self):
        ''' Return highest event rate (events per second) observed during the
            time window. '''
        return max(self.bucket_list) * self.buckets / self.window
 
    def rate_min(self):
        ''' Return lowest event rate (events per second) observed during the
            time window. '''
        return min(self.bucket_list) * self.buckets / self.window

    def stdev(self):
        ''' Return the standard deviation '''
        c = list(self.bucket_list)
        n = len(c)
        sum_x = sum(c)
        sum_x2 = sum(x**2 for x in c)
        mean = sum_x / n
        stdev = (((sum_x2) / n) - (mean**2))**.5
        return stdev
    
    def median(self, d=.5):
        c = sorted(self.bucket_list)
        t = d*len(c)-1
        tr = t % 1
        return c[int(t)] * tr + c[int(t+1)] * (1-tr)

