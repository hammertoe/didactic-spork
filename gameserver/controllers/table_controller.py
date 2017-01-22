from gameserver.game import Game
from gameserver.database import db

from players_controller import player_to_dict

db_session = db.session
game = Game()


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


def create_table(table = None):
    table = game.create_table(table['name'])
    db_session.commit()
    return table_to_dict(table), 201

def get_table(id):
    table = game.get_table(id)
    if not table:
        return "Table not found", 404
    else:
        return table_to_dict(table), 200

def get_tables():
    tables = game.get_tables()
    return [ dict(id=t.id,name=t.name) for t in tables ], 200
