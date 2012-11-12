'''
docopt-nfa v. 0.0.0pre-alpha4

Usage: prog (x|y)...


Options:
    -y<boink>   x y z
'''

import re
import sys
import curses
curses.setupterm()


def _is_argument(name):
    return name[0] == '<' and name[-1] == '>' or name.isupper()


def _is_option(name):
    return name[0] == '-' and name not in '--'


class DocoptLanguageError(SyntaxError):

    '''Thrown when the syntax is violated.'''


class DocoptExit(SystemExit):

    '''Thrown to exit the program (e.g., after --version or -h).'''


class Token(str):

    '''
    Token class is a substring of the docstring (or whatever), extended to
    print with useful debugging info and to give worthwhile error messages
    (you should get underlined, red text pointing out the token).
    '''

    def __new__(klass, value, source, row, col):
        return str.__new__(klass, value)

    def __init__(self, value, source, row, col):
        str.__init__(self, value)
        self.source = source
        self.row = row
        self.col = col

    def __repr__(self):
        setf = curses.tigetstr('setaf') or curses.tigetstr('setf')
        normal = curses.tigetstr('sgr0')
        underline = curses.tigetstr('smul')
        yellow = curses.tparm(setf, curses.COLOR_RED)
        start, end = self.col, self.col + len(self)
        highlight = self.source[:start] + underline + yellow + \
            self + normal + self.source[end:]
        fmt = '%r on line %d:\n%s'
        return fmt % (str(self), self.row, highlight)

    def error(self, message):
        raise DocoptLanguageError('%s %r' % (message, self))


class Node(object):

    def __init__(self, name, symbols):
        self.name = name
        self.next = []
        self.options = []
        self.follow = []
        self.symbols = symbols
        self.proto = self
        self.repred = 0
        self.collapsed = False
        self.required = True
        self.built = False
        self._sym = {}

    def parse(self, tokens, prev, head, tail):
        if not tokens:
            return tail.parse(tokens, prev, head, tail)
        token = tokens[0]
        if token in '|)]':
            return tail, []
        elif token in '[(':
            return self._parse_group(tokens, prev, head, tail)
        elif token == '...':
            if head is None:
                token.error('Unexpected token')
            tokens.pop(0)
            self.next.append(head)
            return Node.parse(self, tokens, prev, head, tail)
        elif token == 'options':
            token.error("'options' directive is currently unsupported:")
        next = self.get(tokens)
        return next.parse(tokens, prev, self, tail)

    def _parse_group(self, tokens, prev, head, tail):
        token = tokens[0]
        start = Epsilon('', self.symbols)
        stop = Epsilon('', self.symbols)
        start.options = stop.options = prev
        optional, closing = token == '[', {'(': ')', '[': ']'}[token]
        appended, all_opts, token = [], [], '|'
        while token == '|':
            tokens.pop(0)
            next, opts = Node.parse(start, tokens, list(prev), self, stop)
            start.next.append(next)
            appended.append(next)
            all_opts += opts
            token = tokens[0]
        if token != closing:
            token.error("Expected %r, saw" % closing)
        if optional and stop not in start.next:
            start.next.append(stop)
        for opt in all_opts:
            opt.required = optional
        tokens.pop(0)
        prev += all_opts
        next, options = Node.parse(stop, tokens, prev, start, tail)
        stop.next.append(next)
        for node in appended:
            node.options += options
        return start, options + all_opts

    def build(self, used, allowed):
        allowed = [option for option in allowed if option in self.options]
        if not used or set(used[0]) - set(allowed) or self.built:
            return
        self.built = True
        self._build_options(used, allowed)
        self._build_nodes(used, allowed)

    def _build_options(self, used, allowed):
        for option in allowed:
            if option not in used[0]:
                copy = option.copy()
                new = self.copy()
                Node.build(new, [used[0] + [option]] + used[1:], allowed)
                copy.follow = list(new.follow)
                self.follow.append(copy)

    def _build_nodes(self, used, allowed):
        required = set(opt for opt in allowed if opt.required)
        skip_ends = required - set(used[0])
        for node in self.next:
            if isinstance(node, CommandEnd) and skip_ends:
                continue
            if node.built:
                self.follow.append(node)
                continue
            copy = node.copy()
            copy.build(used, allowed)
            self.follow.append(copy)

    def collapse(self):
        if not self.collapsed:
            self.collapsed = True
            self.follow = [node for f in self.follow for node in f.collapse()]
        return [self] if self.follow else []

    def match(self, tokens):
        for node in self.follow:
            res = node.match(tokens)
            if res is not None:
                return res
        return None

    def copy(self, copied=None):
        if copied is None:
            copied = {}
        if id(self) in copied:
            return copied[id(self)]
        print self.name, id(self)
        copy = self.__class__(self.name, self.symbols)
        copied[id(self)] = copy
        copy.next = [node.copy(copied) for node in self.next]
        copy.options = self.options
        copy.proto = self.proto
        copy.required = self.required
        copy._sym = self._sym
        return copy

    def __eq__(self, other):
        return self.proto is other.proto

    def get(self, tokens):
        name = tokens[0]
        if name in self.symbols:
            sym = self.symbols[name].copy()
            sym.options, sym.next = [], []
            return sym
        if _is_option(name):
            if len(name) > 2:
                if name[1] == '-':  # -stacked format
                    name, arg = name[:2], '-' + name[2:]
                    tokens.insert(0, arg)
                elif '=' in name:   # --long=<arg> format
                    name, args = name.split('=', 1)
                    tokens.insert(0, arg)
            sym = Option(name, self.symbols)
        elif _is_argument(name):
            sym = Argument(name, self.symbols)
        else:
            sym = Command(name, dict(self._sym))
        sym._sym = self._sym
        self.symbols[name] = sym
        return sym.copy()

    def __repr__(self):
        cl = '<%x>' % id(self.options)
        if self.repred < 4:
            self.repred += 1
            items = self.follow or self.next
            if items:
                nexts = '\n  '.join('\n  '.join(repr(node).split('\n'))
                                    for node in items)
                self.repred -= 1
                return "%s('%s')\n  %s" % (cl, self.name, nexts)
            self.repred -= 1
            return "%s('%s')" % (cl, self.name)
        return '...'


