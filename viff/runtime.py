# -*- coding: utf-8 -*-
#
# Copyright 2007, 2008, 2009 VIFF Development Team.
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

"""VIFF runtime. This is where the virtual ideal functionality is
hiding! The runtime is responsible for sharing inputs, handling
communication, and running the calculations.

Each player participating in the protocol will instantiate a
:class:`Runtime` object and use it for the calculations.

The Runtime returns :class:`Share` objects for most operations, and
these can be added, subtracted, and multiplied as normal thanks to
overloaded arithmetic operators. The runtime will take care of
scheduling things correctly behind the scenes.
"""

import sys, time, struct
from itertools import imap
from collections import deque
from viff.field import GF, FieldElement
from viff.util import rand
from twisted.internet import reactor
from twisted.internet.error import ConnectionDone, CannotListenError
from twisted.internet.defer import Deferred, DeferredList, maybeDeferred, inlineCallbacks
from twisted.internet.protocol import ReconnectingClientFactory, ServerFactory
from twisted.protocols.basic import Int16StringReceiver
from optparse import OptionParser, OptionGroup
from twisted.python import log

class Share(Deferred):
#class Share:
    """A shared number.

    The :class:`Runtime` operates on shares, represented by this class.
    Shares are asynchronous in the sense that they promise to attain a
    value at some point in the future.

    Shares overload the arithmetic operations so that ``x = a + b``
    will create a new share *x*, which will eventually contain the
    sum of *a* and *b*. Each share is associated with a
    :class:`Runtime` and the arithmetic operations simply call back to
    that runtime.
    """

    def __init__(self, runtime, field, value=None):
        """Initialize a share.

        If an initial value is given, it will be passed to
        :meth:`callback` right away.
        """
        assert field is not None, "Cannot construct share without a field."
        assert callable(field), "The field is not callable, wrong argument?"

        Deferred.__init__(self)
        self.runtime = runtime
        self.field = field
        if value is not None:
            self.callback(value)
        self.df = self
#         self.runtime = runtime
#         self.field = field
#         if isinstance(value, Deferred):
#             self.df = value
#         else:
#             self.df = Deferred()
#             if value is not None:
#                 self.df.callback(value)

    def __neg__(self):
        """Negation."""
        return self.runtime.neg(self)

    def __add__(self, other):
        """Addition."""
        return self.runtime.add(self, other)

    def __radd__(self, other):
        """Addition (reflected argument version)."""
        return self.runtime.add(self, other)

    def __sub__(self, other):
        """Subtraction."""
        return self.runtime.sub(self, other)

    def __rsub__(self, other):
        """Subtraction (reflected argument version)."""
        return self.runtime.sub(other, self)

    def __mul__(self, other):
        """Multiplication."""
        return self.runtime.mul(self, other)

    def __rmul__(self, other):
        """Multiplication (reflected argument version)."""
        return self.runtime.mul(self, other)

    def __invert__(self):
        """Inversion."""
        return self.runtime.invert(self)

    def __pow__(self, exponent):
        """Exponentation to known integer exponents."""
        return self.runtime.pow(self, exponent)

    def __xor__(self, other):
        """Exclusive-or."""
        return self.runtime.xor(self, other)

    def __rxor__(self, other):
        """Exclusive-or (reflected argument version)."""
        return self.runtime.xor(self, other)

    def __lt__(self, other):
        """Strictly less-than comparison."""
        # self < other <=> not (self >= other)
        return 1 - self.runtime.greater_than_equal(self, other)

    def __le__(self, other):
        """Less-than or equal comparison."""
        # self <= other <=> other >= self
        return self.runtime.greater_than_equal(other, self)

    def __gt__(self, other):
        """Strictly greater-than comparison."""
        # self > other <=> not (other >= self)
        return 1 - self.runtime.greater_than_equal(other, self)

    def __ge__(self, other):
        """Greater-than or equal comparison."""
        # self >= other
        return self.runtime.greater_than_equal(self, other)

    def __eq__(self, other):
        """Equality testing."""
        return self.runtime.equal(self, other)

    def __ne__(self, other):
        """Negated equality testing."""
        return 1 - self.runtime.equal(self, other)
        
    def clone(self):
        """Clone a share.

        Works like :meth:`util.clone_deferred` except that it returns a new
        :class:`Share` instead of a :class:`Deferred`.
        """

        def split_result(result):
            clone.callback(result)
            return result
        clone = Share(self.runtime, self.field)
        self.addCallback(split_result)
        return clone

