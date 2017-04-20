# Conversion to Unary Representation, BS
import operator
from viff.field import GF
from viff.runtime import Runtime, Share, start
from viff.config import load_config
from viff.util import find_prime
from viff.inlinecb import viffinlinecb, returnValue, declareReturn
from optparse import OptionParser

parser = OptionParser()
Runtime.add_options(parser)
options, args = parser.parse_args()
if len(args) == 0:
    parser.error("You must specify a config file.")
else:
    id, players = load_config(args[0])

@viffinlinecb
def main(runtime):
    global tv, Zp
    tv = runtime
    k = tv.options.security_parameter
    l = tv.options.bit_length
    ln = len(tv.players).bit_length()
    Zp = GF(find_prime(2**(l + k + ln + 1), blum=True))
    yield declareReturn(tv, Zp)

    shareZp = lambda x:Share(tv, Zp, Zp(x))
    t = 12
    for i in xrange(t):
        a = secret_index(shareZp(i),t)
        a = yield map(tv.open, a)
        print i, map(lambda v:int(v.value), a)
    tv.shutdown()  

# secret_index returns x-th unitvector of length n, assuming 0 <= x < n
def secret_index(x, n):
    # si1 returns all-0 vector of length n-1 (if x=0) and (x-1)-st unitvector of length n-1 (if 1 <= x < n)
    def si1(x, n):
        if n==1:
            return []
        elif n==2:
            return [x]
        else:
            b = tv.lsb(x)
            v = si1((x-b)*~Zp(2),(n+1)/2)
            w = tv.scalar_mul(b,v)
            return [b-sum(w)] + [v[i/2]-w[i/2] if i%2==0 else w[i/2] for i in xrange(n-2)]
    v = si1(x, n)
    return [Share(tv, Zp, Zp(1))-sum(v)]+v
        
start(main, id, players, options)
