import logging

from flask import request
from flask_restplus import Resource

from gameserver.game import Game
from gameserver.models import Player

from gameserver.api.restplus import api
from gameserver.api.serializers import player_get, player_post

from gameserver.database import db

db_session = db.session

log = logging.getLogger(__name__)

ns = api.namespace('players', description='Operations related to players')

game = Game()

@ns.route('/')
class PlayerCollection(Resource):

    @api.response(200, 'Success')
    @api.marshal_list_with(player_get)
    def get(self):
        """
        Returns list of players.
        """
        players = game.get_players()
        return players

    @api.response(201, 'Player successfully created.')
    @api.expect(player_post)
    def post(self):
        """
        Creates a new game player.
        """
        data = request.json
        player = game.create_player(data['name'])
        db_session.commit()
        return dict(id=player.id), 201


@ns.route('/<string:id>')
@ns.param('id', 'The player id')
class Player(Resource):

    @api.response(404, 'Player not found')
    @api.response(200, 'Success')
    @api.marshal_with(player_get)
    def get(self, id):
        """
        Returns the specified player.
        """
        player = game.get_player(id)
        if not player:
            api.abort(404)
        return player



