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
    return table_to_dict(table), 201

def get_table(id):
    table = game.get_table(id)
    if not table:
        return "Table not found", 404
    else:
        return table_to_dict(table), 200

def get_tables():
    return 'do some magic!'
