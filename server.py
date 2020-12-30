#!/usr/bin/env python3

import json
import random
import threading
import time
import os
import math

import cherrypy
import shapely.geometry
import psycopg2
from psycopg2.extras import execute_batch

# from line_of_best_fit import get_boundary_line

def random_point_in_polygon(polygon, force_minx=None, force_maxx=None, force_miny=None, force_maxy=None):
    result = None
    minx, miny, maxx, maxy = polygon.bounds

    if force_minx is not None and force_minx > minx:
        minx = force_minx
    if force_maxx is not None and force_maxx < maxx:
        maxx = force_maxx
    if force_miny is not None and force_miny > miny:
        miny = force_miny
    if force_maxy is not None and force_maxy < maxy:
        maxy = force_maxy

    while result is None:
        pnt = shapely.geometry.Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if polygon.contains(pnt):
            result = list(pnt.coords[0])
    return result

def randomString(stringLength):
    letters = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']
    return ''.join(random.choice(letters) for i in range(stringLength))

def long2tileFrac(lon,zoom):
    return (lon+180.0)/360.0 * (2.0 ** zoom)

def lat2tileFrac(lat,zoom):
    return (
        1.0-math.log(math.tan(lat*math.pi/180.0) + 1.0/math.cos(lat*math.pi/180.0))/math.pi
    )/2.0 * (2.0 ** zoom)


valid_answers = [0, 1]

city_poly = None
preferred_maxx = 34.7807
preferred_maxy = 32.0646

class IDb:
    def store_new_answers(self, points, answers):
        pass

    def get_all_answers(self):
        pass

    def new_session(self, points):
        pass

    def get_and_delete_session(self, session_id):
        pass

    def clean_stale_sessions(self):
        pass

    def renew_session(self, session_id):
        pass

class DbPostgres(IDb):
    def __init__(self, db_url):
        self.db_url = db_url
    
    def store_new_answers(self, points, answers):
        if len(points) != len(answers):
            raise ValueError("invalid number of answers")

        t = time.time()

        with psycopg2.connect(self.db_url, sslmode='require') as conn:
            with conn.cursor() as cursor:
                execute_batch(
                    cursor,
                    "INSERT INTO Answer (point_json, answer_val, answer_time) VALUES (%s, %s, %s);",
                    [(json.dumps(point), answer, t) for point, answer in zip(points, answers)]
                )

    def get_all_answers(self):
        with psycopg2.connect(self.db_url, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT point_json, answer_val FROM Answer ORDER BY answer_time ASC;")

                return [
                    json.loads(point_json) + [float(answer_val)]
                    for point_json, answer_val in cursor.fetchall()
                ]

    def new_session(self, points):
        with psycopg2.connect(self.db_url, sslmode='require') as conn:
            with conn.cursor() as cursor:
                # generate a unique random session id lol
                session_id = None
                while session_id is None or cursor.fetchone()[0] != 0:        
                    session_id = randomString(64)
                    cursor.execute(
                        "SELECT COUNT(*) FROM WebSession WHERE session_id = %s;",
                        (session_id,)
                    )
                
                ttl = time.time() + 15*60

                cursor.execute(
                    "INSERT INTO WebSession (session_id, ttl, points_json) VALUES (%s, %s, %s);",
                    (session_id, ttl, json.dumps(points))
                )

                return {
                    "session_id": session_id,
                    "ttl": ttl,
                    "points": points
                }

    def get_and_delete_session(self, session_id):
        with psycopg2.connect(self.db_url, sslmode='require') as conn:
            row = None

            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT session_id, ttl, points_json FROM WebSession WHERE session_id = %s;",
                    (session_id,)
                )

                row = cursor.fetchone()

            if row is not None:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM WebSession WHERE session_id = %s;", (session_id,))
            else:
                raise KeyError("session not found")
            
        if row[1] < time.time():
            raise ValueError("session expired")
            
        return json.loads(row[2])


    def clean_stale_sessions(self):
        with psycopg2.connect(self.db_url, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM WebSession WHERE ttl < %s;",
                    (time.time(),)
                )
    
    def renew_session(self, session_id):
        # q: is this a glaring security hole or a useful ui usability feature?
        # a: why not both?

        with psycopg2.connect(self.db_url, sslmode='require') as conn:
            row = None

            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT session_id, ttl, points_json FROM WebSession WHERE session_id = %s;",
                    (session_id,)
                )

                row = cursor.fetchone()

            if row is None:
                raise KeyError("session not found")

            new_ttl = time.time() + 15*60
            
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE WebSession SET ttl=%s WHERE session_id=%s;",
                    (new_ttl,session_id)
                )
            
            return new_ttl
            
        if row[1] < time.time():
            raise ValueError("session expired")