def gatherShares(obj):
    if isinstance(obj, Share):
        return obj.clone()
    elif isinstance(obj, (list, tuple)):
        mux = [countShares(obj), Deferred()]
        registerShares(mux, obj)
        mux[1].addCallback(lambda _: get_result(obj))
        return mux[1]
    else:
        return obj

def countShares(obj):
    if isinstance(obj, (Share, Deferred)):
        return 1
    elif isinstance(obj, (list, tuple)):
        return sum(imap(countShares, obj))
    else:
        return 0
    
def registerShares(mux, obj):
    if isinstance(obj, (Share, Deferred)):
        def gotShare(val):
            mux[0] -= 1
            if mux[0] == 0:
                mux[1].callback(None)
            return val
        obj.addCallback(gotShare)
    elif isinstance(obj, (list, tuple)):
        for x in obj:
            registerShares(mux, x)
        
def get_result(obj):
    if isinstance(obj, (Share, Deferred)):
        return obj.result
    else:
        return type(obj)(imap(get_result, obj))

class ShareExchanger(Int16StringReceiver):
    """Send and receive shares.

    All players are connected by pair-wise connections and this
    Twisted protocol is one such connection. It is used to send and
    receive shares from one other player.
    """

    def __init__(self):
        self.peer_id = None
        self.lost_connection = Deferred()
        #: Data expected to be received in the future.
        self.incoming_data = {}
        self.waiting_deferreds = {}
        #: Statistics
        self.sent_packets = 0
        self.sent_bytes = 0

    def connectionMade(self):
        self.sendString(str(self.factory.runtime.id))

    def connectionLost(self, reason):
        reason.trap(ConnectionDone)
        self.lost_connection.callback(self)

    def stringReceived(self, string):
        """Called when a share is received.

        The string received is unpacked into the program counter, and
        a data part. The data is passed the appropriate Deferred in
        :class:`self.incoming_data`.
        """
        if self.peer_id is None:
            self.peer_id = int(string)
            self.factory.identify_peer(self)
        else:
            try:
                pc_size, data_size = struct.unpack("!HH", string[:4])
                fmt = "!%dI%ds" % (pc_size, data_size)
                unpacked = struct.unpack(fmt, string[4:])

                program_counter = unpacked[:pc_size]
                data = unpacked[-1]

                key = program_counter
                if key in self.waiting_deferreds:
                    deq = self.waiting_deferreds[key]
                    deferred = deq.popleft()
                    if not deq:
                        del self.waiting_deferreds[key]
                    deferred.callback(data)
                else:
                    deq = self.incoming_data.setdefault(key, deque())
                    deq.append(data)
            except struct.error, e:
                self.factory.runtime.abort(self, e)

    def sendData(self, program_counter, data):
        """Send data to the peer.

        The *program_counter* is a tuple of unsigned integers and 
        *data* is a string.

        The data is encoded as follows::

          +---------+-----------+--------+--------------+
          | pc_size | data_size |   pc   |     data     |
          +---------+-----------+--------+--------------+
            2 bytes   2 bytes     varies      varies

        The program counter takes up ``4 * pc_size`` bytes, 
        the data takes up ``data_size`` bytes.
        """
        pc_size = len(program_counter)
        data_size = len(data)
        fmt = "!HH%dI%ds" % (pc_size, data_size)
        t = (pc_size, data_size) + program_counter + (data,)
        packet = struct.pack(fmt, *t)
        self.sendString(packet)
        self.sent_packets += 1
        self.sent_bytes += len(packet)

    def loseConnection(self):
        """Disconnect this protocol instance."""
        self.transport.loseConnection()

