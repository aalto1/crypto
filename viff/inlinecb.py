from itertools import imap
from viff.runtime import Share, gatherShares
from viff.util import wrapper
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred, _inlineCallbacks, returnValue

class pc_wrapper(object):
    """ Decorator inside which the program counter is forked. """
    def __init__(self, runtime, f):
        self.runtime = runtime
        self.runtime.increment_pc()
        self.runtime.fork_pc()
        self.saved_pc = self.runtime.program_counter[:]
        self.runtime.unfork_pc()
        self.f = f
        
    def send(self, value):
        current_pc = self.runtime.program_counter[:]
        self.runtime.program_counter[:] = self.saved_pc
        try:
            yobj = self.f.send(value)
            return gatherShares(yobj)
        finally:
            self.saved_pc = self.runtime.program_counter[:]
            self.runtime.program_counter[:] = current_pc
        
def reconcile(decl,givn):
    if isinstance(givn,Failure): # detect failures from the inline callback
        givn.raiseException()
    elif decl is None:
        return
    elif type(decl) is list:
        for (d,g) in zip(decl,givn): reconcile(d,g)
    elif isinstance(givn, Deferred):
        givn.chainDeferred(decl)
#     elif isinstance(givn, Share):
#         givn.df.chainDeferred(decl.df)
    else:
        decl.callback(givn)
#        decl.df.callback(givn)
                
def declareReturn(rt, Zp, *args):
    def make(ix):
        if ix>=len(args): return Share(rt, Zp)
        return [make(ix+1) for _ in xrange(args[ix])]
    return rt, make(0)
    
def declareReturnNop(rt, Zp):
    return rt, None

def ncopy(nested_lists):
    if isinstance(nested_lists, list):
        return list(imap(ncopy, nested_lists))
    else:
        return nested_lists

def viffinlinecb(f):
    """
    VIFF inline callback mechanism.
    
    The decorated function should be a generator that:
    
     - yields as first value (rt,shs), where rt is the used runtime and shs
       is a Share/(nested) list of Shares that will be the deferred result
       of this function. For convenience, (rt,shs) can be generated using
       declareReturn or declareReturnNop: use declareReturn(rt,Zp) for
       functions that return a single value; declareReturn(rt,Zp,n1,n2,...) for
       functions returning n1xn2x...-shaped nested list, and declareReturnNop
       for functions without a return value.
       
     - next, yields any Shares or (nested) lists of shares that it needs to
       have the values of. The return of the yield is the value of that share.
       
     - finally, returns values or Shares with returnValue.    
    """
    
    @wrapper(f)
    def unwindGenerator(*args, **kwargs):
        gen = f(*args, **kwargs)
        rt, rettype = gen.send(None)
        defr = _inlineCallbacks(None, pc_wrapper(rt, gen), Deferred())
        defr.addCallback(lambda v: reconcile(rettype, v))
        return ncopy(rettype)
        
    return unwindGenerator
