import urllib2
import json
import time

BASE = 'http://localhost:8080/v1'

# util function for sending data to API
def send(endpoint, data=None):
    if data is not None:
        data = json.dumps(data)
        headers = {'Content-Type': 'application/json'}
        req = urllib2.Request(BASE + endpoint, data, headers)
    else:
        req = urllib2.Request(BASE + endpoint)
    f = urllib2.urlopen(req)
    return json.load(f)

# Create a user named 'matt' and get their access token and user id
data = {'name': 'Matt'}
res = send('/players/', data)

user_id = res['id']
token = res['token'] # we don't use this just yet
goal = res['goal']
policies = res['policies']

# Print out some stuff
print "My Id:"
print "  {}".format(user_id)

print "Goal:"
print "  {id} - {name}".format(**goal)

print "Policies:"
for policy in policies:
  print "  {id} - {name}".format(**policy)

# allocate even funding (20 units) to each 5 policies
funding = []
for policy in policies:
    fund = {'from_id': user_id,
            'to_id': policy['id'],
            'amount': 20.0,}
    funding.append(fund)

res = send('/players/{}/funding'.format(user_id), funding)

print "Current funding:"
for fund in res:
    print "  {amount} {to_id}".format(**fund)

print "Run the game!"
print "Balance of my goal:"
while True:
    send('/game/tick', {})
    
    goal = send('/network/{}'.format(goal['id']))
    print "  {:.2f}".format(goal['balance'])

    time.sleep(1)
    


