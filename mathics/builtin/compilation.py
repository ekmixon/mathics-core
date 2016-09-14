import ctypes

from mathics.builtin.base import Builtin, BoxConstruct
from mathics.core.expression import Atom, Expression, Symbol, String, from_python, Integer, Real


class Compile(Builtin):
    '''
    >> cf = Compile[{{x, _Real}}, Sin[x]]
     = CompiledFunction[{x}, Sin[x], -CompiledCode-]

    >> cf[1.4]
     = 0.98545

    #> cf[1/2]
     = 0.479426

    #> cf[4]
     = -0.756802

    #> cf[x]
     : Invalid argument x should be Integer, Real or boolean.
     = CompiledFunction[{x}, Sin[x], -CompiledCode-][x]
    '''

    requires = (
        'llvmlite',
    )

    messages = {
        'invar': 'var `1` should be {symbol, type} annotation.',
        'invars': 'vars should be a list of {symbol, type} annotations.',
        'comperr': 'expression `1` could not be compiled.',
    }

    def apply(self, vars, expr, evaluation):
        'Compile[vars_, expr_]'
        from mathics.builtin.compile import _compile, int_type, real_type, bool_type, CompileArg, CompileError

        # _Complex not implemented
        permitted_types = {
            Expression('Blank', Symbol('Integer')): int_type,
            Expression('Blank', Symbol('Real')): real_type,
            Symbol('True'): bool_type,
            Symbol('False'): bool_type,
        }

        if not vars.has_form('List', None):
            return evaluation.message('Compile', 'invars')
        args = []
        for var in vars.get_leaves():
            if var.has_form('List', 1) and isinstance(var.leaves[0], Symbol):
                args.append(CompileArg(var.leaves[0].get_name(), real_type))
            elif var.has_form('List', 2):
                symb, typ = var.get_leaves()
                if isinstance(symb, Symbol) and typ in permitted_types:
                    args.append(CompileArg(symb.get_name(), permitted_types[typ]))
                else:
                    return evaluation.message('Compile', 'invar', var)
            else:
                return evaluation.message('Compile', 'invar', var)

        try:
            cfunc = _compile(expr, args)
        except CompileError:
            return evaluation.message('Compile', 'comperr', expr)
        code = CompiledCode(cfunc)
        arg_names = Expression('List', *(Symbol(arg.name) for arg in args))
        return Expression('CompiledFunction', arg_names, expr, code)


class CompiledCode(Atom):
    def __init__(self, cfunc, **kwargs):
        super(CompiledCode, self).__init__(**kwargs)
        self.cfunc = cfunc

    def __str__(self):
        return '-CompiledCode-'

    def do_copy(self):
        return CompiledCode(self.cfunc)

    def default_format(self, evaluation, form):
        return str(self)

    def get_sort_key(self, pattern_sort=False):
        if pattern_sort:
            return super(CompiledCode, self).get_sort_key(True)
        else:
            return hash(self)

    def same(self, other):
        return self is other

    def to_python(self, *args, **kwargs):
        return None

    def __hash__(self):
        return hash(("CompiledCode", ctypes.addressof(self.cfunc)))  # XXX hack

    def atom_to_boxes(self, f, evaluation):
        return Expression('CompiledCodeBox')


class CompiledCodeBox(BoxConstruct):
    def boxes_to_text(self, leaves, **options):
        return '-CompiledCode-'

    def boxes_to_xml(self, leaves, **options):
        return '-CompiledCode-'

    def boxes_to_tex(self, leaves, **options):
        return '-CompiledCode-'


class CompiledFunction(Builtin):
    messages = {
        'argerr': 'Invalid argument `1` should be Integer, Real or boolean.',
    }

    def apply(self, argnames, expr, code, args, evaluation):
        'CompiledFunction[argnames_, expr_, code_CompiledCode][args__]'
        py_args = []
        for arg in args.get_sequence():
            if isinstance(arg, Integer):
                py_args.append(arg.get_int_value())
            elif arg.same(Symbol('True')):
                py_args.append(True)
            elif arg.same(Symbol('False')):
                py_args.append(False)
            else:
                py_args.append(arg.round_to_float(evaluation))
        try:
            result = code.cfunc(*py_args)
        except ctypes.ArgumentError:
            return evaluation.message('CompiledFunction', 'argerr', args)
        return from_python(result)
