__all__ =  ['Command', 'CommandMeta']
__all__ += ['CommandDirectory']
__all__ += ['CommandError', 'CommandSetupError', 'CommandTypeError', 'CommandNameError']



def NotImplementedMethod(*a, **ka):
    raise NotImplementedError("Method not implemented")

class CommandError(Exception): pass
class CommandSetupError(CommandError): pass

class CommandTypeError(CommandSetupError, TypeError): pass
class CommandNameError(CommandSetupError): pass

class CommandDirectory(object):
    ''' A collection of commands '''
    def __init__(self):
        self.commands = {}

    def add_command(self, CommandClass):
        if not issubclass(CommandClass, Command):
            raise CommandTypeError("Command classes must inherit from Command, or "\
                             "at least use CommandMeta as their type. %r" % CommandClass)
        name = CommandClass.__name__
        if name in self.commands:
            if self.commands[name] is CommandClass:
                return
            raise CommandNameError("Command names must be unique.")
        self.commands[name] = CommandClass
    
    def __contains__(self, other):
        return other in self.commands or other in self.commands.values()
    
    def clear(self):
        self.commands.clear()


class CommandMeta(type):
    ''' Metaclass for all commands. The magic happens here. '''

    @classmethod
    def __prepare__(mcl, name, bases):
        return dict()

    def __new__(mcl, name, bases, ns):
        if ns['__module__'] == __name__ and name == 'Command':
            return super().__new__(mcl, name, bases, dict(ns))

        if ns.get('run', NotImplementedMethod) is NotImplementedMethod:
            raise NotImplementedError("Commands must implement run().")

        cls = super().__new__(mcl, name, bases, dict(ns))
        cls.pycopine_directory.add_command(cls)
        return cls



class Command(object, metaclass=CommandMeta):
    ''' Base class for all user defined commands. '''
    pycopine_directory = CommandDirectory()
    run      = NotImplementedMethod
    fallback = NotImplementedMethod


