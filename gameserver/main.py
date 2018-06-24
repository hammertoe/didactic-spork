import logging.config
import os

from flask import Flask, Blueprint, request

import connexion

import settings
from database import get_db

log = logging.getLogger(__name__)

def configure_app(flask_app):
    flask_app.config['SWAGGER_UI_DOC_EXPANSION'] = settings.RESTPLUS_SWAGGER_UI_DOC_EXPANSION
    flask_app.config['RESTPLUS_VALIDATE'] = settings.RESTPLUS_VALIDATE
    flask_app.config['RESTPLUS_MASK_SWAGGER'] = settings.RESTPLUS_MASK_SWAGGER
    flask_app.config['ERROR_404_HELP'] = settings.RESTPLUS_ERROR_404_HELP
    flask_app.config['DEBUG'] = True
    flask_app.config['TESTING'] = True
    flask_app.config['ZODB_STORAGE'] = 'file://app.fs'
    

def cors_after_request(resp):
    headers_allow = request.headers.get('Access-Control-Request-Headers', '*')
    resp.headers['Access-Control-Allow-Headers'] = headers_allow
    resp.headers['Access-Control-Allow-Origin'] = '*'
    methods_allow = request.headers.get('Access-Control-Request-Method', '*')
    resp.headers['Access-Control-Allow-Methods'] = methods_allow
    return resp

def create_app():
    app = connexion.App(__name__, specification_dir='./')
    app.add_api('swagger.yaml', arguments={'title': 'An API for the game server allowing mobile app to interact with players, etc'})
    configure_app(app.app)
    with app.app.app_context():
        db = get_db()
        db.init_app(app.app)

    app.app.after_request(cors_after_request)
    return app.app

app = create_app()

def main(): # pragma: no cover
    app = create_app()
    log.info('>>>>> Starting development server at http://{}/api/ <<<<<'.format(app.config['SERVER_NAME']))
    app.run(debug=settings.FLASK_DEBUG)

if __name__ == "__main__": # pragma: no cover
    main()

