import logging
import threading
from . import pool

__all__ =  ['Command', 'CommandMeta']
__all__ += ['CommandGroup']
__all__ += ['CommandError', 'CommandSetupError', 'CommandTypeError',
            'CommandNameError', 'CommandCancelledError',
            'CommandIntegrityError', 'CommandExecutorNotFoundError',
            'CommandNotFoundError', 'CommandTimeoutError']

# Possible command states (for internal use only).
NEW       = 'NEW'        # Initialized but not queued
PENDING   = 'PENDING'    # Waiting for a slot in the thread pool
RUNNING   = 'RUNNING'    # Waiting for run() to return

FAILED    = 'FAILED'     # Failed for some reason.
SUCCEDED  = 'SUCCEDED'   # Completed successfully.


class NotImplementedCallable(object):
    def __call__(self, *a, **ka):
        raise NotImplementedError("Method not implemented")
NotImplementedMethod = NotImplementedCallable()

class CommandError(Exception): pass
class CommandSetupError(CommandError): pass
class CommandIntegrityError(CommandError): pass

class CommandTypeError(CommandError, TypeError): pass
class CommandNameError(CommandError): pass

class CommandCancelledError(CommandError): pass
class CommandTimeoutError(CommandError): pass

class CommandExecutorError(CommandError): pass
class CommandExecutorNotFoundError(CommandExecutorError): pass

class CommandNotFoundError(CommandError): pass

class CommandGroup(object):
    __instances = dict()

    @staticmethod
    def clear_all():
        for group in CommandGroup.__instances.values():
            group.clear()
        CommandGroup.__instances.clear()

    def __new__(cls, name='default'):
        if name not in cls.__instances:
            obj = super(CommandGroup, cls).__new__(cls)
            cls.__instances[name] = obj
        return cls.__instances[name]

    def __init__(self, name='default'):
        if 'name' in self.__dict__:
            return
        self.name = name
        self.commands = {}
        self.logger = logging.getLogger(name)
        self.executors = {}
        self.add_executor(pool.Pool('default'))

    def _register(self, CommandClass):
        assert issubclass(CommandClass, Command)
        assert not isinstance(CommandClass.group, CommandGroup)
        assert CommandClass.group == self.name

        name = CommandClass.name or CommandClass.__name__
        if name in self.commands:
            raise CommandNameError("Command names must be unique per group.")
        self.commands[name] = CommandClass
        CommandClass.group  = self
        CommandClass.name = name
        CommandClass.logger = self.logger.getChild(name)

    def get_command(self, name):
        try:
            return self.commands[name]
        except KeyError:
            msg = "Command %r not defined for group %r"
            msg.format(name, self)
            raise CommandNotFoundError(msg)

    def get_executor(self, name):
        try:
            return self.executors[name]
        except KeyError:
            msg = "Command executor %r not defined for group %r"
            msg.format(name, self)
            raise CommandExecutorNotFoundError(msg)

    def add_executor(self, executor):
        n = self.executors.setdefault(executor.name, executor)

    def __contains__(self, other):
        return other in self.commands or other in self.commands.values()

    def clear(self):
        self.commands.clear()



class CommandMeta(type):
    ''' Metaclass for all commands. Ensures that the command is registered
        to a command group. '''

    @classmethod
    def __prepare__(mcl, name, bases):
        return dict()

    def __new__(mcl, name, bases, ns):
        if ns['__module__'] == __name__ and name == 'Command':
            return super().__new__(mcl, name, bases, dict(ns))

        if ns.get('run', NotImplementedMethod) is NotImplementedMethod:
            raise NotImplementedError("Commands must implement run().")

        cls = type.__new__(mcl, name, bases, dict(ns))
        CommandGroup(cls.group)._register(cls)
        return cls



