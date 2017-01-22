from decorator import decorator

from flask import request, abort

from gameserver.game import Game
from gameserver.database import db

db_session = db.session
game = Game()

@decorator
def require_user_key(f, *args, **kw):
    key = request.headers.get('X-USER-KEY')
    player_id = request.view_args['player_id']
    player = game.get_player(player_id)
    if not (key and player.token == key):
        abort(401)

    return f(*args, **kw)

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

def get_player(player_id):
    player = game.get_player(player_id)
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

@require_user_key
def update_player(player_id, player=None):
    """
    Updates a player
    """
    if not player:
        return 500
    p = game.get_player(player_id)
    if not p:
        return "Player not found", 404

    for key, value in player.items():
        if key == 'table':
            table = game.get_table(value)
            p.table = table

    db_session.commit()
    return player_to_dict(p), 200

@require_user_key
def set_funding(player_id, funding = None):
    try:
        game.set_funding(player_id, funding)
        db_session.commit()
        return game.get_funding(player_id), 200
    except ValueError:
        return "Sum of funds exceeds max allowed", 400

@require_user_key
def get_funding(player_id):
    funds = game.get_funding(player_id)

    return funds, 200

@require_user_key
def get_policy_offer(player_id, policy_id):
    try:
        offer = game.offer_policy(player_id, policy_id, 20000)
        return offer, 200
    except ValueError, e:
        return str(e), 400
    
@require_user_key
def buy_policy(player_id, offer):
    try:
        buy = game.buy_policy(player_id, offer)
        db_session.commit()
        return buy, 200
    except ValueError, e:
        return str(e), 400
   
