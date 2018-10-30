#!/usr/bin/python2
from flup.server.fcgi import WSGIServer
from app import app

if __name__ == '__main__':
    WSGIServer(app, debug=False).run()
