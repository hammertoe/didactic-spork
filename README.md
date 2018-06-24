[![Build Status](https://travis-ci.org/free-ice-cream/didactic-spork.svg?branch=master)](https://travis-ci.org/free-ice-cream/didactic-spork)
[![Coverage Status](https://coveralls.io/repos/github/free-ice-cream/didactic-spork/badge.svg?branch=master)](https://coveralls.io/github/free-ice-cream/didactic-spork?branch=master)

## Intro

This code is the server developed for the HiveMind 2030 project as part of the Global Festival of Ideas. It tracks the players and money moving through a network of policy and goal nodes. A mobile app and game table both access this server during gameplay.

The server is written in Python using the Flask web framework and Connexions to work directly from an OpenAPI spec.

## Installation

```
virtualenv  --python=python2.7 .
. bin/activate
pip install -r requirements
export PYTHONPATH=${PYTHONPATH}:gameserver
bin/python gameserver/main.py
```

## API

The API has been specified in OpenAPI format, with the spec at [https://raw.githubusercontent.com/hammertoe/didactic-spork/master/gameserver/swagger.yaml]. An instance of the API can be found on the demo site at: [http://free-ice-cream.appspot.com/v1/ui/].

