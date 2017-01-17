from gameserver.game import Game
from gameserver.database import db

db_session = db.session
game = Game()

def player_to_dict(player):
    if player.goal:
        goal = dict(id=player.goal.id,
                    name=player.goal.name)
    else:
        goal = None

    policies = [dict(id=x.id, name=x.name) for x in player.children()]

    return dict(id=player.id,
                name=player.name,
                balance=player.balance,
                goal=goal,
                policies=policies,
                table=player.table_id,
                )

def get_player(id):
    player = game.get_player(id)
    if not player:
        return "Player not found", 404
    return player_to_dict(player), 200


def create_player(player=None):
    """
    Creates a new game player.
    """
    if player:
        player = game.create_player(player['name'])
        db_session.commit()
        d = player_to_dict(player)
        d['token'] = player.token
        return d, 201
    else:
        return 500

def set_funding(id, funding = None):
    try:
        game.set_funding(id, funding)
        db_session.commit()
        return game.get_funding(id), 200
    except ValueError:
        return "Sum of funds exceeds max allowed", 400

def get_funding(id):
    funds = game.get_funding(id)

    return funds, 200

