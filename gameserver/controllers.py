import logging.config
from decorator import decorator
from flask import request, abort

from gameserver.game import Game
from gameserver.database import db
from gameserver.utils import node_to_dict, player_to_dict, node_to_dict2, edge_to_dict, edges_to_checksum, player_to_league_dict, message_to_dict, player_to_funding_dict
from gameserver.settings import APP_VERSION
from hashlib import sha1
from time import asctime, time
import dateutil.parser
from datetime import datetime

from gameserver.models import Player, Goal, Edge, Policy, Table
from sqlalchemy.orm import joinedload, noload

log = logging.getLogger(__name__)

try:
    from google.appengine.api import memcache
except ImportError:
    from gameserver.utils import fake_memcache as memcache

db_session = db.session
game = Game()

def app_version():
    return dict(version=APP_VERSION)

@decorator
def cached(f, *args, **kw):
    cache_key = request.path
    res = memcache.get(cache_key)
    if res:
        return res

    res = f(*args, **kw)
    memcache.set(cache_key, res, 60)
    return res

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
    if request.headers.get('X-AppEngine-TaskName'):
        return f(*args, **kw)

    key = request.headers.get('X-API-KEY')
    mkey = "{}-client-key".format(key)
    client_name = memcache.get(mkey)
    if client_name is None:
        client_name = game.validate_api_key(key)
        if not (key and client_name is not None):
            abort(401)
        memcache.add(mkey, client_name, 3600)

    return f(*args, **kw)

@decorator
def invalidates_player(f, *args, **kw):
    ret = f(*args, **kw)

    player_id = args[0]
    data = _get_player(player_id)
    if data:
        cache_key = '/v1/players/{}'.format(player_id)
        data = (data, 200, {'x-cache':'hit'})
        memcache.set(cache_key, data, 60)

    return ret

@require_api_key
def do_tick():
    _do_tick()
    t1 = time()
    db_session.commit()
    t2 = time()
    log.debug('session commit {:.2f}'.format(t2-t1))

    return None, 200

def _do_tick():
    t1 = time()
    to_cache = {}
    network = {'goals': [],
               'policies': []}
    players = []
    player_dicts = []
    player_fundings = []
    # calculate metadata
    to_cache['/v1/game'] = (_get_metadata(), 200, {'x-cache':'hit'})
    is_passed_year_end = game.is_passed_year_end()
    tables = game.get_tables()
    # tick the game and get the resultant nodes
    game_nodes = game.tick()
    t2 = time()
    log.debug('initial tick part {:.2f}'.format(t2-t1))
    for node in game_nodes:
        # cache each node, incl players
        key = "/v1/network/{}".format(node.id)
        if isinstance(node, Goal):
            d = node_to_dict(node)
            network['goals'].append(d)
        elif isinstance(node, Policy):
            d = node_to_dict(node)
            network['policies'].append(d)
        elif isinstance(node, Player):
            key = "/v1/players/{}".format(node.id)
            players.append(node)
            d = player_to_dict(node)
            player_dicts.append(player_to_league_dict(node))
            player_fundings.append(player_to_funding_dict(node))
            node.network = game.get_network_for_player(node)
        to_cache[key] = (d, 200, {'x-cache':'hit'})

    t3 = time()
    log.debug('pre-cache nodes part {:.2f}'.format(t3-t2))
    # cache the network
    network['generated'] = asctime()
    to_cache['/v1/network/'] = (network, 200, {'x-cache':'hit'})
    # calculate new league table
    player_dicts.sort(key=lambda x: x['goal_contribution'], reverse=True)
    league_table = dict(rows=player_dicts[:50])
    to_cache['/v1/game/league_table'] = (league_table, 200, {'x-cache':'hit'})
    # calculate player fundings
    to_cache['/v1/game/player_fundings'] = (player_fundings, 200, {'x-cache':'hit'})

    t4 = time()
    log.debug('pre-cache network part {:.2f}'.format(t4-t3))

    # calculate the new player tables
    for table in tables:
        players = table.players
        if players:
            # there are players on the table so collect the nodes and edges
            # from all players
            nodes = set()
            edges = set()
            for player in players:
                nodes.update(player.network['nodes'])
                edges.update(player.network['edges'])
        else:
            # get all game nodes that are Policies or Goals
            nodes = [ n for n in game_nodes if isinstance(n, Policy) or isinstance(n, Goal) ]
            # get all the edges from those nodes
            edges = [ n.lower_edges for n in nodes ]
            # flatten the list of edges
            edges = [item for sublist in edges for item in sublist]

        # convert the lists into lists of dicts for json
        nlist = [ node_to_dict2(n) for n in nodes ]
        elist = [ edge_to_dict(e) for e in edges ]
        plist = [ player_to_dict(p) for p in table.players ]

        # constuct the final object
        data = dict(id=table.id,
                    name=table.name,
                    players=plist,
                    network={'nodes': nlist, 'links': elist},
                    layout_checksum=edges_to_checksum(elist),
                    )

        # put it in the cache
        key = "/v1/tables/{}".format(table.id)
        to_cache[key] = (data, 200, {'x-cache':'hit'}) 

    t5 = time()
    log.debug('pre-cache tables part {:.2f}'.format(t5-t4))

    # send everything to the cache
    memcache.set_multi(to_cache, time=60)

    t6 = time()
    log.debug('send all the cache part {:.2f}'.format(t6-t5))

    # if we are passed the next year start then replenish funds
    if is_passed_year_end:
        year = game.current_year()
        game.start(year+1)
        game.do_replenish_budget()

    t7 = time()
    log.debug('total tick {:.2f}'.format(t7-t6))

