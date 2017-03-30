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
import sys
import binascii

log.startLogging(sys.stdout)


def done(result):
    print "Found peers:", result
    reactor.stop()


def bootstrap_done(found, server, info_hash):
    if len(found) == 0:
        print "Could not connect to the bootstrap server."
        reactor.stop()
    else:
        print "Bootstrap completed"

        # server.announce_peer(info_hash, 12357).addCallback(done)
        server.get_peers(info_hash).addCallback(done)


def start_dht_server(ip):
    info_hash = binascii.unhexlify('59f115bc5e2e845326a0c871d33010ef6bc3349a')
    # info_hash = binascii.unhexlify('971862a015ba2fdc834c0df70271983f8a4badb0')

    server = Server(id=binascii.unhexlify('cd2e6673b9f2a21cad1e605fe5fb745b9f7a214d'))
    server.listen(12346)
    server.bootstrap([(ip, 6881)]).addCallback(bootstrap_done, server, info_hash)


reactor.resolve('router.bittorrent.com').addCallback(start_dht_server)
reactor.run()
```
