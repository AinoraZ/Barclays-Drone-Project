from control import DroneControl
import socketio
import threading
import config
import eventlet.wsgi
from flask import Flask, render_template
from data_parser import DataParser

if __name__ == '__main__':
    #eventlet.monkey_patch()
    sio = socketio.Server()
    #worker = DroneControl(config.DRONE_LOCAL, sio)

    @sio.on('connect')
    def connect(sid, environ):
        print('connect ', sid)

    @sio.on('mission')
    def message(sid, data):
        t = threading.Thread(target = DataParser, kwargs={'data' : data})
        t.start()

    @sio.on('_test_mission')
    def message(sid):
        #t = threading.Thread(target = worker.arm_and_takeoff, kwargs={'alt': 10})
        #t.start()
		print "works"

    @sio.on('force_land')
    def message(sid):
        #t = threading.Thread(target = worker.land)
        #t.start()
		print "works"

    @sio.on('disconnect')
    def disconnect(sid):
        print('disconnect ', sid)

    #app = Flask(__name__, template_folder='../templates')
    #app.debug = True

    #@app.route('/')
    #def index():
        #return render_template("index.html")

    app = socketio.Middleware(sio)
    eventlet.wsgi.server(eventlet.listen(('', 8001)), app)