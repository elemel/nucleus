from __future__ import with_statement

import config
from Box2D import *
import pyglet
from pyglet.gl import *
import codecs
from collections import *
from itertools import *
from math import *
import cPickle as pickle
import random

def read_words():
    try:
        with open('strung.pickle') as pickle_file:
            return pickle.load(pickle_file)
    except:
        pass

    print 'Reading words...'
    words = [w.strip().upper() for w in
             codecs.open('/usr/share/dict/swedish', 'r', 'ISO-8859-1')
             if w.lower() == w]

    print 'Counting letters...'
    letter_counts = defaultdict(int)
    for word in words:
        for letter in word:
            letter_counts[letter] += 1
    letters = sorted(letter_counts)

    with open('strung.pickle', 'w') as pickle_file:
        pickle.dump((words, letters), pickle_file, pickle.HIGHEST_PROTOCOL)
    return words, letters

words, letters = read_words()

def create_world(aabb, gravity=(0., 0.), do_sleep=True):
    lower_bound, upper_bound = aabb
    aabb = b2AABB()
    aabb.lowerBound = lower_bound
    aabb.upperBound = upper_bound
    return b2World(aabb, gravity, do_sleep)

world = create_world(aabb=((-50., -25.), (50., 75.)), gravity=(0., -10.),
                     do_sleep=True)

class MyBoundaryListener(b2BoundaryListener):
    def __init__(self):
        super(MyBoundaryListener, self).__init__()
        self.violators = set()

    def Violation(self, body):
        body_actor = body.userData
        if body_actor is not None:
            self.violators.add(body_actor)

boundary_listener = MyBoundaryListener()
world.SetBoundaryListener(boundary_listener)

def create_wall(world, half_width, half_height, position, angle=0.):
    ground_body_def = b2BodyDef()
    ground_body = world.CreateBody(ground_body_def)
    ground_shape_def = b2PolygonDef()
    ground_shape_def.SetAsBox(half_width, half_height, position, angle)
    ground_shape_def.restitution = 0.5
    ground_shape_def.friction = 0.5
    ground_body.CreateShape(ground_shape_def)

create_wall(world, half_width=15., half_height=0.5, position=(0., -10.), angle=0.2)
create_wall(world, half_width=0.5, half_height=10., position=(-15., -5.), angle=0.5)
create_wall(world, half_width=0.5, half_height=10., position=(15., 0.), angle=-0.2)

class BodyActor(object):
    def __init__(self, body, label):
        self.body = body
        self.label = label

    def destroy(self):
        if self.body is not None:
            self.body.GetWorld().DestroyBody(self.body)
            self.body = None

def create_letter(dt):
    letter = random.choice(letters)
    body_def = b2BodyDef()
    body_def.position = 10. * (random.random() - 0.5), 30.
    body_def.angle = 2 * pi * random.random()
    body = world.CreateBody(body_def)
    shape_def = b2CircleDef()
    shape_def.radius = 1. + random.random()
    shape_def.density = 1.
    shape_def.restitution = 0.5
    shape_def.friction = 0.5
    body.CreateShape(shape_def)
    body.SetMassFromShapes()
    body.linearVelocity = 0., -5.
    body.angularVelocity = 2. * (random.random() - 0.5)
    label = pyglet.text.Label(letter, bold=True, dpi=200,
                              anchor_x='center', anchor_y='center')
    body_actor = BodyActor(body, label)
    body.userData = body_actor

time = 0.
time_step = 1. / 60.

def step(dt):
    global time
    time += dt
    while time >= time_step:
        time -= time_step
        world.Step(time_step, 10, 8)
        for body_actor in boundary_listener.violators:
            body_actor.destroy()
        boundary_listener.violators.clear()

pyglet.clock.schedule_interval(step, time_step)
pyglet.clock.schedule_interval(create_letter, 0.5)

window = pyglet.window.Window(fullscreen=True)
window.set_exclusive_mouse()

def create_unit_circle_vertex_list(vertex_count):
    unit_circle_vertices = []
    for i in xrange(vertex_count + 1):
        angle = 2 * pi * float(i) / float(vertex_count)
        unit_circle_vertices.extend((cos(angle), sin(angle)))
    return pyglet.graphics.vertex_list(len(unit_circle_vertices) // 2,
                                       ('v2f', unit_circle_vertices))

unit_circle_vertex_list = create_unit_circle_vertex_list(64)

def debug_draw():
    glColor3f(0., 1., 0.)
    world_aabb = world.GetWorldAABB()
    min_x, min_y = world_aabb.lowerBound.tuple()
    max_x, max_y = world_aabb.upperBound.tuple()
    vertices = [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y,
                min_x, min_y]
    pyglet.graphics.draw(len(vertices) // 2, GL_LINE_STRIP, ('v2f', vertices))
    for body in world.bodyList:
        glPushMatrix()
        glTranslatef(body.position.x, body.position.y, 0.)
        glRotatef(body.angle * 180. / pi, 0., 0., 1.)
        for shape in body.shapeList:
            if isinstance(shape, b2PolygonShape):
                vertices = []
                for vertex in shape.vertices:
                    vertices.extend(vertex)
                vertices.extend(shape.vertices[0])
                pyglet.graphics.draw(len(vertices) // 2, GL_LINE_STRIP,
                                     ('v2f', vertices))
            elif isinstance(shape, b2CircleShape):
                glScalef(shape.radius, shape.radius, shape.radius)
                unit_circle_vertex_list.draw(GL_LINE_STRIP)
        glPopMatrix()

@window.event
def on_draw():
    window.clear()
    glColor3f(1., 1., 1.)
    for body in world.bodyList:
        body_actor = body.userData
        if body_actor is not None:
            glPushMatrix()
            glTranslatef(body.position.x, body.position.y, 0.)
            if config.rotate_letters:
                glRotatef(body.angle * 180. / pi, 0., 0., 1.)
            scale = 0.05 * body.shapeList[0].radius
            glScaled(scale, scale, scale)
            body_actor.label.draw()
            glPopMatrix()
    if config.debug_draw:
        debug_draw()

class Camera(object):
    def __init__(self, position=(0., 0.), scale=1., rotation=0.):
        self.position = position
        self.scale = scale
        self.rotation = rotation

    def update(self, width, height):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        aspect = float(width) / float(height)
        gluOrtho2D(-self.scale * aspect, self.scale * aspect,
                   -self.scale, self.scale)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        x, y = self.position
        gluLookAt(x, y, 1., x, y, -1.,
                  sin(self.rotation), cos(self.rotation), 0.)

camera = Camera(position=(0., 5.), scale=20.)

@window.event
def on_resize(width, height):
    camera.update(width, height)

@window.event
def on_show():
    on_resize(window.width, window.height)

pyglet.app.run()
