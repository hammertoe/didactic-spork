from gameserver.game import Game
from gameserver.database import db
from gameserver.models import Wallet

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

def league_table():
    import pdb; pdb.set_trace()
    res = []
    top = game.top_players()
    for t in top:
        funded = db_session.query(Wallet.balance).filter(Wallet.location == t.goal,
                                                         Wallet.owner == t).scalar()

        if not t.goal:
            continue 

        r = {'id': t.id,
             'name': t.name,
             'goal': t.goal.name,
             'goal_contribution': funded or 0.0,
             'goal_total': t.goal.balance,
             }
        res.append(r)

    return res
        
