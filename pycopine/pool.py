import time
import threading
import atexit

__all__ = ['Pool']

class Pool(object):
    __instances = dict()

    def __new__(cls, name='default'):
        if name not in cls.__instances:
            obj = super(cls, cls).__new__(cls)
            cls.__instances[name] = obj
        return cls.__instances[name]

    #: Maximum number of commands in queue
    max_queue_size = 10
    #: Maximum number of commands running at the same time
    max_pool_size = 10
    #: Idle worker threads are terminated after this timeout.
    max_worker_idle = 60

    def __init__(self, name='default'):
        if 'name' in self.__dict__:
            return
        self.name = name
        self._shutdown = False
        self.queue    = []
        self.running  = []
        self.threads  = []
        self.qlock = threading.Condition(threading.Lock())
        atexit.register(self.shutdown)

    def get_queue_size(self):
        ''' Return the number of jobs waiting in the queue. '''
        return len(self.queue)

    def get_queue_space(self):
        ''' Return the number of available slots in the pool queue '''
        return self.max_queue_size - len(self.queue)

    def dequeue(self, command):
        with self.qlock:
            if command in self.queue:
                self.queue.remove(command)
    
    def enqueue(self, command):
        with self.qlock:
            if self._shutdown:
                raise RuntimeError('Pool is closed')
            if len(self.queue) >= self.max_queue_size:
                raise RuntimeError('Queue full')
            self.queue.append(command)
            if len(self.threads) < self.max_pool_size:
                thread = threading.Thread(target=self._run_loop)
                thread.daemon = True
                self.threads.append(thread)
                thread.start()
            self.qlock.notify()

    def _run_loop(self):
        current_thread = threading.current_thread()
        try:
            while True:
                with self.qlock:
                    if self._shutdown:
                        break
                    if not self.queue:
                        self.qlock.wait(self.max_worker_idle)
                    if self._shutdown or not self.queue:
                        break
                    command = self.queue.pop(0)
                try:
                    self.running.append(command)
                    command._run()
                finally:
                    self.running.remove(command)
        finally:
            self.threads.remove(current_thread)

    def shutdown(self, block=True):
        with self.qlock:
            self._shutdown = True
            self.qlock.notify_all()
        if block:
            for t in self.threads[:]:
                t.join()


