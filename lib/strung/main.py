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

# Monkey patch for subpixel option.
pyglet.sprite.Sprite = sprite.Sprite

class Dictionary(object):
    def __init__(self):
        self.alphabet = set(config.alphabet.upper())
        self._load_words()
        self._count_letters()
        self._set_prefixes()

    def _load_words(self):
        self.words = set()
        with codecs.open(config.dictionary_file, 'r',
                         config.dictionary_encoding) as file_obj:
            for line in file_obj:
                word = line.strip().upper()
                if not set(word) - self.alphabet:
                    self.words.add(word)

    def _count_letters(self):
        self.letter_counts = defaultdict(int)
        for word in self.words:
            for letter in word:
                self.letter_counts[letter] += 1

    def _set_prefixes(self):
        self.prefixes = set()
        for word in self.words:
            for i in xrange(1, len(word)):
                self.prefixes.add(word[:i])

def load_dictionary():
    with open('strung.pickle') as file_obj:
        return pickle.load(file_obj)

def save_dictionary(dictionary):
    with open('strung.pickle', 'w') as file_obj:
        pickle.dump(dictionary, file_obj, pickle.HIGHEST_PROTOCOL)

class MyWindow(pyglet.window.Window):
    def __init__(self, **kwargs):
        super(MyWindow, self).__init__(**kwargs)
        if self.fullscreen:
            self.set_exclusive_mouse()
        self.font = pyglet.font.load(name=config.font_name,
                                     size=config.font_size,
                                     dpi=config.font_dpi,
                                     bold=config.font_bold)
        self.letter_lists = defaultdict(list)
        self.selection = []
        self.batch = pyglet.graphics.Batch()
        self.next_letters = set()

        try:
            self.dictionary = load_dictionary()
        except IOError:
            self.dictionary = Dictionary()
            save_dictionary(self.dictionary)

        self.screen_time = 0.
        self.world_time = 0.

        self.world = self._create_world(aabb=((-50., -25.), (50., 75.)),
                                        gravity=(0., -10.), do_sleep=True)
        self.boundary_listener = MyBoundaryListener()
        self.world.SetBoundaryListener(self.boundary_listener)

        self._create_wall(half_width=15., half_height=0.5, position=(0., -10.),
                          angle=0.2)
        self._create_wall(half_width=0.5, half_height=10.,
                          position=(-15., -5.), angle=0.5)
        self._create_wall(half_width=0.5, half_height=10., position=(15., 0.),
                          angle=-0.2)

        self.circle_vertex_list = self._create_circle_vertex_list()
        self.camera = Camera(position=(0., 5.), scale=20.)

    def _create_world(self, aabb, gravity=(0., 0.), do_sleep=True):
        lower_bound, upper_bound = aabb
        aabb = b2AABB()
        aabb.lowerBound = lower_bound
        aabb.upperBound = upper_bound
        return b2World(aabb, gravity, do_sleep)

    def on_key_press(self, symbol, modifiers):
        symbol_string = pyglet.window.key.symbol_string(symbol)
        if symbol_string.startswith('user_key('):
            user_key = int(symbol_string[9:-1], 16)
            symbol_string = config.user_keys.get(user_key, symbol_string)
        if symbol == pyglet.window.key.ESCAPE:
            self.on_close()
        elif symbol == pyglet.window.key.BACKSPACE:
            if self.selection:
                self.selection.pop()
        elif symbol == pyglet.window.key.ENTER:
            word = u''.join(a.letter for a in self.selection)
            if word in self.dictionary.words:
                for body_actor in self.selection:
                    self.letter_lists[body_actor.letter].remove(body_actor)
                    body_actor.destroy()
                del self.selection[:]
        else:
            letter_list = self.letter_lists[symbol_string]
            if not self.selection:
                if letter_list:
                    self.selection.append(letter_list[0])
            else:
                matching_letters = set(letter_list).difference(self.selection)
                if matching_letters:
                    def key(letter):
                        return (self.selection[-1].body.position -
                                letter.body.position).LengthSquared()
                    self.selection.append(min(matching_letters, key=key))

    def _create_wall(self, half_width, half_height, position, angle=0.):
        ground_body_def = b2BodyDef()
        ground_body = self.world.CreateBody(ground_body_def)
        ground_shape_def = b2PolygonDef()
        ground_shape_def.SetAsBox(half_width, half_height, position, angle)
        ground_shape_def.restitution = config.restitution
        ground_shape_def.friction = config.friction
        ground_body.CreateShape(ground_shape_def)

    def _create_letter(self, dt):
        letter = random.choice(config.alphabet)
        body_def = b2BodyDef()
        body_def.position = 10. * (random.random() - 0.5), 30.
        body_def.angle = 2 * pi * random.random()
        body = self.world.CreateBody(body_def)
        shape_def = b2CircleDef()
        shape_def.radius = 1. + random.random()
        shape_def.density = 1.
        shape_def.restitution = config.restitution
        shape_def.friction = config.friction
        body.CreateShape(shape_def)
        body.SetMassFromShapes()
        body.linearVelocity = 0., -5.
        body.angularVelocity = 2. * (random.random() - 0.5)
        glyph = self.font.get_glyphs(letter)[0]
        glyph.anchor_x = glyph.width // 2
        glyph.anchor_y = glyph.height // 2
        sprite = pyglet.sprite.Sprite(glyph, batch=self.batch, subpixel=True)
        body_actor = BodyActor(body, letter, sprite)
        body.userData = body_actor
        self.letter_lists[letter].append(body_actor)

    def on_draw(self):
        self._update_next_letters()
        self.clear()
        for body in self.world.bodyList:
            body_actor = body.userData
            if body_actor is not None:
                if body_actor in self.selection:
                    word = u''.join(a.letter for a in self.selection)
                    if word in self.dictionary.words:
                        body_actor.sprite.color = 0, 255, 0
                    elif word in self.dictionary.prefixes:
                        body_actor.sprite.color = 255, 255, 0
                    else:
                        body_actor.sprite.color = 255, 0, 0
                elif body_actor in self.next_letters:
                        body_actor.sprite.color = 0, 255, 255
                else:
                    body_actor.sprite.color = 255, 255, 255
                body_actor.sprite.position = body.position.tuple()
                if config.rotate_letters:
                    body_actor.sprite.rotation = -body.angle * 180. / pi
                body_actor.sprite.scale = 0.05 * body.shapeList[0].radius
        self.batch.draw()
        if config.debug_draw:
            self._debug_draw()

    def _update_next_letters(self):
        self.next_letters.clear()
        for letter_list in self.letter_lists.itervalues():
            for letter in letter_list:
                if letter not in self.selection:
                    self.next_letters.add(letter)
                    break

    def _create_circle_vertex_list(self,
                                   vertex_count=config.circle_vertex_count):
        unit_circle_vertices = []
        for i in xrange(vertex_count + 1):
            angle = 2 * pi * float(i) / float(vertex_count)
            unit_circle_vertices.extend((cos(angle), sin(angle)))
        return pyglet.graphics.vertex_list(len(unit_circle_vertices) // 2,
                                           ('v2f', unit_circle_vertices))

    def _debug_draw(self):
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
                    self.circle_vertex_list.draw(GL_LINE_STRIP)
            glPopMatrix()

    def on_resize(self, width, height):
        self.camera.update(width, height)

    def on_show(self):
        self.on_resize(self.width, self.height)

    def _step(self, dt):
        self.screen_time += dt
        while self.world_time + config.time_step <= self.screen_time:
            self.world_time += config.time_step
            self.world.Step(config.time_step, 10, 8)
            for body_actor in self.boundary_listener.violators:
                self.letter_lists[body_actor.letter].remove(body_actor)
                body_actor.destroy()
            self.boundary_listener.violators.clear()

class MyBoundaryListener(b2BoundaryListener):
    def __init__(self):
        super(MyBoundaryListener, self).__init__()
        self.violators = set()

    def Violation(self, body):
        body_actor = body.userData
        if body_actor is not None:
            self.violators.add(body_actor)

class BodyActor(object):
    def __init__(self, body, letter, sprite):
        self.body = body
        self.letter = letter
        self.sprite = sprite

    def destroy(self):
        if self.body is not None:
            self.body.GetWorld().DestroyBody(self.body)
            self.body = None
        if self.sprite is not None:
            self.sprite.delete()
            self.sprite = None

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

def main():
    window = MyWindow(fullscreen=config.fullscreen)
    pyglet.clock.schedule_interval(window._step, config.time_step)
    pyglet.clock.schedule_interval(window._create_letter, 0.5)
    pyglet.app.run()
    
if __name__ == '__main__':
    main()
