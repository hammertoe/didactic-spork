import logging.config
import os
from time import sleep, time

from google.appengine.ext import deferred
from google.appengine.api import memcache

from flask import Flask, Blueprint, request

from gameserver.database import db
from gameserver import settings
from gameserver.game import Game

from gameserver.controllers import _do_tick, _league_table

log = logging.getLogger(__name__)
db_session = db.session
game = Game()

TICKINTERVAL = 3

def configure_app(flask_app):
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', settings.SQLALCHEMY_DATABASE_URI)
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = settings.SQLALCHEMY_TRACK_MODIFICATIONS
    flask_app.config['SWAGGER_UI_DOC_EXPANSION'] = settings.RESTPLUS_SWAGGER_UI_DOC_EXPANSION
    flask_app.config['RESTPLUS_VALIDATE'] = settings.RESTPLUS_VALIDATE
    flask_app.config['RESTPLUS_MASK_SWAGGER'] = settings.RESTPLUS_MASK_SWAGGER
    flask_app.config['ERROR_404_HELP'] = settings.RESTPLUS_ERROR_404_HELP
    flask_app.config['DEBUG'] = True
    flask_app.config['SQLALCHEMY_ECHO'] = False

def initialize_app(flask_app):
    configure_app(flask_app)
    db.app = flask_app
    db.init_app(flask_app)
    with flask_app.app_context():
        import models
        models.Base.metadata.create_all(bind=db.engine)

def create_app():
    app = Flask(__name__)
    initialize_app(app)
    return app

app = create_app()

@app.route('/_ah/start')
def start():
    log.info('Ticker instance started')
    return tick()

@app.route('/tick')
def tick():
    duration = 0
    try:
        # tick the game
        if game.is_running():
            t1 = time()
            _do_tick()
            db_session.commit()
            t2 = time()
            duration = t2-t1
            log.info('Tick! {:.2f}s'.format(duration))
        else:
            log.info('Tick skipped as game stopped')
            db_session.rollback()
    except Exception as e:
        log.exception("Error ticking")
        db_session.rollback()

    interval = TICKINTERVAL - duration
    interval = max(0, interval)
    deferred.defer(tick, _countdown=interval)
    return 'Tick! {:.2f}s'.format(duration), 200

def main(): # pragma: no cover
    app = create_app()
    log.info('>>>>> Starting development server at http://{}/api/ <<<<<'.format(app.config['SERVER_NAME']))
    app.run(debug=settings.FLASK_DEBUG)

if __name__ == "__main__": # pragma: no cover
    main()

