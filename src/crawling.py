from collections import Counter

from log import Logger
from utils import deferred_dict, decode_nodes, decode_values
from node import Node, NodeHeap


class SpiderCrawl(object):
    """
    Crawl the network and look for given 160-bit keys.
    """

    def __init__(self, protocol, node, peers, ksize, alpha):
        """
        Create a new C{SpiderCrawl}er.

        Args:
            protocol: A :class:`~kademlia.protocol.KademliaProtocol` instance.
            node: A :class:`~kademlia.node.Node` representing the key we're looking for
            peers: A list of :class:`~kademlia.node.Node` instances that provide the entry point for the network
            ksize: The value for k based on the paper
            alpha: The value for alpha based on the paper
        """
        self.protocol = protocol
        self.ksize = ksize
        self.alpha = alpha
        self.node = node
        self.nearest = NodeHeap(self.node, self.ksize)
        self.lastIDsCrawled = []
        self.log = Logger(system=self)
        self.log.info("creating spider with peers: %s" % peers)
        self.nearest.push(peers)

    def _find(self, rpcmethod):
        """
        Get either a value or list of nodes.

        Args:
            rpcmethod: The protocol's callfindValue or callFindNode.

        The process:
          1. calls find_* to current ALPHA nearest not already queried nodes,
             adding results to current nearest list of k nodes.
          2. current nearest list needs to keep track of who has been queried already
             sort by nearest, keep KSIZE
          3. if list is same as last time, next call should be to everyone not
             yet queried
          4. repeat, unless nearest list has all been queried, then ur done
        """
        self.log.info("crawling with nearest: %s" % str(tuple(self.nearest)))
        count = self.alpha
        if self.nearest.getIDs() == self.lastIDsCrawled:
            self.log.info("last iteration same as current - checking all in list now")
            count = len(self.nearest)
        self.lastIDsCrawled = self.nearest.getIDs()

        ds = {}
        for peer in self.nearest.getUncontacted()[:count]:
            ds[peer.id] = rpcmethod(peer, self.node)
            self.nearest.markContacted(peer)
        return deferred_dict(ds).addCallback(self._nodesFound)


class ValueSpiderCrawl(SpiderCrawl):
    def __init__(self, protocol, node, peers, ksize, alpha):
        SpiderCrawl.__init__(self, protocol, node, peers, ksize, alpha)
        # keep track of the single nearest node without value - per
        # section 2.3 so we can set the key there if found
        self.nearestWithoutValue = NodeHeap(self.node, 1)

    def find(self):
        """
        Find either the closest nodes or the value requested.
        """
        return self._find(self.protocol.callGetPeers)

    def _nodesFound(self, responses):
        """
        Handle the result of an iteration in _find.
        """
        toremove = []
        foundValues = []

        for peerid, response in responses.items():
            response = RPCFindResponse(response)

            if not response.happened():
                toremove.append(peerid)
            elif response.hasValues():
                foundValues.extend(response.getValues())
            else:
                peer = self.nearest.getNodeById(peerid)
                self.nearestWithoutValue.push(peer)
                self.nearest.push(response.getNodeList())

        self.nearest.remove(toremove)

        if len(foundValues) > 0:
            return list(set(foundValues))  # return unique list of values
        elif self.nearest.allBeenContacted():
            return None  # not found!
        else:
            return self.find()


class NodeSpiderCrawl(SpiderCrawl):
    def find(self):
        """
        Find the closest nodes.
        """
        return self._find(self.protocol.callFindNode)

    def _nodesFound(self, responses):
        """
        Handle the result of an iteration in _find.
        """
        toremove = []
        for peerid, response in responses.items():
            response = RPCFindResponse(response)
            if not response.happened():
                toremove.append(peerid)
            else:
                self.nearest.push(response.getNodeList())
        self.nearest.remove(toremove)

        if self.nearest.allBeenContacted():
            return list(self.nearest)
        return self.find()


class RPCFindResponse(object):
    def __init__(self, response):
        """
        A wrapper for the result of a RPC find.

        Args:
            response: This will be a tuple of (<response received>, <value>)
                      where <value> will be a list of tuples if not found or
                      a dictionary of {'value': v} where v is the value desired
        """
        self.response = response

    def happened(self):
        """
        Did the other host actually respond?
        """
        return self.response[0]

    def hasValues(self):
        return isinstance(self.response[1], dict) and "values" in self.response[1] and len(
            self.response[1]["values"]) > 0

    def getValues(self):
        return decode_values(self.response[1]["values"])

    def getToken(self):
        return self.response[1]["token"]

    def getNodeList(self):
        """
        Get the node list in the response.  If there's no value, this should
        be set.
        """
        nodelist = decode_nodes(self.response[1]["nodes"]) or []
        return [Node(*nodeple) for nodeple in nodelist]
