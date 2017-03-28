# Python Distributed Hash Table

**Documentation can be found at [kademlia.readthedocs.org](http://kademlia.readthedocs.org/).**

This library is an asynchronous Python implementation of the [Kademlia distributed hash table](http://en.wikipedia.org/wiki/Kademlia).  It uses [Twisted](https://twistedmatrix.com) to provide asynchronous communication.  The nodes communicate using [RPC over UDP](https://github.com/bmuller/rpcudp) to communiate, meaning that it is capable of working behind a [NAT](http://en.wikipedia.org/wiki/NAT).

This library aims to be as close to a reference implementation of the [Kademlia paper](http://pdos.csail.mit.edu/~petar/papers/maymounkov-kademlia-lncs.pdf) as possible.


## Usage
*This assumes you have a working familiarity with [Twisted](https://twistedmatrix.com).*

Assuming you want to connect to an existing network (run the standalone server example below if you don't have a network):

```python
from twisted.internet import reactor
from twisted.python import log
from network import Server
from utils import from_hex_to_byte
import sys

log.startLogging(sys.stdout)


def done(result):
    print "Key result:"
    print result
    reactor.stop()


def bootstrapDone(found, server, key):
    if len(found) == 0:
        print "Could not connect to the bootstrap server."
        reactor.stop()
    else:
        print "Bootstrap completed"

    server.get(key).addCallback(done)


key = from_hex_to_byte('f7bf674bd41c5a7affc8a61479d8968063fc609d')

server = Server(id=from_hex_to_byte('b481586aac12255d290fc575656dd31d67f765b8'))
server.listen(12346)
server.bootstrap([('67.215.246.10', 6881)]).addCallback(bootstrapDone, server, key)

reactor.run()

```
