from time import time as now
import itertools
import queue
import atexit
import sys
import threading

__all__ = ['sink', 'BaseSink', 'EventManager']

def _stderr(msg):
    sys.stderr.write(msg.strip()+'\n')


class BaseSink(object):
    def consume(self, event):
        raise NotImplementedError()

    def __eq__(self, other):
        return self.consume is other.consume


class FuncSink(object):
    def __init__(self, func):
        self.consume = func

    def __repr__(self):
        return '<FuncSink of {}>'.format(self.consume)


def sink(func):
    ''' Decorator to register a function to the root event manager as a FuncSink
    '''
    sink = FuncSink(func)
    root.add_sink(sink)
    return sink

_getid = iter(itertools.count()).__next__

class EventManager(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.sinks = []
        self._sink_callbacks = []
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._sink_loop)
        self.thread.daemon = True
        self.thread.start()
    
    def add_sink(self, sink):
        with self.lock:
            if sink in self.sinks: return
            self.sinks.append(sink)
            self._sink_callbacks = [s.consume for s in self.sinks]
        return sink

    def clear(self):
        with self.lock:
            del self.sinks[:]
            del self._sink_callbacks[:]

    def emit(self, _name, **event):
        event['_ts'] = now()
        event['name'] = _name
        with self.lock:
            event['_id'] = _getid()
        self.queue.put(event)

    def consume(self, event):
        self.queue.put(event)

    def _remove_sink_after_error(self, consume_callback, e):
        sink = None
        with self.lock:
            for sink in list(self.sinks):
                if sink.consume is consume_callback:
                    self.sinks.remove(sink)
                    self._sink_callbacks = [s.consume for s in self.sinks]
                    break
        if sink:
            self.emit('pool.sinkfailed', sink=repr(sink), error=repr(e))

    def _sink_loop(self):
        while True:
            event = self.queue.get()
            if event is None:
                break
            for consume in self._sink_callbacks:
                try:
                    consume(event)
                except Exception as e:
                    self._remove_sink_after_error(consume, e)
    
    def shutdown(self):
        self.queue.put(None)
        self.thread.join()

root = EventManager()
emit = root.emit
        
        
