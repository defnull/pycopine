from pycopine import Command
from nose.tools import raises

@raises(NotImplementedError)
def test_not_implemented():
    class TestCommand(Command):
        pass

def test_minimal_command():
    class TestCommand(Command):
        def run(self): pass

