from pycopine import *
from nose.tools import raises
import threading
import time


class CleanupMixin(object):
    def setUp(self):
        CommandGroup.clear_all()
    
    def tearDown(self):
        CommandGroup.clear_all()
        


class TestCommand(CleanupMixin):

    @raises(NotImplementedError)
    def test_run_not_implemented(self):
        class MyCommand(Command):
            pass

    @raises(NotImplementedError)
    def test_fallback_not_implemented_but_called(self):
        class MyCommand(Command):
            def run(self): pass
        MyCommand().fallback()

    def test_minimal_command(self):
        class MyCommand(Command):
            def run(self): pass



class TestCommandGroups(CleanupMixin):

    def test_default(self):
        class MyCommand(Command):
            def run(self): pass
        assert MyCommand in CommandGroup()
        assert MyCommand in MyCommand.group

    def test_explicit(self):
        class MyCommand(Command):
            group = 'test'
            def run(self): pass

        assert MyCommand in CommandGroup('test')
        assert MyCommand.group is CommandGroup('test')
        assert MyCommand not in CommandGroup()

    def test_unique_per_group(self):
        class MyCommand(Command):
            def run(self): pass

        class MyCommand(Command):
            group = 'test'
            def run(self): pass

    @raises(CommandNameError)
    def test_not_unique(self):
        class MyCommand(Command):
            def run(self): pass

        class MyCommand(Command):
            def run(self): pass

    def test_get_command(self):
        class MyCommand(Command):
            def run(self): pass
        assert MyCommand is MyCommand.group.get_command('MyCommand')

    @raises(CommandNotFoundError)
    def test_get_command_not_found(self):
        class MyCommand(Command):
            def run(self): pass
        MyCommand.group.get_command('MyOtherCommand')


class TestCommandPools(CleanupMixin):

    def test_default(self):
        class MyCommand(Command):
            def run(self, value): return value
        assert MyCommand.pool == 'default'
        assert MyCommand(5).result() == 5

    def test_explicit(self):
        class MyCommand(Command):
            pool = 'default'
            def run(self, value): return value
        assert MyCommand.pool == 'default'
        assert MyCommand(5).result() == 5

    @raises(CommandExecutorNotFoundError)
    def test_unknown_pool(self):
        class MyCommand(Command):
            pool = 'undefined'
            def run(self, value): return value
        assert MyCommand.pool == 'undefined'
        assert MyCommand(5).result() == 5


class TestCommandRunnable(CleanupMixin):
    
    def test_sync_execute(self):
        class MyCommand(Command):
            def run(self, value): return value
        
        assert MyCommand(5).result() == 5
        assert MyCommand(6).result() == 6

    def test_async_execute(self):
        wakeup = threading.Event()
        try:
            class MyCommand(Command):
                def run(self, value):
                    wakeup.wait()
                    return value

            command = MyCommand(5) 
            assert not command.running()
            assert not command.done()

            future = command.submit()
            assert command is future
            assert command.running()
            assert not command.done()

            wakeup.set()

            assert command.result() == 5
            assert not command.running()
            assert command.done()
        finally:
            wakeup.set()

    def test_result_twice(self):
        class MyCommand(Command):
            def run(self, value): return value
        
        cmd = MyCommand(5)
        assert cmd.result()
        assert cmd.result()

    @raises(CommandIntegrityError)
    def test_result_twice(self):
        class MyCommand(Command):
            def run(self, value): return value
        
        cmd = MyCommand(5)
        assert cmd.submit()
        assert cmd.submit()

    @raises(CommandCancelledError)
    def test_cancle_early(self):
        class MyCommand(Command):
            def run(self, value): return value
        
        cmd = MyCommand(5)
        assert cmd.cancel()
        assert cmd.done()
        assert cmd.cancelled()
        assert not cmd.running()
        cmd.result()


class TestCommandFallback(CleanupMixin):

    def test_fallback(sefl):
        class MyCommand(Command):
            def run(self, value): return 10/value
            def fallback(self, e): return 0
        
        assert MyCommand(2).result() == 5
        assert MyCommand(0).result() == 0

    @raises(ZeroDivisionError)
    def test_no_fallback(sefl):
        class MyCommand(Command):
            def run(self, value): return 10/value
        
        assert MyCommand(2).result() == 5
        assert isinstance(MyCommand(0).exception(), ZeroDivisionError)
        assert MyCommand(0).result() # This should throw

    @raises(ZeroDivisionError)
    def test_failing_fallback(sefl):
        class MyCommand(Command):
            def run(self, value): return 10/value
            def fallback(self, e): raise RuntimeError()
        
        assert MyCommand(2).result() == 5
        assert isinstance(MyCommand(0).exception(), ZeroDivisionError)
        assert MyCommand(0).result() # This should throw



class TestCommandCleanup(CleanupMixin):

    def test_cleanup(sefl):
        mutable = []
        class MyCommand(Command):
            def run(self): pass
            def cleanup(self): mutable.append(None)
        
        assert not mutable
        MyCommand().result()
        assert mutable

    def test_cleanup_after_error(sefl):
        mutable = []
        class MyCommand(Command):
            def run(self): return 1/0
            def cleanup(self): mutable.append(None)
        
        assert not mutable
        assert MyCommand().exception()
        assert mutable

    def test_cleanup_after_fallback(sefl):
        mutable = []
        class MyCommand(Command):
            def run(self): return 1/0
            def fallback(self, e): return 5
            def cleanup(self): mutable.append(None)
        
        assert not mutable
        assert MyCommand().result() == 5
        assert mutable

    def test_cleanup_after_fallback_error(sefl):
        mutable = []
        class MyCommand(Command):
            def run(self): return 1/0
            def fallback(self, e): return 1/0
            def cleanup(self): mutable.append(None)
        
        assert not mutable
        assert MyCommand().exception()
        assert mutable

    def test_cleanup_error(sefl):
        class MyCommand(Command):
            def run(self): pass
            def cleanup(self): 1/0

        assert MyCommand().result() is None


