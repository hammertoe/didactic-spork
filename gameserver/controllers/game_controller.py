from gameserver.game import Game
from gameserver.database import db

db_session = db.session
game = Game()

def do_tick():
    game.tick()
    db_session.commit()
    return None, 200

def do_sale(sale):
    try:
        buyer = sale['buyer']
        seller = sale['seller']
        policy = sale['policy']
        price = sale['price']
        game.sell_policy(seller, buyer, policy, price)
    except ValueError:
        return None, 400

    return None, 200
