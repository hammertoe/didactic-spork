#import random

#class lcg(random.Random):
#    def __init__( self, seed=1 ):
#        self.state = seed

#    def random(self):
#        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
#        return self.state

import random as orig_random

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
