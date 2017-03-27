from twisted.internet import reactor
from twisted.python import log
from network import Server
import sys


def from_hex_to_byte(hex_string):
    byte_string = ""

    transfer = "0123456789abcdef"
    untransfer = {}
    for i in range(16):
        untransfer[transfer[i]] = i

    for i in range(0, len(hex_string), 2):
        byte_string += chr((untransfer[hex_string[i]] << 4) + untransfer[hex_string[i + 1]])

    return byte_string


log.startLogging(sys.stdout)


def done(result):
    print "Key result:"
    print result
    reactor.stop()


def bootstrapDone(found, server, key):
    if len(found) == 0:
        print "Could not connect to the bootstrap server."
        reactor.stop()
    server.get(key).addCallback(done)


key = from_hex_to_byte('f7bf674bd41c5a7affc8a61479d8968063fc609d')

server = Server()
server.listen(12346)
server.bootstrap([('67.215.246.10', 6881)]).addCallback(bootstrapDone, server, key)

reactor.run()