class Epsilon(Node):

    def collapse(self):
        if not self.collapsed:
            self.collapsed = True
            return [node for f in self.follow for node in f.collapse()]
        return []

    def build(self, used, allowed):
        allowed = [option for option in allowed if option in self.options]
        if set(used[0]) - set(allowed) or self.built:
            return
        self.built = True
        self._build_nodes(used, allowed)


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


class Argument(Node):

    def match(self, tokens):
        if not tokens:
            return None
        name = tokens.pop(0)
        res = Node.match(self, tokens)
        if res is None:
            tokens.insert(0, name)
            return res
        tokens.insert(0, name)
        res[self.name] = name
        return res

    def parse(self, tokens, prev, head, tail):
        if not tokens:
            return tail.parse(tokens, prev, head, tail)
        name = tokens.pop(0)
        if name == self.name:
            next, options = Node.parse(self, tokens, prev, self, tail)
            self.options = prev
            self.next.append(next)
            return self, options
        tokens.insert(0, name)
        return None


class Command(Literal):

    def parse(self, tokens, prev, head, tail):
        if not tokens:
            return tail.parse(tokens, prev, head, tail)
        name = tokens.pop(0)
        if name == self.name:
            end = CommandEnd('#' + name, self.symbols)
            end.options = prev
            next, _ = Node.parse(self, tokens, self.options, self, end)
            self.next.append(next)
            next, options = Node.parse(end, tokens, prev, None, tail)
            end.next.append(next)
            return self, options
        tokens.insert(0, name)
        return None

    def build(self, used, allowed):
        Node.build(self, [[]] + used, self.options)


class CommandEnd(Epsilon):

    def build(self, used, allowed):
        Node.build(self, used[1:], self.options)

    def parse(self, tokens, prev, head, tail):
        return self, []


class Option(Literal):

    def parse(self, tokens, prev, head, tail):
        if not tokens:
            return tail.parse(tokens, prev, head, tail)
        name = tokens.pop(0)
        if name == self.name:
            prev.append(self)
            next, opts = Node.parse(self, tokens, prev, self, tail)
            return next, opts + [self]
        tokens.insert(0, name)
        return None


