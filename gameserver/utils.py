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
            {"id": edge.id,
             "to_id": edge.higher_node.id,
             "from_id": node.id,
             "weight": float("{:.2f}".format(edge.weight)),
             }
            )

    data = {"id": node.id,
            "name": node.name,
            "short_name": node.short_name,
            "leakage": float("{:.2f}".format(node.leak)),
            "max_amount": float("{:.2f}".format(node.max_level)),
            "activation_amount": float("{:.2f}".format(node.activation)),
            "active_level": float("{:.2f}".format(node.active_level)),
            "balance": float("{:.2f}".format(node.balance)),
            "connections": connections
            }
    if node.group is not None:
        data["group"] = int(node.group)
    
    return data

def update_node_from_dict(node, d):
    node.id = d['id']
    node.name = d['name']
    if d.get('short_name') is not None: 
        node.short_name = d['short_name']
    if d.get('group') is not None:
        node.group = int(d['group'])
    node.leak = float(d['leakage'])
    node.max_level = float(d['max_amount'])
    node.activation = float(d['activation_amount'])


def pack_amount(value):
    return binascii.hexlify(struct.pack("f", value)).decode('ascii')

def unpack_amount(value):
    return struct.unpack("f", binascii.unhexlify(value))[0]

def checksum(seller_id, policy_id, price, salt):
    input = "{}{}{}{}".format(seller_id, policy_id, pack_amount(price), salt)
    return hashlib.sha1(input).hexdigest()