class Command(object, metaclass=CommandMeta):
    ''' Abstract base class for all user defined commands. The base class
        implements the (public) api of concurrent.futures.Future and adds some
        other methods. Instances of this class are called "tasks".

        Subclasses MUST implement :meth:`run` and MAY implement :meth:`fallback`
        and/or :meth:`cleanup`. Additional methods or attributes should be
        avoided or made private (prefixed with two underscores).
    '''

    #: Command group for this command.
    group = 'default'
    #: Executor pool responsible for this command.
    pool  = 'default'
    #: Command name. Defaults to class name.
    name = None

    run = NotImplementedMethod
    fallback = NotImplementedMethod
    def cleanup(self): pass

    def __init__(self, *a, **ka):
        self.arguments = a, ka

        # This event is set if state changes to FINISHED, FAILED or CANCELLED
        self.__completed = threading.Event()

        # The state is protected by a lock
        self.__statelock = threading.Lock()
        self.__state = NEW
        self.__canceled = False

        self.__result = None
        self.__exception = None

        # The fallback lock protects the fallback state, and ensures that
        # the fallback is only invoked once.
        self.__fallback_state = NEW
        self.__fallback_result = None
        self.__fallback_exception = None

        self.__pool = None

    def submit(self):
        ''' Queue the task for execution. Submitting a task multiple times has
            no effect. The return value is the task itself to allow chained
            method calls.
        '''
        with self.__statelock:
            if self.__state == NEW:
                self.__state = PENDING
                self.__pool = self.group.get_executor(self.pool)
                self.__pool.enqueue(self)
        return self

    def cancel(self, exception=None):
        ''' Abandon an unfinished task and immediately wake up all threads
            waiting for the result.

            NEW or PENDING tasks are marked as FAILED and removed from any pool.
            RUNNING tasks are marked as FAILED and the result of the run()
              method is ignored. An implementation of run() that checks for the
              state at interruptible points may be able to exit early.
            SUCCEDED or FAILED tasks are not affected. Calling cancel() on these
              has no effect.

            Return True if the task was canceled in a NEW or PENDING state,
              indicating that the run() method was not invoked.
        '''
        with self.__statelock:
            if self.__state in (NEW, PENDING, RUNNING):
                self.__exception = exception or CommandCancelledError()
                self.__state = FAILED
                self.__canceled = True
                self.__completed.set()
            return self.__pool.dequeue(self) if self.__pool else True

    def wait(self, timeout=None):
        ''' Wait for the task to complete. Return True if the task completed
            within timeout seconds regardless of the result, False otherwise.
        '''
        return self.__completed.wait(timeout)

    def result(self, timeout=None):
        ''' Submit the task and return the result as soon as it is available.
            If the task fails or is canceled early, the fallback() value is
            returned instead.

            If fallback() is not defined, this method re-raises the exception
            that originally caused the failure.

            If no result is available within ``timeout`` seconds, the task is
            canceled with a CommandTimeoutError. If you want to wait a limited
            time but not cancel the task early, use wait() instead.
        '''
        self.submit()

        if self.__state in (PENDING, RUNNING):
            self.__completed.wait(timeout)
            if self.__state in (PENDING, RUNNING):
                self.cancel(CommandTimeoutError())

        if self.__state == SUCCEDED:
            return self.__result

        if self.__try_fallback():
            return self.__fallback_result
        else:
            raise self.__exception

    def exception(self, timeout=None):
        if self.__completed.is_set():
            return self.__exception

        try:
            self.result(timeout)
        except Exception:
            return self.__exception

    def has_result(self):
        ''' Returns True if a result is available. The next call to result()
            will not block and not throw an exception. '''
        return self.is_success() or self.is_fallback()

    def is_success(self):
        ''' Return True if the run() method completed successfully. '''
        return self.__state == SUCCEDED

    def is_failure(self):
        ''' Return True if the run() method failed with an exception or someone
            canceled the task early. '''
        return self.__state == FAILED

    def is_fallback(self):
        ''' Return True if the result originated from the fallback routine. '''
        return self.__fallback_state == SUCCEDED or self.__try_fallback()

    def is_canceled(self):
        ''' Return True if the command was canceled or timed out. '''
        return self.__canceled

    def is_timeout(self):
        ''' Return True if the failure was caused by a timeout. '''
        return isinstance(self.__exception, CommandTimeoutError)

    def is_running(self):
        return self.__state == RUNNING

    def is_completed(self):
        return self.__state in (SUCCEDED, FAILED)

    def __try_fallback(self):
        with self.__statelock:
            if self.__state == FAILED and self.__fallback_state == NEW:
                if self.fallback is NotImplementedMethod:
                    self.__fallback_state = FAILED
                else:
                    try:
                        a, ka = self.arguments
                        self.__fallback_result = self.fallback(*a, **ka)
                        self.__fallback_state = SUCCEDED
                    except Exception as e:
                        self.__fallback_exception = e
                        self.__fallback_state = FAILED
                        self.logger.exception('Fallback failed')
            return self.__fallback_state == SUCCEDED

    def _run(self):

        with self.__statelock:
            if self.__state != PENDING: return
            self.__state = RUNNING

        run_error, result = None, None
        try:
            a, ka = self.arguments
            result = self.run(*a, **ka)
        except Exception as e:
            self.logger.exception("Command failed")
            run_error = e

        with self.__statelock:
            if self.__state == RUNNING:
                if run_error:
                    self.__state = FAILED
                    self.__exception = run_error
                else:
                    self.__state = SUCCEDED
                    self.__result = result
                self.__completed.set()
            elif self.__state == FAILED:
                pass # Canceled while running

        try:
            self.cleanup()
        except Exception:
            self.logger.exception("Command cleanup failed.")

