import random

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from rpcudp.protocol import RPCProtocol

from node import Node
from routing import RoutingTable
from log import Logger

from struct import pack

from bencode import bencode, bdecode, BTFailure


class KademliaProtocol(RPCProtocol):
    def __init__(self, sourceNode, storage, ksize):
        RPCProtocol.__init__(self)
        self.router = RoutingTable(self, ksize, sourceNode)
        self.storage = storage
        self.sourceNode = sourceNode
        self.log = Logger(system=self)
        self.transactionSeq = 0

    def datagramReceived(self, datagram, address):
        if self.noisy:
            log.msg("received datagram from %s" % repr(address))

        try:
            msg = bdecode(datagram)
            msgID = msg["t"]
            msgType = msg["y"]

            if msgType == "q":
                self._acceptRequest(msgID, [msg["q"], msg["a"]], address)
            elif msgType == "r":
                self._acceptResponse(msgID, msg["r"], address)
            else:
                # otherwise, don't know the format, don't do anything
                # TODO: we must reply error message
                log.msg("Received unknown message from %s, ignoring" % repr(address))
        except BTFailure:
            log.msg("Not a valid bencoded string from %s, ignoring" % repr(address))

    def sendMessage(self, address, message):
        msgID = pack(">I", self.transactionSeq)
        self.transactionSeq += 1

        message["t"] = msgID

        self.transport.write(bencode(message), address)

        d = defer.Deferred()
        timeout = reactor.callLater(self._waitTimeout, self._timeout, msgID)

        self._outstanding[msgID] = (d, timeout)
        return d

    def getRefreshIDs(self):
        """
        Get ids to search for to keep old buckets up to date.
        """
        ids = []
        for bucket in self.router.getLonelyBuckets():
            ids.append(random.randint(*bucket.range))
        return ids

    def rpc_ping(self, sender, nodeId):
        source = Node(nodeId, sender[0], sender[1])
        self.welcomeIfNewNode(source)
        return self.sourceNode.id

    def rpc_announce_peer(self, sender, nodeId, key, value):
        source = Node(nodeId, sender[0], sender[1])
        self.welcomeIfNewNode(source)
        self.log.debug("got a store request from %s, storing value" % str(sender))
        self.storage[key] = value
        return True

    def rpc_find_node(self, sender, nodeId, key):
        self.log.info("finding neighbors of %i in local table" % long(nodeId.encode('hex'), 16))
        source = Node(nodeId, sender[0], sender[1])
        self.welcomeIfNewNode(source)
        node = Node(key)
        return map(tuple, self.router.findNeighbors(node, exclude=source))

    def rpc_get_peers(self, sender, nodeId, key):
        source = Node(nodeId, sender[0], sender[1])
        self.welcomeIfNewNode(source)
        values = self.storage.get(key, None)
        if values is None:
            return self.rpc_find_node(sender, nodeId, key)
        return {"values": values}

    def callFindNode(self, nodeToAsk, nodeToFind):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.find_node(address, self.sourceNode.id, nodeToFind.id)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="find_node")

    def callGetPeers(self, nodeToAsk, key):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.get_peers(address, self.sourceNode.id, key.id)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="get_peers")

    def callPing(self, nodeToAsk):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.ping(address, self.sourceNode.id)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="ping")

    def callAnnouncePeer(self, nodeToAsk, key, value, token):
        address = (nodeToAsk.ip, nodeToAsk.port)
        d = self.announce_peer(address, self.sourceNode.id, key, value, token)
        return d.addCallback(self.handleCallResponse, nodeToAsk, responseMessage="announce_peer")

    # BitTorrent protocol messages implementation
    def ping(self, address, nodeId):
        return self.sendMessage(address, {"y": "q", "q": "ping", "a": {"id": nodeId}})

    def find_node(self, address, nodeId, targetId):
        return self.sendMessage(address, {"y": "q", "q": "find_node", "a": {"id": nodeId, "target": targetId}})

    def get_peers(self, address, nodeId, info_hash):
        return self.sendMessage(address, {"y": "q", "q": "get_peers", "a": {"id": nodeId, "info_hash": info_hash}})

    def announce_peer(self, address, nodeId, info_hash, port, token):
        return self.sendMessage(address, {"y": "q", "q": "announce_peer",
                                          "a": {"id": nodeId, "implied_port": 0, "info_hash": info_hash, "port": port,
                                                "token": token}})

    def welcomeIfNewNode(self, node):
        """
        Given a new node, send it all the keys/values it should be storing,
        then add it to the routing table.

        @param node: A new node that just joined (or that we just found out
        about).

        Process:
        For each key in storage, get k closest nodes.  If newnode is closer
        than the furtherst in that list, and the node for this server
        is closer than the closest in that list, then store the key/value
        on the new node (per section 2.5 of the paper)
        """
        if self.router.isNewNode(node):
            ds = []
            for key, value in self.storage.iteritems():
                keynode = Node(key)
                neighbors = self.router.findNeighbors(keynode)
                if len(neighbors) > 0:
                    newNodeClose = node.distanceTo(keynode) < neighbors[-1].distanceTo(keynode)
                    thisNodeClosest = self.sourceNode.distanceTo(keynode) < neighbors[0].distanceTo(keynode)
                if len(neighbors) == 0 or (newNodeClose and thisNodeClosest):
                    ds.append(self.callAnnouncePeer(node, key, value))
            self.router.addContact(node)
            return defer.gatherResults(ds)

    def handleCallResponse(self, result, node, responseMessage):
        """
        If we get a response, add the node to the routing table.  If
        we get no response, make sure it's removed from the routing table.
        """
        if result[0]:
            self.log.info("got response from %s, adding to router" % node)
            self.welcomeIfNewNode(node)
        else:
            self.log.debug("no response from %s, removing from router" % node)
            self.router.removeContact(node)
        return result
