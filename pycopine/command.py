import concurrent.futures
import logging
import threading

__all__ =  ['Command', 'CommandMeta']
__all__ += ['CommandGroup']
__all__ += ['CommandError', 'CommandSetupError', 'CommandTypeError',
            'CommandNameError', 'CommandCancelledError',
            'CommandIntegrityError', 'CommandExecutorNotFoundError',
            'CommandNotFoundError', 'CommandTimeoutError']

# Possible command states (for internal use only).
NEW       = 'NEW'        # Initialized but not queued
PENDING   = 'PENDING'    # Waiting for a spot in the thread pool
RUNNING   = 'RUNNING'    # Running
CANCELLED = 'CANCELLED'  # Stopped before run() finished
FAILED    = 'FAILED'     # Stopped because of an exception in run()
FINISHED  = 'FINISHED'   # Completed successfully


class NotImplementedCallable(object):
    def __call__(self, *a, **ka):
        raise NotImplementedError("Method not implemented")
NotImplementedMethod = NotImplementedCallable()

class CommandError(Exception): pass
class CommandSetupError(CommandError): pass
class CommandIntegrityError(CommandError): pass

class CommandTypeError(CommandError, TypeError): pass
class CommandNameError(CommandError): pass

class CommandCancelledError(concurrent.futures.CancelledError, CommandError): pass
class CommandTimeoutError(concurrent.futures.TimeoutError, CommandError): pass

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
        self.add_executor('default', concurrent.futures.ThreadPoolExecutor(4))

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

    def add_executor(self, name, executor):
        n = self.executors.setdefault(name, executor)

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
    ''' Base class for all user defined commands. The base class implements the
        (public) api of concurrent.futures.Future and adds some other methods.

        Subclasses MUST implement run() and MAY implement fallback() and/or
        cleanup(). Additional methods or attributes should be avoided or
        made private (prefixed with `__`).
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
        self._completed = threading.Event()

        # The state is protected by a lock
        self._statelock = threading.Lock()
        self._state = NEW

        self._result = None
        self._exception = None

        # The fallback lock protects the fallback state, and ensures that
        # the fallback is only invoked once.
        self._fallback_lock = threading.Lock()
        self._fallback_state = NEW
        self._fallback_result = None
        self._fallback_exception = None

        self.__future = None

    def submit(self):
        ''' Queue the call for execution. '''
        if self._state == CANCELLED:
            raise CommandCancelledError("Submit on cancelled command.")
        if self._state != NEW:
            raise CommandIntegrityError("Submitted twice")
        self._submit()
        return self

    def _submit(self):
        with self._statelock:
            if self._state == NEW:
                self._state = PENDING
                self.__future = self.group.get_executor(self.pool).submit(self._run)
        return self

    def cancel(self, exception=None):
        ''' Stop the execution of the call (if possible) and wake up all
            threads that are waiting for the result.

            If the call is currently running and cannot be stopped, it is
            still marked as cancelled and the result is thrown away.

            This is a no-op on completed or cancelled calls.

            Return True if the command was cancelled before execution, false
            otherwise.
        '''
        with self._statelock:
            if self._state in (NEW, PENDING, RUNNING):
                self._exception = exception or CommandCancelledError()
                self._state = CANCELLED
                self._completed.set()
            # Note that future.cancel() MUST be protected with statelock.
            # to prevent _run() from being started in a CANCELLED state.
            return self.__future.cancel() if self.__future else True

    def cancelled(self):
        ''' Return True if the call was cancelled. '''
        return self._state == CANCELLED

    def running(self):
        ''' Return True if the call is currently being executed. '''
        return self._state == RUNNING

    def completed(self):
        ''' Return True if the call finished, failed or was cancelled. '''
        return self._completed.is_set()

    def wait(self, timeout=None):
        ''' Wait for the call to complete. Return True if the call completed
            within timeout seconds.

            This method does not cancel() the command after the timeout (as
            result() with a timeout would do).
        '''
        self._submit()
        return self._completed.wait(timeout)

    def result(self, timeout=None):
        ''' Submit the command and wait for the result.

            If run() fails with an exception and fallback() is defined, the
            fallback() result is returned instead.

            If fallback() is not defined or fails with an exception, this method
            will raise the exception that was originally raised by run().

            If a timeout is specified and the call takes longer than timeout
            seconds, it will be cancelled with a CommandTimeoutError.

            If the call runs into a timeout or is explicitly cancelled
            from a differed thread, this method will immediately return the
            fallback() value. If fallback() is not defined or fails
            with an exception, CommandCancelledError or CommandTimeoutError will
            be raised.
        '''
        self._submit()

        if self._state in (PENDING, RUNNING):
            self._completed.wait(timeout)

        if self._state in (PENDING, RUNNING):
            self.cancel(CommandTimeoutError())

        if self._state == FINISHED:
            return self._result

        with self._fallback_lock:
            if self._fallback_state == NEW:
                try:
                    self._fallback_result = self.fallback(self._exception)
                    self._fallback_state = FINISHED
                except Exception as e:
                    self._fallback_exception = e
                    self._fallback_state = FAILED
                    self.logger.exception('Fallback failed')

        if self._fallback_state == FINISHED:
            return self._fallback_result
        else:
            raise self._exception

    def exception(self, timeout=None):
        if self.wait(timeout):
            return self._exception
        raise CommandTimeoutError()

    def _run(self):

        with self._statelock:
            if self._state != PENDING: return
            self._state = RUNNING

        run_error, result = None, None
        try:
            a, ka = self.arguments
            result = self.run(*a, **ka)
        except Exception as e:
            self.logger.exception("Command failed")
            run_error = e

        with self._statelock:
            if self._state == RUNNING:
                if run_error:
                    self._state = FAILED
                    self._exception = run_error
                else:
                    self._state = FINISHED
                    self._result = result
                self._completed.set()
            # Other possible states:
            # CANCELLED: We ignore the result.

        try:
            self.cleanup()
        except Exception:
            log.exception("Command cleanup failed.")

