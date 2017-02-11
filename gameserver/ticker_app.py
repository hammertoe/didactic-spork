import logging.config
import os
from time import sleep

from google.appengine.ext import deferred
from google.appengine.api import taskqueue

from flask import Flask, Blueprint, request

from gameserver.database import db

from gameserver import settings

log = logging.getLogger(__name__)

def configure_app(flask_app):
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', settings.SQLALCHEMY_DATABASE_URI)
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = settings.SQLALCHEMY_TRACK_MODIFICATIONS
    flask_app.config['SWAGGER_UI_DOC_EXPANSION'] = settings.RESTPLUS_SWAGGER_UI_DOC_EXPANSION
    flask_app.config['RESTPLUS_VALIDATE'] = settings.RESTPLUS_VALIDATE
    flask_app.config['RESTPLUS_MASK_SWAGGER'] = settings.RESTPLUS_MASK_SWAGGER
    flask_app.config['ERROR_404_HELP'] = settings.RESTPLUS_ERROR_404_HELP
    flask_app.config['DEBUG'] = True
    flask_app.config['SQLALCHEMY_ECHO'] = True

def initialize_app(flask_app):
    configure_app(flask_app)

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
    q = taskqueue.Queue('pullq')
    while True:
        try:
            tasks = q.lease_tasks_by_tag(600, 100, deadline=60)
        except (taskqueue.TransientError,
                apiproxy_errors.DeadlineExceededError) as e:
            logging.exception(e)
            time.sleep(1)
            continue
        if tasks:
            key = tasks[0].tag

            import pdb; pdb.set_trace()

            try:
                update_counter()
            except Exception as e:
                logging.exception(e)
            else:
                q.delete_tasks(tasks)
        time.sleep(0.5)

    return tick()

def tick():
    log.info('Tick!')
    deferred.defer(tick, _countdown=3)
    return "tick!", 200

def main(): # pragma: no cover
    app = create_app()
    log.info('>>>>> Starting development server at http://{}/api/ <<<<<'.format(app.config['SERVER_NAME']))
    app.run(debug=settings.FLASK_DEBUG)

if __name__ == "__main__": # pragma: no cover
    main()

