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
                goal=player.goal.id if player.goal else None,
                policies=[x.id for x in player.children()],
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
    try:
        game.set_funding(id, funding)
        db_session.commit()
        return None, 200
    except ValueError:
        return "Sum of funds exceeds max allowed", 400

def get_funding(id):
    funds = game.get_funding(id)

    return funds, 200

