#!/usr/bin/python3
from flup.server.fcgi import WSGIServer
from app import app

if __name__ == '__main__':
    WSGIServer(app, debug=False).run()
