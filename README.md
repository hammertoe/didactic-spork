[![Build Status](https://travis-ci.org/hammertoe/didactic-spork.svg?branch=master)](https://travis-ci.org/hammertoe/didactic-spork)
[![Coverage Status](https://coveralls.io/repos/github/hammertoe/didactic-spork/badge.svg?branch=master)](https://coveralls.io/github/hammertoe/didactic-spork?branch=master)

## Intro

This code is the server developed for the HiveMind 2030 project as part of the Global Festival of Ideas. It tracks the players and money moving through a network of policy and goal nodes. A mobile app and game table both access this server during gameplay.

The server is written in Python using the Flask web framework and Connexions to work directly from an OpenAPI spec.

## Parts

The server is split into 3 distinct 'services' on Google App Engine that co-operate.

- ticker.yaml 
  This is a scheduler that puts a new task for the task worker onto a Google Push Queue once every 3 seconds. It checks that the game is actually running and if the game has been stopped by the API then the ticker stops. This needs to be a manually scaled instance so that it continues to run indefinitely. It can be run on the smallest instance type available as has very little CPU or memory requirements.
  
- tick_worker.yaml
  This processes the jobs put on the queue by the ticker. It processes the game running the main `tick` method. It can handle a game of up to around 400-500 players when run on the highest CPU manually scaled instance. Just a single instance of this needs to be running. It processes the network, pre-calculates the JSON for a number of the API endpoints and stores them in memcached.
   
- app.yaml
  This service handles the requests from the client. It can have multiple instances running to handle additional load. For 400-500 players, we ran 5 instances. It checks memcache and serves up cached responses from the tick_worker if there, otherwise it calculates the responses itself. 

## Deployment

The server is deployed to Google App Engine and runs on a number of instances that can be scaled up or down depending on the load as necessary. It stores the data in Google Cloud SQL (Hosted MySQL). 

## API

The API has been specified in OpenAPI format, with the spec at [https://raw.githubusercontent.com/hammertoe/didactic-spork/master/gameserver/swagger.yaml]. An instance of the API can be found on the demo site at: [http://free-ice-cream.appspot.com/v1/ui/].

