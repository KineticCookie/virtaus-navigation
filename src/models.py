import datetime
import random
import polyline
from routing import *
from data import *


class Point:
    def __init__(self, lat, lng):
        self.lat = lat
        self.lng = lng

    def to_tuple(self):
        return (self.lat, self.lng)


class Fleet:
    maximum_route_deviation = 10*60 # in seconds

    def __init__(self, ):
        self.routes = []
        pass

    def reset(self):
        self.routes = []

    def add_route(self, route_id, loc):
        self.routes.append(Route(route_id, loc))

    def stop_route(self, route_id):
        list(filter(lambda x: x.route_id == route_id, self.routes))[0].set_blocked(True)

    def add_passenger(self, user_id, user_loc):
        routes_deviations = map(lambda r: r.mimimum_deviation_point(user_loc), self.routes)
        routes_deviations = [x for x in routes_deviations if x is not None]
        if len(routes_deviations) > 0:
            mindev = min(routes_deviations, key=lambda x: x[1][0])
            minrdev_route = self.routes[routes_deviations.index(mindev)]
            node, (dev, new_r) = mindev
            print(new_r)
            minrdev_route.stops = new_r
            minrdev_route.update_geometry()
            minrdev_route.users_waiting.append(user_id)
            minrdev_route.user2stop[user_id] = node
            new_user_geometry = get_route([user_loc, node])['routes'][0]['geometry']
            minrdev_route.user_geometry.append(new_user_geometry)
            return True
        else:
            return False
    def get_all_routes(self):
        return self.routes
    
    # to be called periodically
    def move(self, ):
        for r in self.routes:
            r.check_availability()
            r.move() 

# Represents a bus
class Route:

    distance_threshold = 6 * 60
    user_walk_time = 5*60
    maximum_riding_time = 15 * 60 # SLA?

    def __init__(self, route_id, loc):
        self.route_id = route_id
        self.loc = loc
        self.available = True
        self.users_in = []
        self.users_waiting = []
        self.user2stop = dict()
        self.stops = []
        self.geometry = polyline.encode([self.loc])
        self.user_geometry = []

    def acceptable_deviation(self, deviation):
        if len(self.users_in) == 0:
            return True
        oldest_user = min(self.users_in, key = lambda x: x[1])
        return (datetime.datetime.now() - oldest_user[1]).total_seconds + deviation < Route.maximum_riding_time

    def move(self, new_loc):
        self.loc = new_loc

    def update_geometry(self, ):
        self.geometry = get_route([self.loc] + self.stops)['routes'][0]['geometry']

    def set_blocked(self, new_status):
        self.available = new_status

    # Returns points which will mimize the
    # deviation of bus from it's route
    def mimimum_deviation_point(self, user_loc):
        if not self.available:
            return None
        distance = get_distance(self.loc, user_loc)
        if distance > self.distance_threshold:
            return None
        user_walk_distance = min(distance + 3 * 60, self.user_walk_time)
        user_isoline = get_user_isoline(user_loc[0], user_loc[1], time_to_walk=int(user_walk_distance), to_utm=False)
        nodes_around = filter_isoline_nearby(user_isoline, get_nearby(user_loc, number=20))
        results = {}
        # TODO use MCMC:
        for node in random.choices(nodes_around, k=5):
            route, length = get_trip(self.stops + [node], start = self.loc)
            print(node)
            results[node] = (length, route[1:])
        proposal = min(results, key=results.get)
        if not self.acceptable_deviation(results[proposal]): # SLA
            return None
        else:
            return (proposal, results[proposal])

    def set_blocked(self, new_status):
        self.available = status 

    def check_availability(self, ):
        if len(self.users_in) == 0:
            return True
        oldest_user = min(self.users_in, key = lambda x: x[1])
        if len(self.stops) > 0:
            tram_routing_time = list(map(lambda x: get_distance(self.stops[-1], x), tram_stations))
        else:
            tram_routing_time = list(map(lambda x: get_distance(self.loc, x), tram_stations))

        closest_tram = tram_stations[tram_routing_time.index(min(tram_routing_time))]
        proba =  ((datetime.datetime.now() - oldest_user[1]).total_seconds() - min(tram_routing_time))/(self.maximum_riding_time)
        if proba > 0.8 or len(self.stops) <= 1:
            self.stops.append(closest_tram)
            self.update_geometry()
            return False
        else:
            True
    
    def move(self, ):
        if not self.available:
            pass
        if len(self.stops) > 0:
            
            route = polyline.decode(self.geometry)
            print("Next stop: ", np.round(self.stops[0], decimals=3), "Cur location: ", np.round(self.loc, decimals=3))
            if np.array_equal(np.round(self.loc, decimals=3), np.round(self.stops[0], decimals=3)):
                if len(self.stops) > 1:
                    self.stops = self.stops[1:]
                    self.update_geometry()
                else:
                    self.stops = [self.loc]
                    self.update_geometry()
                self.users_in.append((random.randint(0,1e4), datetime.datetime.now()))
                self.user_geometry = list(filter(lambda x: not (polyline.decode(x)[-1] == x), self.user_geometry))
                return None
            
            self.loc = route[0]
            
            if len(route) > 1:
                self.geometry = polyline.encode(route[1:])
            else:
                self.geometry = polyline.encode([self.loc])
        else:
            pass # Move to the highest density 

    def acceptable_deviation(self, deviation):
        if len(self.users_in) == 0:
            return True
        oldest_user = min(self.users_in, key = lambda x: x[1])
        return (datetime.datetime.now() - oldest_user[1]).total_seconds + deviation < maximum_riding_time 