Pycopine - Fail softly
======================

Pycopine is a latency and fault tolerance library designed to isolate points of
access to remote systems, services and 3rd party libraries, stop cascading
failure and enable resilience in complex distributed systems where failure
is inevitable.

As the copy-pasted text suggests,
it is heavily inspired by `Hystrix <https://github.com/Netflix/Hystrix>`_.

Pycopine requires Python 3.2+, but may be backportet to 2.7 in the future.

Example
-------

.. code-block:: python
    from pycopine import Command
    
    class MyCommand(Command):
    
        def run(self, input):
            return call_remote_api(input)

        def fallback(self, exception):
            return fallback_value

    # Run synchronously
    result = MyCommand('input').result()

    # Run in a background thread pool
    future = MyCommand('input').submit()
    
    # Check for exceptions without try/catch
    if not future.exception():
        result = future.result()


