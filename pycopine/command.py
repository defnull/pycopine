import concurrent.futures
import logging
import threading

__all__ =  ['Command', 'CommandMeta']
__all__ += ['CommandGroup']
__all__ += ['CommandError', 'CommandSetupError', 'CommandTypeError',
            'CommandNameError', 'CommandCancelledError', 'CommandIntegrityError', 'CommandExecutorNotFoundError']

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
        self.__cancelled = False
        self.__future = None
        self.__statelock = threading.Lock()

    def _run(self):
        a, ka = self.arguments
        log   = self.logger

        try:
            return self.run(*a, **ka)
        except Exception as e:
            log.warning("Command failed")
            log.exception("Command  exception: %r", e)
            if self.fallback is NotImplementedMethod:
                raise
            try:
                return self.fallback(e)
            except Exception as e2:
                log.error("Command fallback failed, too.")
                log.exception("Fallback exception: %r", e2)
                raise e
        finally:
            try:
                self.cleanup()
            except Exception as e:
                log.error("Command cleanup failed.")
                log.exception("Command exception: %r", e)

    def submit(self):
        with self.__statelock:
            if self.__future:
                raise CommandIntegrityError("Command submitted twice.")
            if self.__cancelled:
                raise CommandCancelledError("Submit on cancelled command.")
            self.__future = self.group.get_executor(self.pool).submit(self._run)
            return self

    def cancel(self):
        ''' Attempt to cancel the call. If the call is currently being executed
            and cannot be cancelled then the method will return False, otherwise
            the call will be cancelled and the method will return True. '''
        with self.__statelock:
            self.__cancelled = True
            return self.__future.cancel() if self.__future else True

    def cancelled(self):
        ''' Return True if the call was successfully cancelled.'''
        return self.__future.cancelled() if self.__future else self.__cancelled

    def running(self):
        ''' Return True if the call is currently being executed and cannot be
            cancelled.'''
        return self.__future and self.__future.running()

    def done(self):
        ''' Return True if the call was successfully cancelled or finished
            running.'''
        return self.__future.done() if self.__future else self.__cancelled

    def result(self, timeout=None):
        ''' Return the value returned by run(). If run() failed with an
            exception and fallback() is defined, the the fallback result is
            returned. If fallback() is not defined or fails too, this method
            will raise the same exception as run().

            If the call hasn’t yet completed then this method will wait up to
            timeout seconds. If the call hasn’t completed in timeout seconds,
            then a TimeoutError will be raised. timeout can be an int or float.
            If timeout is not specified or None, there is no limit to the wait
            time.

            If the future is cancelled before completing then CancelledError
            will be raised.'''
        if not self.__future: self.submit()
        return self.__future.result(timeout)

    def exception(self, timeout=None):
        ''' Return the exception raised by run(). If the call hasn’t yet
            completed then this method will wait up to timeout seconds. If the
            call hasn’t completed in timeout seconds, then a TimeoutError will
            be raised. timeout can be an int or float. If timeout is not
            specified or None, there is no limit to the wait time.

            If the future is cancelled before completing then CancelledError
            will be raised.

            If the call completed without raising, None is returned.'''
        if not self.__future: self.submit()
        return self.__future.exception(timeout)

    def add_done_callback(self, fn):
        ''' Attaches the callable fn to the future. fn will be called, with the
            future as its only argument, when the future is cancelled or
            finishes running.

            Added callables are called in the order that they were added and are
            always called in a thread belonging to the process that added them.
            If the callable raises a Exception subclass, it will be logged and
            ignored. If the callable raises a BaseException subclass, the
            behavior is undefined.

            If the future has already completed or been cancelled, fn will be
            called immediately.'''
        if not self.__future: self.submit()
        return self.__future.add_done_callback(fn)


