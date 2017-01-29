from gameserver.database import db
from gameserver.game import Game
from time import time, sleep
from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+cymysql://root:foobar@localhost:3306/freeicecream'
#    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://root:foobar@/freeicecream?unix_socket=/cloudsql/free-ice-cream:europe-west1:free-ice-cream'
#    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+cymysql://root:foobar@104.199.96.2:3306/freeicecream'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = False
    db.app = app
    db.init_app(app)
    return app

app = create_app()
db_session = db.session
game = Game()

TICKINTERVAL = 3

while 1:
    t1 = time()
    game.tick()
    db_session.commit()
    t2 = time()
    duration = t2-t1
    print "tick! {:.2f}s".format(duration)
    if duration < TICKINTERVAL:
        sleep(TICKINTERVAL-duration)


