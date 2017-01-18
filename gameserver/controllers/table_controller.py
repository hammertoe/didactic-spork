from gameserver.game import Game
from gameserver.database import db

from players_controller import player_to_dict

db_session = db.session
game = Game()

def table_to_dict(table):
    return dict(id=table.id,
                name=table.name,
                players=[ player_to_dict(p) for p in table.players ],
                network=game.get_network(table.players),
                )


def create_table(table = None):
    table = game.create_table(table['name'])
    db_session.commit()
    return table_to_dict(table), 201

def Xget_table(id):
    table = game.get_table(id)
    if not table:
        return "Table not found", 404
    else:
        return table_to_dict(table), 200

def get_table(id):

    table = game.get_table(id)
    if not table:
        return "Table not found", 404
    else:
        data = { 'nodes': [],
                 'edges': [],
                 }        
        nset = set()
        nodes = tuple(game.get_network2(table.players))
        for n in nodes:
            data['nodes'].append(
                dict(id=n.id,
                     label=n.name,
                     )
                )
            nset.add(n.id)

        for n in nodes:
            edges = n.higher_edges
            for e in edges:
                if n.id in nset and e.lower_node.id in nset:
                    data['edges'].append(
                        {'from': e.lower_node.id,
                         'to': n.id,
                         'id':e.id,
                         }
                        )
        return data

def get_tables():
    tables = game.get_tables()
    return [ dict(id=t.id,name=t.name) for t in tables ], 200