class ShareExchangerFactory(ReconnectingClientFactory, ServerFactory):
    """Factory for creating ShareExchanger protocols."""

    protocol = ShareExchanger
    maxDelay = 3
    factor = 1.234567 # About half of the Twisted default

    def __init__(self, runtime, players, protocols_ready):
        self.runtime = runtime
        self.players = players
        self.needed_protocols = len(players) - 1
        self.protocols_ready = protocols_ready
        if self.needed_protocols == 0:
            self.protocols_ready.callback(self.runtime)
            
    def identify_peer(self, protocol):
        self.runtime.add_player(self.players[protocol.peer_id], protocol)
        self.needed_protocols -= 1
        if self.needed_protocols == 0:
            self.protocols_ready.callback(self.runtime)

    def clientConnectionLost(self, connector, reason):
        reason.trap(ConnectionDone)

class Runtime:
    """Basic VIFF runtime with no crypto.

    This runtime contains only the most basic operations needed such
    as the program counter, the list of other players, etc.
    """

    @staticmethod
    def add_options(parser):
        group = OptionGroup(parser, "VIFF Runtime Options")
        parser.add_option_group(group)

        group.add_option("-t", "--threshold", type="int", metavar="T",
                         help="Threshold -- threshold should be below n/2")
        group.add_option("-l", "--bit-length", type="int", metavar="L",
                         help=("Maximum bit length of input numbers for "
                               "comparisons."))
        group.add_option("-k", "--security-parameter", type="int", metavar="K",
                         help=("Security parameter. Comparisons will leak "
                               "information with probability 2**-K."))
        group.add_option("--no-log", action="store_true",
                         default=False, help="Disable logging.")
        group.add_option("--no-socket-retry", action="store_true",
                         default=False, help="Fail rather than keep retrying "
                         "to connect if port is already in use.")
        group.add_option("--host", metavar="HOST:PORT", action="append",
                         help="Override host and port of players as specified "
                         "in the configuration file. You can use this option "
                         "multiple times on the command line; the first will "
                         "override host and port of player 1, the second that "
                         "of player 2, and so forth.")

        parser.set_defaults(threshold=1, bit_length=32, security_parameter=30)
        
    def __init__(self, player, options):
        """Initialize runtime.

        Initialized a runtime owned by the given, the threshold, and
        optionally a set of options. The runtime has no network
        connections and knows of no other players -- the
        :func:`create_runtime` function should be used instead to
        create a usable runtime.
        """
        #: ID of this player.
        self.id = player.id
        #: Shamir secret sharing threshold.
        self.threshold = options.threshold

        self.options = options

        #: Current program counter.
        self.program_counter = [0]

        #: Connections to the other players.
        #: Mapping from Player ID to :class:`ShareExchanger` objects.
        self.protocols = {}

        #: Information on players.
        #: Mapping from Player ID to :class:`Player` objects.
        self.players = {}
        # Add ourselves without protocol.
        self.add_player(player)

    def add_player(self, player, protocol=None):
        self.players[player.id] = player
        if protocol is not None:
            self.protocols[player.id] = protocol

    @inlineCallbacks
    def shutdown(self):
        """Shutdown the runtime.

        All connections are closed and the runtime cannot be used
        again after this has been called.
        """

        if len(self.players)>1:
            print "Closing connections."
            yield self.synchronize()
            results = [maybeDeferred(self.port.stopListening)]
            for protocol in self.protocols.itervalues():
                results.append(protocol.lost_connection)
                protocol.loseConnection()
            yield DeferredList(results)
            reactor.stop()

    def abort(self, protocol, exc):
        """Abort the execution due to an exception.

        The *protocol* received bad data which resulted in *exc* being
        raised when unpacking.
        """
        print "*** bad data from Player %d: %s" % (protocol.peer_id, exc)
        print "*** aborting!"
        for p in self.protocols.itervalues():
            p.loseConnection()
        reactor.stop()
        print "*** all protocols disconnected"

    def increment_pc(self):
        """Increment the program counter."""
        self.program_counter[-1] += 1

    def fork_pc(self):
        """Fork the program counter."""
        self.program_counter.append(0)

    def unfork_pc(self):
        """Leave a fork of the program counter."""
        self.program_counter.pop()

    @inlineCallbacks
    def synchronize(self):
        """Introduce a synchronization point.

        Returns a :class:`Deferred` which will trigger if and when all
        other players have made their calls to :meth:`synchronize`. By
        adding callbacks to the returned :class:`Deferred`, one can
        divide a protocol execution into disjoint phases.
        """
        input_shares = [(GF(101)(player), GF(101)(0)) for player in self.players]
        yield DeferredList(self._exchange_shares(input_shares))
        
    def _send_share(self, peer_id, field_element):
        pc = tuple(self.program_counter)
        data = hex(field_element.value)
        self.protocols[peer_id].sendData(pc, data)
        
    def _expect_share(self, peer_id, field):
        share = Share(self, field)
        share.addCallback(lambda value: field(long(value, 16)))
