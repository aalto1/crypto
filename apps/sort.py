# Copyright 2008 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License (LGPL) as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General
# Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with VIFF. If not, see <http://www.gnu.org/licenses/>.

# This example demonstrates how a secure sorting algorithm can be
# implemented using VIFF. The algorithm used is bitonic sort which was
# chosen in order to maximize the amount of work (comparisons) done in
# parallel. Bitonic sort uses 1/2 * log n * (log n + 1) comparator
# stages and each stage consists of n/2 parallel comparisons. The
# total number of comparisons is thus O(n log^2 n).
#
# http://www.iti.fh-flensburg.de/lang/algorithmen/sortieren/bitonic/oddn.htm

from viff.field import GF
from viff.runtime import Runtime, Share, start
from viff.config import load_config
from viff.util import find_prime, rand
from viff.inlinecb import viffinlinecb, declareReturnNop
from optparse import OptionParser

parser = OptionParser()
parser.add_option("-s", "--size", type="int", help="array size")
parser.set_defaults(size=8)
Runtime.add_options(parser)
options, args = parser.parse_args()
if len(args) == 0:
    parser.error("you must specify a config file")
else:
    id, players = load_config(args[0])

@viffinlinecb
def main(runtime):
    global tv, Zp, comparisons
    tv = runtime
    k = tv.options.security_parameter
    l = tv.options.bit_length
    ln = len(tv.players).bit_length()
    Zp = GF(find_prime(2**(l + k + ln + 1), blum=True))
    
    yield declareReturnNop(tv, Zp)
 
    comparisons = 0
    a = [Share(tv, Zp, Zp(i**2)) for i in range(options.size)]
    sorted = yield map(tv.open, bsort(a))
    print "Sorted array: ", [int(x.value) for x in sorted]
    print "Made %d comparisons" % comparisons
    tv.shutdown()

def bsort(a):

    def bitonic_sort(lo, n, dir):
        if n > 1:
            m = n / 2
            bitonic_sort(lo, m, not dir)
            bitonic_sort(lo + m, n - m, dir)
            bitonic_merge(lo, n, dir)
    
    def bitonic_merge(lo, n, dir):
        if n > 1:
            # set m as the greatest power of 2 less than n.
            m=2**((n-1).bit_length()-1)
            for i in xrange(lo, lo + n - m):
                compare(i, i+m, dir)
            bitonic_merge(lo, m, dir)
            bitonic_merge(lo + m, n - m, dir)
    
    def compare(i, j, dir):
        global comparisons
        comparisons += 1
        b = dir^(a[i] <= a[j])
        b_ai_aj = b * (a[i] - a[j])
        a[i] -= b_ai_aj
        a[j] += b_ai_aj

    bitonic_sort(0, len(a), dir=True)
    return a

start(main, id, players, options)
