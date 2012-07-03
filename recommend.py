'''
If you have a list of possible commands, then we can recommend the nearest
one(s) a la git. This is an example based on my US keyboard.
'''


def make_keypos(*keyboard):
    keypos = {}
    for i, g in enumerate(keyboard):             # case (upper/lower)
        for j, row in enumerate(g.split('\n')):  # keyboard column
            for k, char in enumerate(row):       # keyboard row
                keypos[char] = (i, j, k)
    del keypos[' ']
    return keypos


keypos = make_keypos(
    r'''
    `1234567890-=
     qwertyuiop[]\
     asdfghjkl;'
     zxcvbnm,./
    ''',
    r'''
    ~!@#$%^&*()_+
     QWERTYUIOP{}|
     ASDFGHJKL:"
     ZXCVBNM<>?
    '''
)


def sub(a, b):  # substitution cost
    pa, pb = keypos[a], keypos[b]
    return sum(abs(pa[i] - pb[i]) for i in xrange(3))


def repl(a, b):
    al, bl = len(a), len(b)
    mat = [[0 for i in xrange(al + 1)] for j in xrange(bl + 1)]
    for j in xrange(bl):
        for i in xrange(al):
            if j == 0:
                mat[0][i + 1] = mat[0][i] + keypos[a[i]][0] + 1
            if i == 0:
                mat[j + 1][0] = mat[j][0] + keypos[b[j]][0] + 1
            mat[j + 1][i + 1] = min(
                mat[j][i] + sub(a[i], b[j]),  # match or hit nearby key
                mat[j][i + 1] + keypos[b[j]][0] + 1,
                mat[j + 1][i] + keypos[a[i]][0] + 1
                #          shift key ^            ^ missing key
            )
    return mat[j + 1][i + 1]


def did_you_mean(ipt):
    close = []
    commands = ('branch', 'commit', 'add', 'rm', 'tab', 'tag')
    beat_this = 4
    for c in commands:
        dist = repl(ipt, c)
        if 0 < dist < beat_this:
            close.append(c)
    if close:
        print("Did you mean %s?\n    %s" %
              ("this" if len(close) == 1 else "one of these",
              '\n    '.join(close)))


did_you_mean('remv')
did_you_mean('rm')
did_you_mean('remove')
did_you_mean('ad')
did_you_mean('comit')
did_you_mean('comet')
did_you_mean('tav')
