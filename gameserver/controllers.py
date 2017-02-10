from decorator import decorator
from flask import request, abort

from gameserver.game import Game
from gameserver.database import db
from gameserver.utils import node_to_dict
from hashlib import sha1
from time import asctime

from gameserver.models import Player, Goal, Edge, Policy
from sqlalchemy.orm import joinedload, noload

try:
    from google.appengine.api import memcache
except ImportError:
    from gameserver.utils import fake_memcache as memcache

db_session = db.session
game = Game()

def app_version():
    return dict(version="0.13")

@decorator
def require_user_key(f, *args, **kw):
    key = request.headers.get('X-USER-KEY')
    player_id = request.view_args['player_id']
    mkey = "{}-player-token".format(player_id)
    token = memcache.get(mkey)
    if token is None or token != key:
        player = game.get_player(player_id)
        if not player:
            abort(404)
        if not (key and player.token == key):
            abort(401)
        memcache.add(mkey, player.token, 3600)

    return f(*args, **kw)

@decorator
def require_api_key(f, *args, **kw):
    key = request.headers.get('X-API-KEY')
    mkey = "{}-client-key".format(key)
    client_name = memcache.get(mkey)
    if client_name is None:
        client_name = game.validate_api_key(key)
        if not (key and client_name is not None):
            abort(401)
        memcache.add(mkey, client_name, 3600)

    return f(*args, **kw)

@require_api_key
def do_tick():
    return _do_tick()

def _do_tick():
    game.tick()

    network =  game.get_network()
    network['goals'] = [ node_to_dict(g) for g in network['goals'] ]
    network['policies'] = [ node_to_dict(p) for p in network['policies'] ]
    network['generated'] = asctime()
    memcache.set(key="network", value=network, time=120)

    db_session.commit()
    return None, 200

@require_api_key
def clear_players():
    game.clear_players()

    db_session.commit()
    return None, 200

@require_api_key
def league_table():
    return _league_table()

def _league_table():
    res = memcache.get('league_table')
    if res is None:
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
        memcache.set('league_table', res, 30)

    return dict(rows=res)

@require_api_key
def create_network(network):
    game.create_network(network)

    db_session.commit()
    return None, 201

@require_api_key
def get_network():
    network =  memcache.get("network")
    if network is None:
        network =  game.get_network()
        network['goals'] = [ node_to_dict(g) for g in network['goals'] ]
        network['policies'] = [ node_to_dict(p) for p in network['policies'] ]
        network['generated'] = asctime()
        return network, 200, {'x-cache': 'miss'}

    return network, 200, {'x-cache': 'hit'}

@require_api_key
def update_network(network):
    game.update_network(network)
    network =  game.get_network()
    network['goals'] = [ node_to_dict(g) for g in network['goals'] ]
    network['policies'] = [ node_to_dict(p) for p in network['policies'] ]

    db_session.commit()
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

#@require_api_key
def get_player(player_id):
    mkey = "{}-player".format(player_id)
    data = memcache.get(mkey)
    if data is None:
        player = db_session.query(Player).filter(Player.id == player_id).options(
            joinedload(Player.goal.of_type(Goal)),
            joinedload(Player.lower_edges.of_type(Edge)).joinedload(Edge.higher_node.of_type(Policy))).one_or_none()
        if not player:
            return "Player not found", 404
        data = player_to_dict(player)
        memcache.add(mkey, data, 3)
    return data, 200


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
def set_player_table(player_id, table_id):
    """
    Adds / Updates the table a player is on
    """
    p = game.get_player(player_id)
    if not p:
        return "Player not found", 404

    t = game.get_table(table_id)
    if not t:
        return "Table not found", 404

    p.table = t

    db_session.commit()
    return player_to_dict(p), 200

@require_api_key
@require_user_key
def delete_player_table(player_id, table_id):
    """
    Adds / Updates the table a player is on
    """
    p = game.get_player(player_id)
    if not p:
        return "Player not found", 404

    t = game.get_table(table_id)
    if not t:
        return "Table not found", 404

    p.table = None

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
   
@require_api_key
def create_table(table = None):
    table = game.create_table(table['name'])
    db_session.commit()
    return generate_table_data(table), 201

@require_api_key
def clear_table(id):
    table = game.get_table(id)
    if not table:
        return "Table not found", 404

    table.players = []

    db_session.commit()

    return "table cleared", 200

@require_api_key
def get_table(id):
    mkey = "{}-table".format(id)
    data = memcache.get(mkey)
    if data is None:
        table = game.get_table(id)
        if not table:
            return "Table not found", 404

        data = generate_table_data(table)
        memcache.add(mkey, data, 3)

    return data, 200

def generate_table_data(table):
    name = table.name
    players = table.players
    network = game.get_network(players)

    nodes = {}
    links = []

    for n in players:
        nodes[n.id] = {'id': n.id,
                       'name': n.name,
                       'group': 8,
                       'resources': "{:.2f}".format(n.balance),
                       }
        for l in n.lower_edges:
            links.append({'source': n.id,
                          'target': l.higher_node.id,
                          'weight': float("{:.2f}".format(l.weight)),
                          })
    for n in network['policies']:
        nodes[n.id] = {'id': n.id,
                       'name': n.name,
                       'group': 9,
                       'active': n.active and True or False,
                       'active_level': "{:.2f}".format(n.active_level),
                       'active_percent': "{:.2f}".format(n.active_percent),
                       'resources': "{:.2f}".format(n.balance),
                       }
        for l in n.lower_edges:
            links.append({'source': n.id,
                          'target': l.higher_node.id,
                          'weight': float("{:.2f}".format(l.weight)),
                          })

    for i,n in enumerate(network['goals'], start=1):
        nodes[n.id] = {'id': n.id,
                       'name': n.name,
                       'group': i,
                       'active': n.active and True or False,
                       'active_level': "{:.2f}".format(n.active_level),
                       'active_percent': "{:.2f}".format(n.active_percent),
                       'resources': "{:.2f}".format(n.balance),
                       }

    links = [ l for l in links 
              if l['source'] in nodes
              and l['target'] in nodes
              ]

    network =  {'nodes': nodes.values(), 'links': links}
    players_dict = [ player_to_dict(p) for p in players ]

    checksum = sha1()
    for link in sorted(links, key=lambda x: x['source']):
        checksum.update(link['source'])
        checksum.update(link['target'])

    return dict(id=table.id,
                name=name,
                players=players_dict,
                network=network,
                layout_checksum=checksum.hexdigest(),
                )

@require_api_key
def get_tables():
    tables = game.get_tables()
    return [ dict(id=t.id,name=t.name) for t in tables ], 200
