#!/usr/bin/env python3

import json
import random
import threading
import time
import os

import cherrypy
import shapely.geometry
import psycopg2
from psycopg2.extras import execute_batch

def random_point_in_polygon(polygon):
    result = None
    minx, miny, maxx, maxy = polygon.bounds
    while result is None:
        pnt = shapely.geometry.Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if polygon.contains(pnt):
            result = list(pnt.coords[0])
    return result

def randomString(stringLength):
    letters = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f']
    return ''.join(random.choice(letters) for i in range(stringLength))

valid_answers = [0, 1]

city_poly = None

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

DATABASE_URL = os.environ['DATABASE_URL']

class DbPostgres(IDb):
    def store_new_answers(self, points, answers):
        if len(points) != len(answers):
            raise ValueError("invalid number of answers")

        t = time.time()

        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
            with conn.cursor() as cursor:
                execute_batch(
                    cursor,
                    "INSERT INTO Answer (point_json, answer_val, answer_time) VALUES (%s, %s, %s);",
                    [(json.dumps(point), answer, t) for point, answer in zip(points, answers)]
                )

    def get_all_answers(self):
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT point_json, answer_val FROM Answer;")

                return {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": json.loads(point_json)
                            },
                            "properties": {
                                "answer": int(answer_val)
                            }
                        }
                        for point_json, answer_val in cursor.fetchall()
                    ]
                }

    def new_session(self, points):
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
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
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
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
        with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE WebSession WHERE ttl < %s;",
                    (time.time(),)
                )

# class DbInMemory(IDb):
#     def __init__(self):
#         self.db = []
#         self.sessionsdb = {}
#         self.sessionslock = threading.Lock()

#     def store_new_answers(self, points, answers):
#         for point, answer in zip(points, answers):
#             self.db.append({
#                 'type': 'Feature',
#                 'geometry': {
#                     'type': 'Point',
#                     'coordinates': point,
#                 },
#                 'properties': {
#                     'answer': answer
#                 }
#             })

#     def get_all_answers(self):
#         return {
#             'type': 'FeatureCollection',
#             'features': self.db
#         }
    
#     def new_session(self, points):
#         with self.sessionslock:
#             session_id = None
#             while session_id is None or session_id in self.sessionsdb:        
#                 session_id = randomString(64)
    
#             self.sessionsdb[session_id] = {
#                 'session_id': session_id,
#                 'points': points,
#                 'ttl': time.time() + 15*60
#             }

#             return self.sessionsdb[session_id]
    
#     def get_and_delete_session(self, session_id):
#         session = None

#         with self.sessionslock:
#             session = self.sessionsdb.get(session_id, None)

#             if session is not None:
#                 del self.sessionsdb[session_id]

#         if session is None or session['ttl'] < time.time():
#             raise KeyError('session not found')
        
#         return session['points']
    
#     def clean_stale_sessions(self):
#         with self.sessionslock:
#             for k in list(self.sessionsdb.keys()):
#                 if self.sessionsdb[k]['ttl'] < time.time():
#                     del self.sessionsdb[k]

class TlvOrJServer:
    def __init__(self):
        self.db = DbPostgres()

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
            return self.db.get_all_answers()
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_session(self):
        points = [random_point_in_polygon(city_poly) for i in range(5)]

        return self.db.new_session(points)

config = {
    'global': {
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.environ.get('PORT', 5000)),
    },
    '/assets': {
        'tools.staticdir.root': os.path.dirname(os.path.abspath(__file__)),
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'assets',
    }
}

def main():
    global city_poly
    with open('citylimits.geojson.json', 'r', encoding='utf-8-sig') as f:
        city_poly = shapely.geometry.shape(json.load(f)['features'][0]['geometry'])
    cherrypy.quickstart(TlvOrJServer(), config=config)

if __name__ == "__main__":
    main()