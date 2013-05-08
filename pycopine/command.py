
def NotImplementedMethod(*a, **ka):
    raise NotImplementedError("Method not implemented")

class CommandMeta(type):

   @classmethod
   def __prepare__(mcl, name, bases):
       return dict()

   def __new__(mcl, name, bases, ns):
       if ns['__module__'] == __name__ and name == 'Command':
          return super().__new__(mcl, name, bases, dict(ns))
       if ns.get('run', NotImplementedMethod) is NotImplementedMethod:
           raise NotImplementedError()
       return super().__new__(mcl, name, bases, dict(ns))

class Command(object, metaclass=CommandMeta):
    run      = NotImplementedMethod
    fallback = NotImplementedMethod
    


