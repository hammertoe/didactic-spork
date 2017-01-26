from gameserver.database import db
from gameserver.game import Game
from flask import Flask

def create_app():
    app = Flask(__name__)
#    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:foobar@localhost:3306/freeicecream'
#    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqldb://root:foobar@/freeicecream?unix_socket=/cloudsql/free-ice-cream:europe-west1:free-ice-cream'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:foobar@104.199.96.2:3306/freeicecream'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.app = app
    db.init_app(app)
    return app

app = create_app()

db_session = db.session

game = Game()

for x in range(100):
    p = game.create_player('Test Player {}'.format(x))
    print p.name
    for policy in p.children():
        p.fund(policy, 0.15)
    
print "Committing"
db_session.commit()