#        share.df.addCallback(lambda value: field(long(value, 16)))
        key = tuple(self.program_counter)
        if key in self.protocols[peer_id].incoming_data:
            # We have already received some data from the other side.
            deq = self.protocols[peer_id].incoming_data[key]
            data = deq.popleft()
            if not deq:
                del self.protocols[peer_id].incoming_data[key]
            share.callback(data)
#            share.df.callback(data)
        else:
            # We have not yet received anything from the other side.
            deq = self.protocols[peer_id].waiting_deferreds.setdefault(key, deque())
            deq.append(share)
#            deq.append(share.df)
        return share

    def _exchange_shares(self, input_shares):
        output_shares = []
        for peer_id, share in input_shares:
            field = type(share)
            if peer_id.value == self.id:
                d = Share(self, field, share)
            else:
                self._send_share(peer_id.value, share)
                d = self._expect_share(peer_id.value, field)
            d.addCallback(lambda share, peer_id: (peer_id, share), peer_id)
#            d.df.addCallback(lambda share, peer_id: (peer_id, share), peer_id)
            output_shares.append(d)
        return output_shares

def create_runtime(id, players, options):
    """Create a :class:`Runtime` and connect to the other players.

    This function should be used in normal programs instead of
    instantiating the Runtime directly. This function makes sure that
    the Runtime is correctly connected to the other players.
    """

    assert 2 * options.threshold < len(players)

    # The import is put here because of circular depencencies
    # between viff.runtime and viff.passive.
    from viff.passive import PassiveRuntime

    # This will yield a Runtime when all protocols are connected.
    result = Deferred()

    # Create a runtime that knows about no other players than itself.
    # It will eventually be returned in result when the factory has
    # determined that all needed protocols are ready.
    runtime = PassiveRuntime(players[id], options)

    if len(players)==1: 
        result.callback(runtime)
        return result

    if options.host:
        for i in xrange(len(options.host)):
            players[i+1].host, port_str = options.host[i].rsplit(":")
            players[i+1].port = int(port_str)
        
    factory = ShareExchangerFactory(runtime, players, result)

    port = players[id].port
    runtime.port = None
    delay = 2
    while runtime.port is None:
        # We keep trying to listen on the port, but with an
        # exponentially increasing delay between each attempt.
        try:
            runtime.port = reactor.listenTCP(port, factory)
        except CannotListenError, e:
            if options.no_socket_retry:
                raise
            delay *= 1 + rand.random()
            print "Error listening on port %d: %s" % (port, e.socketError[1])
            print "Will try again in %d seconds" % delay
            time.sleep(delay)
    print "Listening on port %d" % port

    for peer_id, player in players.iteritems():
        if peer_id > id:
            print "Will connect to %s" % player
            reactor.connectTCP(player.host, player.port, factory)

    return result

def start(f, id, players, options):
    if not options.no_log:
        log.startLogging(sys.stdout)
    runtime = create_runtime(id, players, options)
    runtime.addCallback(f)
    if len(players)>1:
        reactor.run()
