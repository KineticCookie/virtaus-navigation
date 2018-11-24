from flask import Flask, jsonify, request

from config import APP_PORT
from data import tram_stations
from models import Fleet, Point

app = Flask(__name__)

state_fleet = Fleet()

state_fleet.add_route(1, tram_stations[0])
state_fleet.add_route(2, tram_stations[1])


@app.route("/api/bus", methods=["POST"])
def add_passenger():
    content = request.json
    user_id = int(content['user_id'])
    point_json = content['point']
    point = Point(point_json['lat'], point_json['lng'])
    result = state_fleet.add_passenger(user_id, point.to_tuple())
    return jsonify(result=result)


@app.route("/api/routes", methods=["GET"])
def get_all_routes():
    routes = state_fleet.get_all_routes()
    return jsonify(routes=[x.__dict__ for x in routes])


if __name__ == "__main__":
    app.run("0.0.0.0", int(APP_PORT))
