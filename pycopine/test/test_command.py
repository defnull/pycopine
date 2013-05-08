from pycopine import Command
from nose.tools import raises

class TestCommand(object):

    def tearDown(self):
        Command.pycopine_directory.clear()

    @raises(NotImplementedError)
    def test_not_implemented(self):
        class TestCommand(Command):
            pass

    def test_minimal_command(self):
        class TestCommand(Command):
            def run(self): pass

    def test_command_in_directory(self):
        class TestCommand(Command):
            def run(self): pass
        assert TestCommand in TestCommand.pycopine_directory

