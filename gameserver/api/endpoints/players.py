import logging

from flask import request
from flask_restplus import Resource

from gameserver.game import Game
from gameserver.models import Player

from gameserver.api.restplus import api
from gameserver.api.serializers import player

from gameserver.database import db

db_session = db.session

log = logging.getLogger(__name__)

ns = api.namespace('players', description='Operations related to players')

game = Game()

@ns.route('/')
class PlayerCollection(Resource):

    @api.marshal_list_with(player)
    def get(self):
        """
        Returns list of players.
        """
        players = game.get_players()
        return players

    @api.response(201, 'Player successfully created.')
    @api.expect(player)
    def post(self):
        """
        Creates a new game player.
        """
        data = request.json
        player = game.create_player(data['name'])
        db_session.commit()
        return player.id, 201



