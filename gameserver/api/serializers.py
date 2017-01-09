
from flask_restplus import fields
from gameserver.api.restplus import api

player = api.model('Player', {
    'id': fields.String(readOnly=True, description='The unique identifier of a player'),
    'name': fields.String(required=True, description='Player name'),
})

