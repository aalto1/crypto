#!/usr/bin/env python

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

# This example is a tribute to the original example of secure
# multi-party computation by Yao in 1982. In his example two
# millionaires meet in the street and they want to securely compare
# their fortunes. They want to do so without revealing how much they
# own to each other. This problem would be easy to solve if both
# millionaires trust a common third party, but we want to solve it
# without access to a third party.
#
# In this example the protocol is run between three millionaires and
# uses a protocol for secure integer comparison by Toft from 2005.
#
# Give a player configuration file as a command line argument or run
# the example with '--help' for help with the command line options.

from viff.field import GF
from viff.runtime import Runtime, start
from viff.config import load_config
from viff.util import rand, find_prime
from viff.inlinecb import viffinlinecb, declareReturnNop
from optparse import OptionParser

parser = OptionParser()
Runtime.add_options(parser)
options, args = parser.parse_args()
if len(args) == 0:
    parser.error("you must specify a config file")
else:
    id, players = load_config(args[0])

@viffinlinecb
def main(runtime):
    tv = runtime

    # This is the value we will use in the protocol.
    millions = rand.randint(1, 200)
    print "I am Millionaire %d and I am worth %d millions." \
        % (tv.id, millions)

    # For the comparison protocol to work, we need a sufficiently
    # large field modulus.
    k = tv.options.security_parameter
    l = tv.options.bit_length
    ln = len(tv.players).bit_length()
    Zp = GF(find_prime(2**(l + k + ln + 1), blum=True))
    yield declareReturnNop(tv, Zp)

    # We must secret share our input with the other parties. They
    # will do the same and we end up with three variables
    m1, m2, m3 = tv.shamir_share([1, 2, 3], Zp, millions)

    # Now that everybody has secret shared their inputs we can
    # compare them. We compare the worth of the first millionaire
    # with the two others, and compare those two millionaires with
    # each other.
    m1_ge_m2 = m1 >= m2
    m1_ge_m3 = m1 >= m3
    m2_ge_m3 = m2 >= m3

    # The results are secret shared, so we must open them before
    # we can do anything usefull with them.
    open_m1_ge_m2 = tv.open(m1_ge_m2)
    open_m1_ge_m3 = tv.open(m1_ge_m3)
    open_m2_ge_m3 = tv.open(m2_ge_m3)

    # We will now gather the results.
    m1_ge_m2, m1_ge_m3, m2_ge_m3 = yield open_m1_ge_m2, open_m1_ge_m3, open_m2_ge_m3

    # We can establish the correct order of Millionaires 2 and 3.
    if m2_ge_m3:
        comparison = [3, 2]
    else:
        comparison = [2, 3]

    # We only have to insert Millionaire 1 in the correct spot.
    if m1_ge_m2 and m1_ge_m3:
        # Millionaire 1 is largest.
        comparison = comparison + [1]
    elif not m1_ge_m2 and not m1_ge_m3:
        # Millionaire 1 is smallest.
        comparison = [1] + comparison
    else:
        # Millionaire 1 is between the others.
        comparison = [comparison[0], 1, comparison[1]]

    print "From poorest to richest:"
    for id in comparison:
        if id == tv.id:
            print "  Millionaire %d (%d millions)" % (id, millions)
        else:
            print "  Millionaire %d" % id

    tv.shutdown()

start(main, id, players, options)
