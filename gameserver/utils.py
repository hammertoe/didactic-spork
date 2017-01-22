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
    for edge in node.higher_edges:
        connections.append(
            {"from_id": edge.lower_node.id,
             "to_id": node.id,
             "weight": edge.weight,
             }
            )

    data = {"id": node.id,
            "name": node.name,
            "leakage": node.leak,
            "max_amount": node.max_level,
            "activation_amount": node.activation,
            "balance": node.balance,
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
