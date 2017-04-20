# Copyright 2007, 2008 VIFF Development Team.
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

from viff.field import GF
from viff.runtime import Runtime, start
from viff.config import load_config
from viff.inlinecb import viffinlinecb, declareReturnNop
from optparse import OptionParser

parser = OptionParser()
Runtime.add_options(parser)
options, args = parser.parse_args()
if len(args) == 0:
    parser.error("you must specify a config file")
else:
    id, players = load_config(args[0])

Zp = GF(1031)
Zq = GF(2039)

base = 1000
input1 = base - id
input2 = base + id

print "I am player %d, will share %d and %d " % (id, input1, input2)

@viffinlinecb
def main(tv):
    yield declareReturnNop(tv, Zp)

    a, b, c = tv.shamir_share([1, 2, 3], Zp, input1)
    x, y, z = tv.shamir_share([1, 2, 3], Zq, input2)

    d = yield tv.open(tv.mul(tv.mul(a, b), c))
    w = yield tv.open(tv.mul(tv.mul(x, y), z))

    def check(result, field, expected):
        if result == expected:
            print "%s: %s (correct)" % (field, result.value)
        else:
            print "%s: %s (incorrect, expected %d)" % (field, result.value, expected)

    check(d, "Zp", Zp(base-1) * Zp(base-2) * Zp(base-3))
    check(w, "Zq", Zq(base+1) * Zq(base+2) * Zq(base+3))

    tv.shutdown()

start(main, id, players, options)
