import sys
import math
import operator

def _print(*args):
    ''' print function wrapper '''

    # TODO write to fout?
    for arg in args:
        print arg,
    print

def tokenize(script):
    '''simplist possible tokenizer, just split on whitespace.'''

    for word in script.split():
       yield word

def parse(tokens):
    '''parse returns a block element wrapped around all the expressions
    you feed it. This is a very simple stack based parser with only two
    kinds of tokens: square brackets, which push/pop the stack level,
    and literal values. floats, integers, string literals, and symbols are allowed.'''

    stack = [ ['block'] ]
    for word in tokens:
        if word == '[':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif word == ']':
            stack.pop()
        else:
            if word.startswith("'"):
                value = unicode(word[1:])
            else:
                try:
                    value = int(word)
                except ValueError:
                    try:
                        value = float(word)
                    except ValueError:
                        value = word
            stack[-1].append(value)
    return stack[0]


class Frame(object):
    '''the Frame holds a namespace and current dynamic values. Used
    by Blocks and Functions to support lexical namespacing.'''

    def __init__(self, env, parent):
        '''env is a dictionary of key/value pairs at this level, parent
        is the parent frame to use if the key is not found.'''

        self.env = env or {}
        self.parent = parent

    def get(self, name):
        '''name resolution starts at this frame and proceeds recursivelly
        upwards through parents if necessary. Returns None if not found at
        any level'''

        if name in self.env:
            return self.env[name]
        else:
            return self.parent.get(name)

    def set(self, name, value):
        self.env[name] = value


class GlobalFrame(Frame):
    '''The ultimate frame object with some special features, namely the
    core library already installed.'''

    def __init__(self):
        self.env = {
            "nil": None,
            "print": _print,
        }
        # sin, cos, sqrt, pow, etc.
        self.env.update(math.__dict__)

        # eq, lte, in, and other python operators
        self.env.update(operator.__dict__)
    
    def get(self, name):
        '''no parent resolution is required, you either
        find the key here or it doesn't exist.'''
        return self.env.get(name)



class Function(object):
    '''Represents the instantiation of a user-defined function. Because of
    lexical scoping, each function instantation carries its own frame stack.'''

    def __init__(self, parent, names, expressions):
        self.parent = parent
        self.expressions = expressions
        self.names  = names

    def __call__(self, *args):
        '''During a call, a new Frame is constructed on the fly out of the
        passed in arguments. If the name isn't found in the arguments, name
        resolution continues to the lexical closing frame from where the 
        function was originally defined.'''

        # TODO, length checking, defaults, etc.
        env = dict(zip(self.names, args))
        frame = Frame(env, self.parent)
        for expression in self.expressions:
            result = evaluate(expression, frame)
        return result


class FExpr(Function):
    '''Represents the instantiation of a user-defined function expression. These
    differ from functions in that they do not evaluate their arguments until
    resolve is called but are otherwise basically identical.'''
    pass


class Block(object):
    '''Blocks evaluate a sequence of expressions and return the last value.
    They too get their own local frame, so can be used for namespacing, for
    example. Currently, blocks are aways evaluated immediately, but it would be
    possible to extend the language to obtain a reference to a block and
    execute it later.'''

    def __init__(self, parent, expressions):
        self.parent = parent
        self.expressions = expressions

    def do_it(self):
        frame = Frame({}, self.parent)
        result = None
        for expression in self.expressions:
            result = evaluate(expression, frame)

        return result

class Promise(object):
    '''A Promise a defered evaluation expression. Unlike a Block, it does not
    execute in its own Frame, but directly in the parent frame. For example, a
    set expression evaluated in a promise can have a side effect in the
    containing frame. Another difference is that A Promise can contain only a
    single expression. Promises are used in the implementation of if-else and
    fexpr.
    '''
    def __init__(self, frame, expression):
        self.frame = frame
        self.expression = expression

    def do_it(self):
        return evaluate(self.expression, self.frame)



def evaluate(expression, frame):
    '''This key function evaluates an already parsed expression in the context of a frame.'''

    if isinstance(expression, list):
        if len(expression) == 0:
            return None
        else:
            if expression[0] == 'set':
                left_hand_side = expression[1]
                right_hand_side = evaluate(expression[2], frame)
                frame.set(left_hand_side, evaluate(right_hand_side, frame))
                return right_hand_side
            elif expression[0] == 'if':
                if evaluate(expression[1], frame):
                    return evaluate(expression[2], frame)
                elif len(expression) >= 4:
                    return evaluate(expression[3], frame)
            elif expression[0] == 'block':
                return Block( frame, expression[1:] ).do_it()
            elif expression[0] == 'function':
                return Function(frame, expression[1], expression[2])
            elif expression[0] == 'fexpr':
                return FExpr(frame, expression[1], expression[2])
            elif expression[0] == 'resolve':
                possible_promise = evaluate(expression[1], frame)
                if hasattr(possible_promise, 'do_it') and callable(possible_promise.do_it):
                    return possible_promise.do_it()
                else:
                    return possible_promise
            else:
                try:
                    func = evaluate(expression[0], frame)
                    if isinstance(func, FExpr):
                        args = [ Promise(frame, expr) for expr in expression[1:] ]
                    else:
                        args = [ evaluate(arg, frame) for arg in expression[1:] ]
                    return func(*args)
                except Exception as e:
                    raise
    elif isinstance(expression, str):
        return frame.get(expression)
    else: # literal value
        return expression
        
def read_eval_print(fin, fout):
    '''not quite a repl loop, but does handle one complete iteration.'''
    
    frame = GlobalFrame()

    # define an iterator that can handle comments and multiple lines
    def non_comment_tokens(fin):
        for line in fin.readlines():
            if '#' in line:
                code, comment = line.split('#', 1)
            else:
                code = line
            for token in tokenize(code):
                yield token

    # parse always returns one "block" expression, which may have
    # zero to many expressions inside. Evaluating the block executes
    # these statements sequentially.
    expression = parse(non_comment_tokens(fin))
    result = evaluate(expression, frame)

    # if the whole program returns a result, print it out.
    if result is not None:
        fout.write(repr(result))
        fout.write('\n')

if __name__ == '__main__':
    if len(sys.argv) == 1:
        read_eval_print(sys.stdin, sys.stdout)
    else:
        read_eval_print(open(sys.argv[1]), sys.stdout)
