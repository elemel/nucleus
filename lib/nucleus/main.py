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
    def __init__(self, words):
        self.letter_tree = {}
        self.letter_counts = defaultdict(int)
        for word in words:
            self._add_word(word)

    def _add_word(self, word):
        tree = self.letter_tree
        for letter in word:
            self.letter_counts[letter] += 1
            tree = tree.setdefault(letter, {})
        tree[u''] = None

    def get_next_letters(self, prefix):
        tree = self.letter_tree
        for letter in prefix:
            if letter in tree:
                tree = tree[letter]
            else:
                return set()
        return set(tree)

def parse_dictionary():
    def read_words():
        alphabet = set(config.alphabet)
        with codecs.open(config.dictionary_file, 'r',
                         config.dictionary_encoding) as file_obj:
            for line in file_obj:
                word = line.strip().upper()
                if not set(word) - alphabet:
                    yield word
    return Dictionary(read_words())

def unpickle_dictionary():
    with open('nucleus.pickle') as file_obj:
        return pickle.load(file_obj)

def pickle_dictionary(dictionary):
    with open('nucleus.pickle', 'w') as file_obj:
        pickle.dump(dictionary, file_obj, pickle.HIGHEST_PROTOCOL)

class MyWindow(pyglet.window.Window):
    def __init__(self, **kwargs):
        super(MyWindow, self).__init__(**kwargs)
        if self.fullscreen:
            self.set_exclusive_mouse()
        self.scale = self.height / config.view_height
        self.font = pyglet.font.load(name=config.font_name,
                                     size=(self.scale * config.font_scale),
                                     bold=config.font_bold)
        self.letter_sets = defaultdict(set)
        self.selection = []
        self.batch = pyglet.graphics.Batch()
        self.score = 0
        self.score_label = pyglet.text.Label('SCORE %d' % self.score,
                                             font_size=self.scale, bold=True)

        try:
            self.dictionary = unpickle_dictionary()
        except IOError:
            self.dictionary = parse_dictionary()
            pickle_dictionary(self.dictionary)

        self.screen_time = 0.
        self.world_time = 0.
        self.time_label = pyglet.text.Label('TIME ' + self.format_time(),
                                             font_size=self.scale, bold=True,
                                             anchor_x='right')

        self.world = self._create_world()
        self.boundary_listener = MyBoundaryListener()
        self.world.SetBoundaryListener(self.boundary_listener)

        self.circle_vertex_list = self._create_circle_vertex_list()

    def _create_world(self):
        aabb = b2AABB()
        aabb.lowerBound = -100., -100.
        aabb.upperBound = 100., 100.
        return b2World(aabb, (0., 0.), True)

    def format_time(self):
        return '%d:%02d' % divmod(int(config.time - self.world_time), 60)

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
            if u'' in self.dictionary.get_next_letters(word):
                print word
                multiplier = 1
                score = len(self.selection)
                for i, actor in enumerate(self.selection):
                    for other in self.selection[i + 1:]:
                        if ((actor.body.GetWorldCenter() -
                             other.body.GetWorldCenter()).LengthSquared()
                             < (actor.radius + other.radius + 0.5) ** 2):
                             multiplier += 1
                for actor in list(self.selection):
                    self._destroy_letter(actor)
                actors = list(chain(*self.letter_sets.values()))
                actors.sort(key=self.get_actor_key)
                for actor in actors[:multiplier]:
                    self._destroy_letter(actor)
                self.score += multiplier * score
                self.score_label.text = 'SCORE %d' % self.score
            else:
                del self.selection[:]
        else:
            actors = self.letter_sets[symbol_string] - set(self.selection)
            if actors:
                self.selection.append(min(actors, key=self.get_actor_key))

    def get_last_position(self):
        if self.selection:
            return self.selection[-1].body.position
        else:
            return b2Vec2(0., 0.)

    def get_actor_key(self, actor):
        return (actor.body.position - self.get_last_position()).LengthSquared()

    def create_letter(self, dt):
        letter_count = sum(len(s) for s in self.letter_sets.values())
        if letter_count >= config.letter_count:
            return

        letter = random.choice(config.alphabet)
        body_def = b2BodyDef()
        creation_angle = 2. * pi * random.random()
        body_def.position = (config.creation_distance *
                             b2Vec2(cos(creation_angle), sin(creation_angle)))
        body_def.angle = 2 * pi * random.random()
        body = self.world.CreateBody(body_def)
        shape_def = b2CircleDef()
        radius = (config.min_radius +
                  random.random() * (config.max_radius - config.min_radius))
        shape_def.radius = radius
        shape_def.density = config.density
        shape_def.restitution = config.restitution
        shape_def.friction = config.friction
        body.CreateShape(shape_def)
        body.SetMassFromShapes()
        glyph = self.font.get_glyphs(letter)[0]
        glyph.anchor_x = glyph.width // 2
        glyph.anchor_y = glyph.height // 2
        sprite = pyglet.sprite.Sprite(glyph, batch=self.batch,
                                      subpixel=config.subpixel)
        if config.scale_letters:
            sprite.scale = radius
        actor = Actor(body, letter, sprite, radius)
        body.userData = actor
        self.letter_sets[letter].add(actor)

    def on_draw(self):
        glClearColor(*(tuple(config.background_color) + (0,)))
        self.clear()
        word = u''.join(a.letter for a in self.selection)
        next_letters = self.dictionary.get_next_letters(word)
        next_actors = set()
        for letter in next_letters:
            actors = self.letter_sets[letter] - set(self.selection)
            if actors:
                next_actors.add(min(actors, key=self.get_actor_key))
        for body in self.world.bodyList:
            actor = body.userData
            if actor is not None:
                if actor in self.selection:
                    if u'' in next_letters:
                        actor.sprite.color = config.word_color
                    elif next_letters:
                        actor.sprite.color = config.prefix_color
                    else:
                        actor.sprite.color = config.error_color
                elif config.hint and actor in next_actors:
                    actor.sprite.color = config.hint_color
                else:
                    actor.sprite.color = config.color
                world_x, world_y = body.position.tuple()
                screen_x = world_x * self.scale + self.width // 2
                screen_y = world_y * self.scale + self.height // 2
                actor.sprite.position = screen_x, screen_y
                if config.rotate_letters:
                    actor.sprite.rotation = -body.angle * 180. / pi
        self.batch.draw()
        if config.debug_draw:
            self._debug_draw()
        self.score_label.draw()
        self.time_label.x = self.width
        self.time_label.draw()

    def _create_circle_vertex_list(self,
                                   vertex_count=config.circle_vertex_count):
        unit_circle_vertices = []
        for i in xrange(vertex_count + 1):
            angle = 2 * pi * float(i) / float(vertex_count)
            unit_circle_vertices.extend((cos(angle), sin(angle)))
        return pyglet.graphics.vertex_list(len(unit_circle_vertices) // 2,
                                           ('v2f', unit_circle_vertices))

    def _debug_draw(self):
        glColor3ub(*config.debug_color)
        glPushMatrix()
        glTranslatef(float(self.width // 2), float(self.height // 2), 0.)
        glScalef(self.scale, self.scale, self.scale)
        world_aabb = self.world.GetWorldAABB()
        min_x, min_y = world_aabb.lowerBound.tuple()
        max_x, max_y = world_aabb.upperBound.tuple()
        vertices = (min_x, min_y, max_x, min_y, max_x, max_y, min_x, max_y,
                    min_x, min_y)
        pyglet.graphics.draw(len(vertices) // 2, GL_LINE_STRIP,
                             ('v2f', vertices))
        for body in self.world.bodyList:
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
                    self.circle_vertex_list.draw(GL_LINE_STRIP)
            glPopMatrix()
        glPopMatrix()

    def step(self, dt):
        self.screen_time += dt
        while self.world_time + config.time_step <= self.screen_time:
            self.world_time += config.time_step
            for body in self.world.bodyList:
                force = -(config.spring_constant * body.GetWorldCenter() +
                          config.damping * body.GetLinearVelocity())
                body.ApplyForce(force, body.GetWorldCenter())
            self.world.Step(config.time_step, 10, 8)
            for actor in self.boundary_listener.violators:
                self._destroy_letter(actor)
            self.boundary_listener.violators.clear()
        if self.world_time < config.time:
            self.time_label.text = 'TIME ' + self.format_time()
        else:
            print 'SCORE %d' % self.score
            self.on_close()

    def _destroy_letter(self, actor):
        if actor in self.selection:
            self.selection.remove(actor)
        self.letter_sets[actor.letter].remove(actor)
        self.world.DestroyBody(actor.body)
        actor.sprite.delete()

class MyBoundaryListener(b2BoundaryListener):
    def __init__(self):
        super(MyBoundaryListener, self).__init__()
        self.violators = set()

    def Violation(self, body):
        actor = body.userData
        if actor is not None:
            self.violators.add(actor)

class Actor(object):
    def __init__(self, body, letter, sprite, radius):
        self.body = body
        self.letter = letter
        self.sprite = sprite
        self.radius = radius

def main():
    window = MyWindow(fullscreen=config.fullscreen)
    pyglet.clock.schedule_interval(window.step, config.time_step)
    pyglet.clock.schedule_interval(window.create_letter,
                                   config.creation_interval)
    pyglet.app.run()
    
if __name__ == '__main__':
    main()
