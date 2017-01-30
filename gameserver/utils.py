import random as orig_random
from decorator import decorator
import binascii
import struct
import hashlib

from gameserver.database import db

db_session = db.session

random = orig_random.Random()
random.seed()

def node_to_dict(node):
    connections = []
    for edge in node.lower_edges:
        connections.append(
            {"from_id": edge.higher_node.id,
             "to_id": node.id,
             "weight": "{:.2f}".format(edge.weight),
             }
            )

    data = {"id": node.id,
            "name": node.name,
            "leakage": "{:.2f}".format(node.leak),
            "max_amount": "{:.2f}".format(node.max_level),
            "activation_amount": "{:.2f}".format(node.activation),
            "balance": "{:.2f}".format(node.balance),
            "connections": connections
            }
    
    return data


def pack_amount(value):
    return binascii.hexlify(struct.pack("f", value)).decode('ascii')

def unpack_amount(value):
    return struct.unpack("f", binascii.unhexlify(value))[0]

def checksum(seller_id, policy_id, price, salt):
    input = "{}{}{}{}".format(seller_id, policy_id, pack_amount(price), salt)
    return hashlib.sha1(input).hexdigest()
