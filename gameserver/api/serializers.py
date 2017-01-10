
from flask_restplus import fields
from gameserver.api.restplus import api

player_get = api.model('Player GET', {
    'id': fields.String(readOnly=True, description='The unique identifier of a player'),
    'name': fields.String(required=True, description='Player name'),
})

player_post = api.model('Player POST', {
    'name': fields.String(required=True, description='Player name'),
})

player_delete = api.model('Player DELETE', {
    'id': fields.String(readOnly=True, description='The unique identifier of a player'),
})

