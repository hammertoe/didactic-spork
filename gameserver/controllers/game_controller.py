from gameserver.game import Game
from gameserver.database import db

db_session = db.session
game = Game()

def do_tick():
    game.tick()
    db_session.commit()
    return None, 200

