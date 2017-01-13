from gameserver.game import Game
from gameserver.database import db

db_session = db.session
game = Game()

def create_network():
    return 'do some magic!'

def get_network():
    return game.get_network(), 200