@require_api_key
def clear_players():
    game.clear_players()

    db_session.commit()
    return None, 200

@require_api_key
@cached
def league_table():
    res = _league_table()
    return res, 200

@require_api_key
@cached
def player_fundings():
    return "Not computed yet", 503, {'Retry-After': 3}


def _league_table():
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
    game.clear_network()
    game.create_network(network)

    db_session.commit()
    return _get_network(), 201

@require_api_key
@cached
def get_network():
    return _get_network(), 200

def _get_network():
    network =  game.get_network()
    network['goals'] = [ node_to_dict(g) for g in network['goals'] ]
    network['policies'] = [ node_to_dict(p) for p in network['policies'] ]
    network['generated'] = asctime()
    return network

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
                    'balance': float("{:.2f}".format(amount)),
                    })

    return res, 200
    
@require_api_key
@cached
def get_player(player_id):
    player = _get_player(player_id)
    if player:
        return player, 200
    else:
        return "Player not found", 404

def _get_player(player_id):
    player = db_session.query(Player).filter(Player.id == player_id).options(
        joinedload(Player.goal.of_type(Goal)),
        joinedload(Player.lower_edges.of_type(Edge)).joinedload(Edge.higher_node.of_type(Policy))).one_or_none()
    if player:
        data = player_to_dict(player)
        return data
    else:
        return None


@require_api_key
def create_player(player=None):
    """
    Creates a new game player.
    """
    if player:
        game_id = player.get('game_id')
        if game_id != game.settings.game_id:
            return "Game not found", 404
        player = game.create_player(player['name'])
        db_session.commit()
        d = player_to_dict(player)
        d['token'] = player.token
        return d, 201
    else:
        return "error", 500

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
    log.info('get_policy_offer start {}'.format(id(db_session())))
    if price == None:
        price = game.default_offer_price
    try:
        offer = game.offer_policy(player_id, policy_id, price)
        if offer is None:
            return "Player of policy not found", 404
        log.info('get_policy_offer end')
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
@require_user_key
@invalidates_player
def claim_budget(player_id):
    try:
        player = game.get_player(player_id)
        if player is None:
            return "Player not found", 404
        player.claim_budget()
        db_session.commit()
        return "budget claimed", 200
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
@cached
def get_table(id):
    table = game.get_table(id)
    if not table:
        return "Table not found", 404

    data = generate_table_data(table)
    return data, 200

@require_api_key
def delete_table(id):
    if game.delete_table(id):
        db_session.commit()
        return "Table deleted", 200
    else:
        return "Table not found", 404


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
        links.extend([edge_to_dict(e) for e in n.lower_edges])

    for n in network['policies']:
        data = node_to_dict2(n)
        data['group'] = 9
        nodes[n.id] = data
        links.extend([edge_to_dict(e) for e in n.lower_edges])

    for n in network['goals']:
        data = node_to_dict2(n)
        nodes[n.id] = data

    links = [ l for l in links 
              if l['source'] in nodes
              and l['target'] in nodes
              ]

    network =  {'nodes': nodes.values(), 'links': links}
    players_dict = [ player_to_dict(p) for p in players ]

    return dict(id=table.id,
                name=name,
                players=players_dict,
                network=network,
                layout_checksum=edges_to_checksum(links),
                )

@require_api_key
def get_tables():
    tables = game.get_tables()
    return [ dict(id=t.id,name=t.name) for t in tables ], 200

@require_api_key
@cached
def get_metadata():
    return _get_metadata(), 200

def _get_metadata():
    settings = game.settings
    return {'game_year': settings.current_game_year,
            'game_year_start': settings.current_game_year_start,
            'next_game_year': settings.current_game_year+1 if settings.current_game_year else None,
            'next_game_year_start': settings.next_game_year_start if settings.next_game_year_start else None,
            'version': APP_VERSION,
            'total_players_inflow': game.total_players_inflow,
            'total_active_players_inflow': game.total_active_players_inflow,
            }

# move to game class
@require_api_key
def stop_game():
    year = game.stop()
    db_session.commit()
    return "game stopped at year {}".format(year), 200

@require_api_key
def start_game(params):
    year = game.start(params['year'])
    game.do_replenish_budget()
    db_session.commit()
    return "game started, year {}".format(year), 200

@require_api_key
def set_messages(messages):
    game.clear_messages()
    for m in messages['budgets']:
        ts = dateutil.parser.parse(m['time']).replace(tzinfo=None)
        game.add_message(ts, "budget", m['message'])
    for m in messages['events']:
        ts = dateutil.parser.parse(m['time']).replace(tzinfo=None)
        game.add_message(ts, "event", m['message'])
    db_session.commit()

@require_api_key
@cached
def get_messages():
    budgets = []
    events = []
    for m in sorted(game.get_messages(), key=lambda x: x.timestamp):
        data = message_to_dict(m)
        if m.type == 'budget':
            budgets.append(data)
        elif m.type == 'event':
            events.append(data)

    return dict(budgets=budgets, events=events), 200
