import re
import sys
import curses
curses.setupterm()


def _is_argument(name):
    return name[0] == '<' and name[-1] == '>' or name.isupper()


def _is_option(name):
    return name[0] == '-' and str(name) not in '--'


class DocoptLanguageError(SyntaxError):

    '''Thrown when the syntax is violated.'''


class DocoptExit(SystemExit):

    '''Thrown to exit the program (e.g., after --version or -h).'''


class Token(object):

    def __init__(self, value, source, row, col):
        self.value = value
        self.source = source
        self.row = row
        self.col = col

    def __eq__(self, other):
        return self.value == other

    def __ne__(self, other):
        return self.value != other

    def __len__(self):
        return len(self.value)

    def __repr__(self):
        setf = curses.tigetstr('setaf') or curses.tigetstr('setf')
        normal = curses.tigetstr('sgr0')
        underline = curses.tigetstr('smul')
        yellow = curses.tparm(setf, curses.COLOR_RED)
        start, end = self.col, self.col + len(self.value)
        highlight = self.source[:start] + underline + yellow + \
            self.value + normal + self.source[end:]
        fmt = '%r on line %d:\n%s'
        return fmt % (self.value, self.row, highlight)

    def __str__(self):
        return self.value

    def __getitem__(self, item):
        return self.value.__getitem__(item)

    def __radd__(self, other):
        return other + self.value

    def error(self, message):
        raise DocoptLanguageError('%s %r' % (message, self))

    def isupper(self):
        return self.value.isupper()


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

    def parse(self, tokens, prev, head, tail):
        if not tokens:
            return tail.parse(tokens, prev, head, tail)
        token = tokens[0]
        if str(token) in '|)]':
            return tail, []
        elif str(token) in '[(':
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
        optional, closing = token == '[', {'(': ')', '[': ']'}[str(token)]
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
        if not used or set(used[0]) - set(allowed):
            return
        self._build_options(used, allowed)
        self._build_nodes(used, allowed)

    def _build_options(self, used, allowed):
        for option in allowed:
            if option not in used[0]:
                copy = option.copy()
                new = self.copy()
                Node.build(new, [used[0] + [option]] + used[1:], allowed)
                copy.follow += new.follow
                self.follow.append(copy)

    def _build_nodes(self, used, allowed):
        required = set(opt for opt in allowed if opt.required)
        skip_ends = required - set(used[0])
        for node in self.next:
            if isinstance(node, CommandEnd) and skip_ends:
                continue
            copy = node.copy()
            copy.build(used, allowed)
            self.follow.append(copy)

    def collapse(self):
        if not self.collapsed:
            #self.collapsed = True
            self.follow = [node for f in self.follow for node in f.collapse()]
        return [self] if self.follow else []

    def match(self, tokens):
        for node in self.follow:
            res = node.match(tokens)
            if res is not None:
                return res
        return None

    def copy(self):
        copy = self.__class__(self.name, self.symbols)
        copy.next = list(self.next)
        copy.options = self.options
        copy.proto = self.proto
        copy.required = self.required
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
            sym = Command(name, {})
        self.symbols[name] = sym
        return sym.copy()

    def __repr__(self):
        cl = '<%x>' % id(self.options)
        if self.repred < 4:
            self.repred += 1
            items = self.follow
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
            #self.collapsed = True
            return [node for f in self.follow for node in f.collapse()]
        return []

    def build(self, used, allowed):
        allowed = [option for option in allowed if option in self.options]
        if set(used[0]) - set(allowed):
            return
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
            res[str(name)] = True
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
        res[str(self.name)] = name
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
            col = self.name.col
            src = self.name.source
            token = Token('#' + name, src[:col] + '#' + src[col:],
                          self.name.row, self.name.col)
            end = CommandEnd(token, self.symbols)
            end.options = prev
            next, _ = Node.parse(self, tokens, self.options, self, end)
            self.next.append(next)
            # Use None as head... I dunno if it's ever possible to encounter
            # a case where a command ends and there's a '...' immediately
            # following it. For good measure, we make it a syntax error...
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
        # '...' as the first token is a syntax error.
        next, options = Node.parse(self, tokens, self.options, None, copy)
        self.next.append(next)
        return self, options


class Parser(object):

    CARET_TOKEN = Token('^', '^', 0, 0)
    DOLLAR_TOKEN = Token('$', '$', 0, 0)

    def __init__(self):
        self.schema = []
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
        try:
            for tokens in lexer:
                caret.parse(tokens, [], None, dollar)
        except DocoptLanguageError as e:
            raise DocoptExit(e.message)
        caret.build([], None)
        caret.collapse()
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
        program = tok[0][0].value
        breaks = [i for i, line in enumerate(tok) if line[0] == program]
        return [sum(tok[i:j], [])[1:]
                for i, j in zip(breaks, breaks[1:] + [None])]

    def error(self, message):
        raise DocoptLanguageError(message)


docopt = Parser()
test = '''
       Usage: prog x [-y 1 3 5 | 2 4 6]
       '''
if __name__ == '__main__':
    args = docopt(test, sys.argv[1:])
    if args is None:
        print docopt.usage[0]
    else:
        print args
