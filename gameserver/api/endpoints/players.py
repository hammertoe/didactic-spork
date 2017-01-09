import logging

from flask import request
from flask_restplus import Resource

from gameserver.game import Game
from gameserver.models import Player

from gameserver.api.restplus import api
from gameserver.api.serializers import player

log = logging.getLogger(__name__)

ns = api.namespace('players', description='Operations related to players')

@ns.route('/')
class PlayerCollection(Resource):

    @api.marshal_list_with(player)
    def get(self):
        """
        Returns list of blog categories.
        """
        players = Game().get_players()
        return players

    @api.response(201, 'Category successfully created.')
    @api.expect(player)
    def post(self):
        """
        Creates a new blog category.
        """
        data = request.json
        p1 = Game().add_player(data['name'])
        return p1.id, 201