class TlvOrJServer:
    def __init__(self):
        self.db = DbPostgres(os.environ['DATABASE_URL'])

        self.cleanup_thread = threading.Thread(target=self.cleanup_loop)
        self.cleanup_thread.start()
    
    def cleanup_loop(self):
        while True:
            time.sleep(5*60)
            self.db.clean_stale_sessions()
    
    @cherrypy.expose
    def index(self):
        return open('index.html')

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_all_answers(self):
        return self.db.get_all_answers()
    
    # def get_boundary_for_answers(self, answers_geojson):
    #     # haha gotta convert everything to xyz coordinates at zoom 14 because magic haha
    #     ZOOM = 14
    #     xyj = [
    #         [
    #             #long2tileFrac(f["geometry"]["coordinates"][0], ZOOM),
    #             #lat2tileFrac(f["geometry"]["coordinates"][1], ZOOM),
    #             f["geometry"]["coordinates"][0],
    #             f["geometry"]["coordinates"][1],
    #             f["properties"]["answer"]
    #         ]
    #         for f in answers_geojson["features"]
    #     ]

    #     minlon, minlat, maxlon, maxlat = city_poly.bounds

        # m = get_boundary_line(
        #     xyj, minlon, maxlon, minlat, maxlat
        # )

        return m
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def answer_session(self, session_id, answers, get_all_answers=False):
        points = self.db.get_and_delete_session(session_id)

        answers = list(map(int, str(answers).split(',')))

        if len(answers) != len(points):
            raise ValueError('wrong number of answers')

        for a in answers:
            if a not in valid_answers:
                raise ValueError('invalid answer')

        self.db.store_new_answers(points, answers)

        if get_all_answers:
            all_answers = self.db.get_all_answers()
            # all_answers["properties"] = {
            #     "boundary": self.get_boundary_for_answers(all_answers)
            # }
            return all_answers
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_session(self):
        points = [
            random_point_in_polygon(
                city_poly,
                force_miny=preferred_maxy + random.uniform(-0.04, 0)
            )
            for i in range(2)
        ] + [
            random_point_in_polygon(
                city_poly,
                force_maxx=preferred_maxx + random.uniform(0, 0.03),
                force_maxy=preferred_maxy + random.uniform(0, 0.03)
            )
            for i in range(3)
        ]

        # sort either north to south or south to north
        # sort_direction = random.choice([False, True])
        # points.sort(key=lambda p: p[1], reverse=sort_direction)
        random.shuffle(points)

        return self.db.new_session(points)
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def renew_session(self, session_id):
        return self.db.renew_session(session_id)

config = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.environ.get('PORT', 5000)),
    },
    '/assets': {
        'tools.staticdir.root': os.path.dirname(os.path.abspath(__file__)),
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'assets',
    },
    '/favicon.ico': {
        'tools.staticfile.root': os.path.dirname(os.path.abspath(__file__)),
        'tools.staticfile.on': True,
        'tools.staticfile.filename': 'assets/icons/favicon.ico'
    }
}

def main():
    global city_poly
    with open('citylimits.geojson.json', 'r', encoding='utf-8-sig') as f:
        city_poly = shapely.geometry.shape(json.load(f)['features'][0]['geometry'])
    cherrypy.quickstart(TlvOrJServer(), config=config)

if __name__ == "__main__":
    main()