class Terminus(CommandEnd):

    def collapse(self):
        if self.follow:  # stuff follows this "Terminus"
            return []
        return [self.proto]  # this is an accepting state of the NFA

    def match(self, tokens):
        return {} if not tokens else None


class Beginning(Command):

    def match(self, tokens):
        return Node.match(self, tokens)

    def parse(self, tokens, prev, head, tail):
        copy = tail.copy()
        token = '|'
        while token == '|':
            tokens.pop(0)
            # '...' as the first token is a syntax error.
            next, options = Node.parse(self, tokens, self.options, None, copy)
            self.next.append(next)
            if not tokens:
                break
            token = tokens[0]
        if tokens:
            token[0].error('Unexpected token')
        return self, options


class Parser(object):

    CARET_TOKEN = Token('^', '^', 0, 0)
    DOLLAR_TOKEN = Token('$', '$', 0, 0)

    def __init__(self):
        self.schema = [[]]
        self.usage = []

    def __call__(self, doc, args=None):
        if args is None:
            args = sys.argv[1:]
        return self._to_nfa(doc).match(args)

    def __enter__(self):
        self.schema.insert(0, [])
        return self

    def __exit__(self, type, value, traceback):
        self.schema.pop(0)
        return False  # allow the propagation of exceptions

    def _to_nfa(self, doc):
        lexer = Lexer(doc)
        self.usage.insert(0, lexer.usage)
        caret = Beginning(self.CARET_TOKEN, {})
        dollar = Terminus(self.DOLLAR_TOKEN, {})
        for tokens in lexer:
            caret.parse(tokens, [], None, dollar)
        try:
            caret.build([], None)
            caret.collapse()
        except RuntimeError:
            pass
        return caret

    def validate(self, tokens):
        def decorator(fun):
            self.schema.append((tokens, fun))
            return fun
        return decorator


class Lexer(object):

    usage_regex = re.compile(r'(usage:)', re.I)
    emptyline_regex = re.compile(r'\n[\s^\n]*\n')
    spacing_regex = re.compile('([\[\]\(\)\|]|\.\.\.)')

    def __init__(self, source):
        self.source = source
        self.usage, self.lineno = self.get_usage(source)
        self.tokens = self.lex(self.usage)

    def __iter__(self):
        for stream in self.tokens:
            yield stream
        raise StopIteration()

    def get_usage(self, source):
        indent = min(len(line) - len(line.strip())
                     for line in source.split('\n')[1:] if line.strip())
        source = '\n'.join(line[indent:] for line in source.split('\n'))
        ure = self.usage_regex
        elre = self.emptyline_regex
        try:
            before, usage, patterns = ure.split(source, maxsplit=1)
        except:
            self.error('No usage pattern found.')
        patterns = elre.split(patterns, maxsplit=1)[0]
        return usage + patterns.rstrip(), before.count('\n')

    def lex(self, usage):
        spaced = usage.split(None, 1)[1]
        spaced = self.spacing_regex.sub(r' \1 ', spaced)
        lines, patterns = spaced.split('\n'), usage.split('\n')
        tok = []
        lineno_offset = self.lineno
        while not lines[0].strip():
            lines = lines[1:]
            patterns = patterns[1:]
            lineno_offset += 1
        for index, pair in enumerate(zip(lines, patterns)):
            tok.append([])
            line, pattern = pair
            parts = line.split()
            offset = 0
            for part in parts:
                pos = pattern[offset:].find(part)
                lineno = lineno_offset + index
                tok[-1].append(Token(part, pattern,  lineno, offset + pos))
                offset += pos + len(part)
        program = tok[0][0]
        breaks = [i for i, line in enumerate(tok) if line[0] == program]
        return [sum(tok[i:j], [])
                for i, j in zip(breaks, breaks[1:] + [None])]

    def error(self, message):
        raise DocoptLanguageError(message)


docopt = Parser()
if __name__ == '__main__':
    args = docopt(__doc__, sys.argv[1:])
    if args is None:
        print docopt.usage[0]
    else:
        print args
