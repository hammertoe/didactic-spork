from gameserver.game import Game

from gameserver.database import db

db_session = db.session

game = Game()

def get_player(id):
    player = game.get_player(id)
    if not player:
        return None, 404
    return dict(id=player.id,
                name=player.name,
                goal='',
                policies=[],
                table=None,
                ), 200

def create_player(player=None):
    """
    Creates a new game player.
    """
    if player:
        player = game.create_player(player['name'])
        db_session.commit()
        return dict(id=player.id,
                    token=player.token), 201
    else:
        return 500

def set_funding(id, funding = None):
    return 'do some magic!'
