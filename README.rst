Pycopine - Handle with Care
===========================

Pycopine is a latency and fault tolerance library designed to isolate points of
access to remote systems, services and 3rd party libraries, stop cascading
failure and enable resilience in complex distributed systems where failure
is inevitable.

As this copy-pasted text suggests, pycopine is heavily inspired by
`Hystrix <https://github.com/Netflix/Hystrix>`_. 

Prerequisites
-------------

Pycopine requires Python 3.2+, but may be backportet to 2.7 in the future.

Installation
------------

Pycopine is not released yet.

(Planned) Features
------------------

* Detect and report failing services.
* Short-circuit services that fail on high load to help them recover.
* Monitor failure rates and performance metrics to detect bottlenecks.
* Manage thread pool and queue sizes on demand, at runtime, from everywhere.
* ... (more to come)

Example
-------

Lets say we want to speak to a remote service that is slow, unreliable or both:

.. code-block:: python

    import time
    import random
    
    def crappy_service(input):
        ''' The most useless piece of code ever.'''
        time.sleep(5)
        if 'OK' != random.choice(['OK', 'OK', 'f**ck']):
            raise RuntimeError('We broke something.')
        return input

You could throw lots of threads and try/except clauses at the problem and hope
to not break the internet. Or you could use pycopine:

.. code-block:: python

    from pycopine import Command
    
    class MyCommand(Command):
        ''' Does nothing with the input, but with style. '''
    
        def run(self, input):
            return crappy_service(input)

        def fallback(self, input):
            return input
    
    # Run and wait for the result
    result = MyCommand('input').result()
    
    # Give up after 2 seconds
    result = MyCommand('input').result(timeout=2)
    
    # Fire and forget
    MyCommand('input').submit()
    
    # Do stuff in parallel
    foo = MyCommand('input_a').submit()
    bar = MyCommand('input_b').submit()
    results = [foo.result(), bar.result()]
    
    # Change your mind midway through
    foobar = MyCommand('input').submit()
    if foobar.wait(timeout=2):
        result = foobar.reault()
    else:
        foobar.cancel(RuntimeError('No time for this sh**t'))


