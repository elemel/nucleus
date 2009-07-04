from __future__ import with_statement

import config
import sprite
from Box2D import *
import pyglet
from pyglet.gl import *
import codecs
from collections import *
from itertools import *
from math import *
from operator import attrgetter
import cPickle as pickle
import random

pyglet.sprite.Sprite = sprite.Sprite

font = pyglet.font.load(name=config.font_name, size=config.font_size,
                        dpi=config.font_dpi, bold=config.font_bold)
letter_lists = defaultdict(list)
selection = []

batch = pyglet.graphics.Batch()

def read_words():
    try:
        with open('strung.pickle') as pickle_file:
            return pickle.load(pickle_file)
    except:
        pass

    print 'Reading dictionary...'
    dictionary = set()
    lower_alphabet_set = set(config.alphabet.lower())
    with codecs.open(config.dictionary_file, 'r',
                     config.dictionary_encoding) as file_obj:
        for line in file_obj:
            word = line.strip()
            if not set(word) - lower_alphabet_set:
                dictionary.add(word)

    print 'Counting letters...'
    letter_counts = defaultdict(int)
    for word in dictionary:
        for letter in word:
            letter_counts[letter] += 1

    with open('strung.pickle', 'w') as pickle_file:
        pickle.dump((dictionary, letter_counts), pickle_file,
                    pickle.HIGHEST_PROTOCOL)
    return dictionary, letter_counts

dictionary, letter_counts = read_words()
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
    ground_shape_def.restitution = config.restitution
    ground_shape_def.friction = config.friction
    ground_body.CreateShape(ground_shape_def)

create_wall(world, half_width=15., half_height=0.5, position=(0., -10.),
            angle=0.2)
create_wall(world, half_width=0.5, half_height=10., position=(-15., -5.),
            angle=0.5)
create_wall(world, half_width=0.5, half_height=10., position=(15., 0.),
            angle=-0.2)

class BodyActor(object):
    def __init__(self, body, letter, sprite):
        self.body = body
        self.letter = letter
        self.sprite = sprite

    def destroy(self):
        if self.body is not None:
            self.body.GetWorld().DestroyBody(self.body)
            self.body = None
        if self.letter is not None:
            letter_lists[self.letter].remove(self)
            self.letter = None
        if self.sprite is not None:
            self.sprite.delete()
            self.sprite = None

def create_letter(dt):
    letter = random.choice(config.alphabet)
    body_def = b2BodyDef()
    body_def.position = 10. * (random.random() - 0.5), 30.
    body_def.angle = 2 * pi * random.random()
    body = world.CreateBody(body_def)
    shape_def = b2CircleDef()
    shape_def.radius = 1. + random.random()
    shape_def.density = 1.
    shape_def.restitution = config.restitution
    shape_def.friction = config.friction
    body.CreateShape(shape_def)
    body.SetMassFromShapes()
    body.linearVelocity = 0., -5.
    body.angularVelocity = 2. * (random.random() - 0.5)
    glyph = font.get_glyphs(letter)[0]
    glyph.anchor_x = glyph.width // 2
    glyph.anchor_y = glyph.height // 2
    sprite = pyglet.sprite.Sprite(glyph, batch=batch, subpixel=True)
    body_actor = BodyActor(body, letter, sprite)
    body.userData = body_actor
    letter_lists[letter].append(body_actor)

screen_time = 0.
world_time = 0.

def step(dt):
    global screen_time, world_time
    screen_time += dt
    while world_time + config.time_step <= screen_time:
        world_time += config.time_step
        world.Step(config.time_step, 10, 8)
        for body_actor in boundary_listener.violators:
            body_actor.destroy()
        boundary_listener.violators.clear()

pyglet.clock.schedule_interval(step, config.time_step)
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

unit_circle_vertex_list = create_unit_circle_vertex_list(config.circle_vertex_count)

def debug_draw():
    glColor3f(0., 1., 0.)
    world_aabb = world.GetWorldAABB()
    min_x, min_y = world_aabb.lowerBound.tuple()
    max_x, max_y = world_aabb.upperBound.tuple()
    vertices = [min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y,
                min_x, min_y]
    pyglet.graphics.draw(len(vertices) // 2, GL_LINE_STRIP, ['v2f', vertices])
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
                                     ['v2f', vertices])
            elif isinstance(shape, b2CircleShape):
                glScalef(shape.radius, shape.radius, shape.radius)
                unit_circle_vertex_list.draw(GL_LINE_STRIP)
        glPopMatrix()

@window.event
def on_draw():
    window.clear()
    for body in world.bodyList:
        body_actor = body.userData
        if body_actor is not None:
            if body_actor in selection:
                body_actor.sprite.color = 255, 255, 0
            else:
                body_actor.sprite.color = 255, 255, 255
            body_actor.sprite.position = body.position.tuple()
            if config.rotate_letters:
                body_actor.sprite.rotation = -body.angle * 180. / pi
            body_actor.sprite.scale = 0.05 * body.shapeList[0].radius
    batch.draw()
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

@window.event
def on_key_press(symbol, modifiers):
    symbol_string = pyglet.window.key.symbol_string(symbol)
    if symbol_string.startswith('user_key('):
        user_key = int(symbol_string[9:-1], 16)
        symbol_string = config.user_keys.get(user_key, symbol_string)
    if symbol == pyglet.window.key.ESCAPE:
        window.on_close()
    elif symbol == pyglet.window.key.BACKSPACE:
        if selection:
            selection.pop()
    elif symbol == pyglet.window.key.ENTER:
        word = u''.join(a.letter for a in selection)
        if word.lower() in dictionary:
            for body_actor in selection:
                body_actor.destroy()
            del selection[:]
    else:
        letter_list = letter_lists[symbol_string]
        if not selection:
            if letter_list:
                selection.append(letter_list[0])
        else:
            matching_letters = set(letter_list).difference(selection)
            if matching_letters:
                def key(letter):
                    return (selection[-1].body.position -
                            letter.body.position).LengthSquared()
                selection.append(min(matching_letters, key=key))

pyglet.app.run()
