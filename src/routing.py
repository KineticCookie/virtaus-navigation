import numpy as np
import requests
import shapely.geometry as g
import utm

from config import HERE_APP_ID, HERE_APP_CODE, OSMR_ADDR


def latlon2utm_list(ps):
    utms = []
    for p in ps:
        x, y, _, _ = utm.from_latlon(p[0], p[1])
        utms.append((x, y))
    return utms


def get_user_isoline(user_lat, user_lon, time_to_walk=5 * 60, to_utm=True):
    here_isoline_base = "https://isoline.route.api.here.com/routing/7.2/calculateisoline.json"
    isoline_params = {"app_id": HERE_APP_ID,
                      "app_code": HERE_APP_CODE,
                      "mode": "shortest;pedestrian;traffic:disabled",
                      "start": f"geo!{user_lat},{user_lon}",
                      "range": time_to_walk,
                      "rangetype": "time"}
    get_isoline = requests.get(here_isoline_base, params=isoline_params)
    if get_isoline.status_code == 200:
        iso_shape = get_isoline.json()['response']['isoline'][0]['component'][0]['shape']
        iso_xy = [(float(x.split(',')[0]), float(x.split(',')[1])) for x in iso_shape]
        if to_utm == True:
            iso_xy = [(utm.from_latlon(x[0], x[1])[0], utm.from_latlon(x[0], x[1])[1]) for x in iso_xy]
        return g.Polygon(iso_xy)
    else:
        print("Isoline got error:", get_isoline.status_code, get_isoline.json())
        return None


def get_trip(wps, start):
    coordinates = f"{start[0]},{start[1]};" + ";".join([f"{wp[1]},{wp[0]}" for wp in wps])
    api = f"/trip/v1/car/{coordinates}?source=first&annotations=duration"
    r = requests.get(f"{OSMR_ADDR}{api}").json()
    r['waypoints'].sort(key=lambda x: x['waypoint_index'])
    trip_points = [x['location'] for x in r['waypoints']]
    trip_points = [(x[1], x[0]) for x in trip_points]
    trip_points[0] = start
    duration = r['trips'][0]['duration']
    return trip_points, duration


# lat, lon
def get_distance(x, y):
    #     x =  requests.get(f"{base}/nearest/v1/walking/{x[1]},{x[0]}").json()['waypoints'][0]['location']
    #     y =  requests.get(f"{base}/nearest/v1/walking/{y[1]},{y[0]}").json()['waypoints'][0]['location']
    #     distance = requests.get(f"{base}/table/v1/walking/{x[0]},{x[1]};{y[0]},{y[1]}").json()['durations'][0][1]
    distance = requests.get(f"{OSMR_ADDR}/table/v1/walking/{x[1]},{x[0]};{y[1]},{y[0]}").json()['durations'][0][1]

    return distance  # in seconds


def get_nearby(x, number=1, mode="waliking"):
    points = requests.get(f"{OSMR_ADDR}/nearest/v1/{mode}/{x[1]},{x[0]}", params={"number": number}).json()['waypoints']
    points = [x['location'] for x in points]
    points = [(x[1], x[0]) for x in points]

    return points


def get_route(wps):
    coordinates = ";".join([f"{wp[1]},{wp[0]}" for wp in wps])
    route = requests.get(f"{OSMR_ADDR}/route/v1/car/{coordinates}", params={"annotations": "distance"})
    return route.json()


# (x, y), [(x, y)]
def propose_node(cur_node, nodes):
    nodes_distances = np.array(list(map(lambda x: get_distance(x, cur_node), nodes)))
    new_node = np.random.choice(nodes, p=(nodes_distances / np.sum(nodes_distances)))
    return new_node


def get_nodes_in_isoline(isoline, G):
    return list(filter(lambda x: isoline.contains(g.Point(G.nodes[x]['y'], G.nodes[x]['x'])), G.nodes))


def filter_isoline_nearby(isoline, points):
    return list(filter(lambda x: isoline.contains(g.Point(x)), points))


def here_sort(wps, start):
    base = "https://wse.api.here.com/2/findsequence.json?"
    start = f"start={start[0]},{start[1]}&"
    destinations = ""
    for i, wp in enumerate(wps):
        destinations += f"destination{i+1}={wp[0]},{wp[1]}&"
    #     end = f"end={end[0]},{end[1]}&"
    trail = f"mode=fastest;car&app_id={HERE_APP_ID}&app_code={HERE_APP_CODE}"
    q = base + start + destinations + trail
    r = requests.get(q, timeout=0.5)
    wps = r.json()['results'][0]['waypoints']
    wps.sort(key=lambda x: x['sequence'])
    order = [(x['lat'], x['lng']) for x in wps]
    return order


def dist(order, xs, ys):
    x, y = xs[order[0]], ys[order[0]]
    cum_dist = 0
    for i in order[1:]:
        cum_dist += get_distance((x, y), (xs[i], ys[i]))
        x, y = xs[i], ys[i]
    return cum_dist


# Randomly swap two items in an array
def permute(order):
    temp_order = order.copy()
    indexes = np.arange(len(temp_order))
    np.random.shuffle(indexes)
    a, b = indexes[:2]
    temp = temp_order[a]
    temp_order[a] = temp_order[b]
    temp_order[b] = temp
    return temp_order


def ts_sort(wps, start, T=100, alpha=0.5, iterations=20):
    if len(wps) == 1:
        return [start] + wps

    xs, ys = list(zip(*wps))
    order = np.arange(0, len(wps))  # initial order
    np.random.shuffle(order)
    distance = dist(order, xs, ys)
    for i in range(iterations):
        new_order = permute(order)
        thresh = np.random.uniform()
        new_distance = dist(new_order, xs, ys)
        d = (new_distance - distance) / distance;
        p = 1 if d < 0 else np.exp(- d / T)
        if p >= thresh:
            order = new_order
            distance = new_distance
        T = T * alpha  # decrease temperature
    return [start] + np.array(wps)[order]


def route_duration(wps):
    print(wps)
    route = get_route(wps)
    return route['routes'][0]['duration']
