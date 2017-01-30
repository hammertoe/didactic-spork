from decorator import decorator
from flask import request, abort

from gameserver.game import Game
from gameserver.database import db
from gameserver.utils import node_to_dict

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

@decorator
def require_api_key(f, *args, **kw):
    key = request.headers.get('X-API-KEY')
    client_name = game.validate_api_key(key)
    if not (key and client_name is not None):
        abort(401)

    return f(*args, **kw)

#@require_api_key
def do_tick():
    game.tick()
    db_session.commit()
    return None, 200

@require_api_key
def league_table():
    res = []
    top = game.top_players()
    for t in top:

        if not t.goal:
            continue 

        r = {'id': t.id,
             'name': t.name,
             'goal': t.goal.name,
             'goal_contribution': "{:.2f}".format(t.goal_funded),
             'goal_total': "{:.2f}".format(t.goal.balance),
             }
        res.append(r)

    return dict(rows=res)

@require_api_key
def create_network(network):
    game.create_network(network)
    return None, 201

@require_api_key
def get_network():
    network =  game.get_network()
    network['goals'] = [ node_to_dict(g) for g in network['goals'] ]
    network['policies'] = [ node_to_dict(p) for p in network['policies'] ]

    return network, 200

@require_api_key
def get_node(id):
    node = game.get_node(id)
    if not node:
        return "Node not found", 404
    return node_to_dict(node), 200

@require_api_key
def get_wallets(id):
    wallet = game.get_wallets_by_location(id)
    if not wallet:
        return "No wallet found", 404
    res = []
    for player_id, amount in wallet.items():
        res.append({'owner': player_id,
                    'location': id,
                    'balance': amount,
                    })

    return res, 200
    
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

@require_api_key
def get_player(player_id):
    player = game.get_player(player_id)
    if not player:
        return "Player not found", 404
    return player_to_dict(player), 200


@require_api_key
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

@require_api_key
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

@require_api_key
@require_user_key
def set_funding(player_id, funding = None):
    try:
        game.set_funding(player_id, funding)
        db_session.commit()
        return game.get_funding(player_id), 200
    except ValueError:
        return "Sum of funds exceeds max allowed", 400

@require_api_key
@require_user_key
def get_funding(player_id):
    funds = game.get_funding(player_id)

    return funds, 200

@require_api_key
@require_user_key
def get_policy_offer(player_id, policy_id, price=None):
    if price == None:
        price = game.default_offer_price
    try:
        offer = game.offer_policy(player_id, policy_id, price)
        return offer, 200
    except ValueError, e:
        return str(e), 400
    
@require_api_key
@require_user_key
def buy_policy(player_id, offer):
    try:
        buy = game.buy_policy(player_id, offer)
        db_session.commit()
        return buy, 200
    except ValueError, e:
        return str(e), 400
   
def convert_to_d3(players, network):
    nodes = {}
    links = []

    for n in players:
        nodes[n['id']] = {'id': n['id'],
                          'name': n['name'],
                          'group': 1,
                          'resources': n['balance'],
                          }
    for n in network['policies']:
        nodes[n['id']] = {'id': n['id'],
                          'name': n['name'],
                          'group': 2,
                          'resources': n['balance'],
                          }
        for l in n['connections']:
            links.append({'source': l['from_id'],
                          'target': l['to_id'],
                          'value': l['weight'],
                          })
    for n in network['goals']:
        nodes[n['id']] = {'id': n['id'],
                          'name': n['name'],
                          'group': 3,
                          'resources': n['balance'],
                          }
        for l in n['connections']:
            links.append({'source': l['from_id'],
                          'target': l['to_id'],
                          'value': l['weight'],
                          })

    links = [ l for l in links 
              if l['source'] in nodes
              and l['target'] in nodes
              ]

    return {'nodes': nodes.values(), 'links': links}

def table_to_dict(table):
    players = [ player_to_dict(p) for p in table.players ]
    return dict(id=table.id,
                name=table.name,
                players=players,
                network=convert_to_d3(players, game.get_network(table.players)),
                )


@require_api_key
def create_table(table = None):
    table = game.create_table(table['name'])
    db_session.commit()
    return table_to_dict(table), 201

@require_api_key
def get_table(id):
    table = game.get_table(id)
    if not table:
        return "Table not found", 404

    name = table.name
    players = table.players
    network = game.get_network(players)

    nodes = {}
    links = []

    for n in players:
        nodes[n.id] = {'id': n.id,
                       'name': n.name,
                       'group': 1,
                       'resources': "{:.2f}".format(n.balance),
                       }
    for n in network['policies']:
        nodes[n.id] = {'id': n.id,
                       'name': n.name,
                       'group': 2,
                       'active': n.active and True or False,
                       'resources': "{:.2f}".format(n.balance),
                       }
        for l in n.lower_edges:
            links.append({'source': n.id,
                          'target': l.higher_node.id,
                          'weight': "{:.2f}".format(l.weight),
                          })
    for n in network['goals']:
        nodes[n.id] = {'id': n.id,
                       'name': n.name,
                       'group': 3,
                       'resources': "{:.2f}".format(n.balance),
                       }

    links = [ l for l in links 
              if l['source'] in nodes
              and l['target'] in nodes
              ]

    return {'nodes': nodes.values(), 'links': links}, 200

@require_api_key
def get_tables():
    tables = game.get_tables()
    return [ dict(id=t.id,name=t.name) for t in tables ], 200
