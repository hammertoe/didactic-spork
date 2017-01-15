from gameserver.game import Game
from gameserver.database import db

db_session = db.session
game = Game()

def create_network(network):
    game.create_network(network)
    return None, 201

def get_network():
    return game.get_network(), 200
