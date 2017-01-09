import logging.config
import os

from flask import Flask, Blueprint

from gameserver.api.restplus import api
from gameserver.database import db, init_db

from gameserver.api.endpoints.players import ns as players_namespace

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


def initialize_app(flask_app):
    configure_app(flask_app)

    blueprint = Blueprint('api', __name__, url_prefix='/api')
    api.init_app(blueprint)
    api.add_namespace(players_namespace)
    flask_app.register_blueprint(blueprint)

    db.init_app(flask_app)
    with flask_app.app_context():
        import models
        models.Base.metadata.create_all(bind=db.engine)

def create_app():
    app = Flask(__name__)
    initialize_app(app)
    return app

app = create_app()

def main():
    app = create_app()
    log.info('>>>>> Starting development server at http://{}/api/ <<<<<'.format(app.config['SERVER_NAME']))
    app.run(debug=settings.FLASK_DEBUG)

if __name__ == "__main__":
    main()

