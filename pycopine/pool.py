import time
import threading

class Pool(object):
    __instances = dict()

    def __new__(cls, name='default'):
        if name not in cls.__instances:
            obj = super(CommandGroup, cls).__new__(cls)
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
        self.qlock = threading.Condition()

    def get_queue_size(self):
        ''' Return the number of jobs waiting in the queue. '''
        return len(self.queue)

    def get_queue_space(self):
        ''' Return the number of available slots in the pool queue '''
        return self.max_queue_size - len(self.queue)

    def dequeue(self, command):
        with self.qlock:
            self.queue.remove(command)
    
    def enqueue(self, command):
        with self.qlock:
            if self._shutdown:
                raise RuntimeError('Queue closed')
            if len(self.queue) >= self.max_queue_size:
                raise RuntimeError('Queue full')
            self.queue.append(item)
            if len(self.threads) < self.max_pool_size:
                thread = threading.Thread(target=self._runloop)
                thread.start()
                self.threads.append(thread)
            self.qlock.notify()

    def _run_loop(self):
        current_thread = threading.current_thread()
        while True:
            try:
                with self.qlock:
                    if not self.queue:
                        self.qlock.wait(self.max_worker_idle)
                    if self._shutdown:
                        break
                    if not self.queue:
                        break
                    command = self.queue.pop(0)
                try:
                    self.running.append(command)
                    command._run()
                finally:
                    self.running.remove(command)
            finally:
                self.threads.remove(current_thread)

    def shutdown(self):
        with self.qlock:
            self._shutdown = True
            self.qlock.notifyAll()

    @classmethod
    def shutdown_all(cls):
        for pool in cls.__instances.items():
            pool.shutdown()

import atexit
atexit.register(Pool.shutdown_all)
