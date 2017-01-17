from gameserver.game import Game
from gameserver.database import db
from gameserver.utils import node_to_dict

db_session = db.session
game = Game()


def Xnode_to_dict(node):
    return dict(id=node.id,
                name=node.name,
                balance=node.balance,
                activation_amount=node.activation,
                max_amount=node.max_level,
                leakage=node.leak,
                )

def wallet_to_dict(wallet):
    return dict(owner=wallet.owner_id,
                location=wallet.location_id,
                balance=wallet.balance,
                )

def create_network(network):
    game.create_network(network)
    return None, 201

def get_network():
    return game.get_network(), 200

def get_node(id):
    node = game.get_node(id)
    if not node:
        return "Node not found", 404
    return node_to_dict(node), 200

def get_wallets(id):
    wallets = game.get_wallets_by_location(id)
    if not wallets:
        return "No wallets found", 404
    return [ wallet_to_dict(w) for w in wallets ], 200
    
