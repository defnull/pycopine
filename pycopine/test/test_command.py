from pycopine import Command, CommandDirectory, CommandNameError
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


class TestCommandDirectory(object):

    def setUp(self):
        self.dir = CommandDirectory()

    def tearDown(self):
        Command.pycopine_directory.clear()

    def test_default(self):
        class TestCommand(Command):
            def run(self): pass
        assert TestCommand in Command.pycopine_directory
        assert TestCommand in TestCommand.pycopine_directory

    def test_explicit(self):
        class TestCommand(Command):
            pycopine_directory = self.dir
            def run(self): pass

        assert TestCommand in self.dir
        assert TestCommand.pycopine_directory is self.dir
        assert TestCommand not in Command.pycopine_directory

    @raises(CommandNameError)
    def test_NotUnique(self):
        class TestCommand(Command):
            pycopine_directory = self.dir
            def run(self): pass

        class TestCommand(Command):
            pycopine_directory = self.dir
            def run(self): pass
