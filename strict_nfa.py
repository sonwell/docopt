from __future__ import with_statement, print_function
from operator import attrgetter

def _is_argument(name):
    return name[0] == '<' and name[-1] == '>' or name.isupper()


def _is_option(name):
    return name[0] == '-' and name not in '--'


class DocoptLanguageError(SyntaxError):

    '''
    Thrown when the syntax is violated.
    '''

class DocoptExit(SystemExit):

    '''
    Thrown to exit the program (e.g., after --version or -h).
    '''


class Node(object):

    def __init__(self, name, symbols):
        self.name = name
        self.next = []
        self.options = []
        self.follow = []
        self.symbols = symbols
        self.proto = self
        self.repred = 0

    def parse(self, tokens, prev, end):
        if not tokens:
            return end.parse(tokens, prev, end)
#        for node in self.next + self.options:
#            res = node.parse(tokens, prev, end)
#            if res is not None:
#                return res
        next = self.get(tokens)
        return next.parse(tokens, prev, end)

    def build(self, used):
        if set(used[0]) - set(self.options):
            return
        for option in self.options:
            if option not in used[0]:
                copy = option.copy()
                new = self.copy()
                Node.build(new, [used[0] + [option]] + used[1:])
                copy.follow += new.follow
                self.follow.append(copy)
#        if set(used[0]) ^ set(self.options):
#            return
        for node in self.next:
            copy = node.copy()
#            if copy not in self.follow:
            self.follow.append(copy)
            copy.build(used)

    def collapse(self):
        self.follow = [node for f in self.follow for node in f.collapse()]
        return [self]

    def match(self, tokens):
        for node in self.follow:
            res = node.match(tokens)
            if res is not None:
                return res
        return None

    def copy(self):
        copy = self.__class__(self.name, self.symbols)
        copy.next = list(self.next)
        copy.options = list(self.options)
        copy.proto = self.proto
        return copy

    def __eq__(self, other):
        return self.proto is other.proto

    def get(self, tokens):
        name = tokens[0]
        if name in self.symbols:
            sym = self.symbols[name].copy()
            sym.options = []
            sym.next = []
            return sym
        if _is_option(name):
            if len(name) > 2:
                if name[1] == '-':  # -o<arg> format
                    name, arg = name[:2], name[2:]
                    tokens.insert(0, arg)
                elif '=' in name:   # --long=<arg> format
                    name, args = name.split('=', 1)
                    tokens.insert(0, arg)
            sym = Option(name, self.symbols)
        elif _is_argument(name):
            sym = Argument(name, self.symbols)
        else:
            sym = Command(name, {})
        self.symbols[name] = sym
        return sym.copy()

    def __repr__(self):
        cl = '<%x>' % id(self)  #self.__class__.__name__
        if self.repred < 4:
            self.repred += 1
            items = self.follow  #or self.next + self.options
            if items:
                nexts = '\n  '.join('\n  '.join(repr(node).split('\n'))
                                                for node in items)
                self.repred -= 1
                return '%s(%r)\n  %s' % (cl, self.name, nexts) 
            self.repred -= 1
            return '%s(%r)' % (cl, self.name) 
        return '...'


class Literal(Node):

    def match(self, tokens):
        if not tokens:
            return None
        name = tokens.pop(0)
        if self.name == name:
            res = Node.match(self, tokens)
            if res is None:
                tokens.insert(0, name)
                return res
            res[name] = True
            return res
        tokens.insert(0, name)
        return None

class Variable(Node):

    def match(self, tokens):
        if not tokens:
            return None
        name = tokens.pop(0)
        res = Node.match(self, tokens)
        if res is None:
            tokens.insert(0, tokens)
            return res
        res[self.name] = name
        return res

class Argument(Variable):

    weight = 1

    def parse(self, tokens, prev, end):
        if not tokens:
            return end.parse(tokens, prev, end)
        name = tokens.pop(0)
        if name == self.name:
            next, options = Node.parse(self, tokens, prev, end)
            self.options = prev + options
            self.next.append(next)
            return self, options
        tokens.insert(0, name)
        return None


class Command(Literal):

    weight = 2

    def parse(self, tokens, prev, end):
        if not tokens:
            return end.parse(tokens, prev, end)
        name = tokens.pop(0)
        if name == self.name:
            cend = CommandEnd('#' + name, self.symbols)
            next, options = Node.parse(self, tokens, [], cend)
            self.options += options
            self.next.append(next)
            next, options = Node.parse(cend, tokens, prev, end)
            cend.options = prev + options
            cend.next.append(next)
            return self, options
        tokens.insert(0, name)
        return None

    def build(self, used):
        Node.build(self, [[]] + used)


class CommandEnd(Node):

    def build(self, used):
        used = used[1:]
        if len(used) < 1 or set(used[0]) - set(self.options):
            return
        for option in self.options:
            if option not in used[0]:
                copy = option.copy()
                new = self.copy()
                Node.build(new, [used[0] + [option]] + used[1:])
                copy.follow += new.follow
                self.follow.append(copy)
        if set(used[0]) ^ set(self.options):
            return
        for node in self.next:
            copy = node.copy()
            self.follow.append(copy)
            copy.build(used)

    def parse(self, tokens, prev, end):
#        self.options += prev
        return self, []

#    def collapse(self):
#        print self.follow
#        return [node for f in self.follow for node in f.collapse()]


class Option(Literal):

    weight = 2

    def parse(self, tokens, prev, end):
        if not tokens:
            return end.parse(tokens, prev, end)
        name = tokens.pop(0)
        if name == self.name:
            next, options = Node.parse(self, tokens, prev + [self], end)
            return next, [self] + options
        tokens.insert(0, name)
        return None


class Terminus(CommandEnd):

    weight = 3

#    def parse(self, tokens, prev, end):
#        self.options += prev
#        return self, []

    def collapse(self):
        if self.follow:  # stuff follows this "Terminus"
            return [self.proto]
        return [self.proto]  # this is an accepting state of the NFA

    def match(self, tokens):
        return {} if not tokens else None


class Beginning(Command):

    weight = 3

    def match(self, tokens):
        return Node.match(self, tokens)

    def parse(self, tokens, prev, end):
        next, options = Node.parse(self, tokens, [], end.copy())
        self.options += options
        self.next.append(next)
        return self, []


class Parser(object):

    def __init__(self):
        self.caret = Beginning('^', {})
        self.dollar = Terminus('$', {})
        self.schema = []

    def __call__(self, tokens, args):
        self.caret.parse(tokens, [], self.dollar)
        self.caret.build([])
        self.caret.collapse()
        return self.caret.match(args)

    def __enter__(self):
        self.schema.insert(0, [])
        return self

    def __exit__(self, type, value, traceback):
        self.schema.pop(0)
        return False  # allow the propagation of exceptions

    def validate(self, tokens):
        def decorator(fun):
            self.schema.append((tokens, fun))
            return fun
        return decorator


docopt = Parser()
if __name__ == '__main__':
    print(docopt(['y', '-y', '<y>', 'x', '<x>'],
                 ['y', '-y', '<y>', 'x', '<x>']))
