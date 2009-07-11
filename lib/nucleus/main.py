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

    def complete(self, prefix):
        tree = self.letter_tree
        for letter in prefix:
            if letter in tree:
                tree = tree[letter]
            else:
                return set()
        return set(tree)

    def random_letter(self):
        total_count = sum(self.letter_counts.values())
        random_count = random.randrange(total_count)
        for letter, count in self.letter_counts.items():
            if random_count < count:
                return letter
            random_count -= count
        return None

    @staticmethod
    def parse():
        def read_words():
            alphabet = set(config.alphabet)
            with codecs.open(config.dictionary_file, 'r',
                             config.dictionary_encoding) as file_obj:
                for line in file_obj:
                    word = line.strip().upper()
                    if not set(word) - alphabet:
                        yield word
        return Dictionary(read_words())

    @staticmethod
    def unpickle():
        with open(config.pickle_file) as file_obj:
            return pickle.load(file_obj)

    def pickle(self):
        with open(config.pickle_file, 'w') as file_obj:
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

        try:
            self.dictionary = Dictionary.unpickle()
        except IOError:
            self.dictionary = Dictionary.parse()
            self.dictionary.pickle()

        self._init_gl()
        self.my_screen = TitleScreen(self)

    def _init_gl(self):
        clear_color = [float(c) / 255. for c in config.background_color]
        clear_color.append(0.)
        glClearColor(*clear_color)

    def on_draw(self):
        self.my_screen.on_draw()

    def on_key_press(self, symbol, modifiers):
        self.my_screen.on_key_press(symbol, modifiers)

    def on_text(self, text):
        self.my_screen.on_text(text)

class TitleScreen(object):
    def __init__(self, window):
        self.window = window
        self.batch = pyglet.graphics.Batch()
        self._init_labels()

    def _init_labels(self):
        self.title_label = pyglet.text.Label('Nucleus',
                                             font_size=(self.window.scale *
                                                        1.5),
                                             bold=True,
                                             x=(self.window.width // 2),
                                             y=(self.window.height * 2 // 3),
                                             anchor_x='center',
                                             anchor_y='center',
                                             batch=self.batch)
        self.instr_label = pyglet.text.Label(config.instr_label,
                                             font_size=(self.window.scale /
                                                        1.5),
                                             bold=True,
                                             x=(self.window.width // 2),
                                             y=(self.window.height // 3),
                                             anchor_x='center',
                                             anchor_y='center',
                                             batch=self.batch)

    def on_draw(self):
        self.window.clear()
        self.batch.draw()

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.window.on_close()
        if symbol in (pyglet.window.key.SPACE, pyglet.window.key.ENTER):
            self.window.my_screen = GameScreen(self.window)

    def on_text(self, text):
        pass

class GameScreen(object):
    def __init__(self, window):
        self.window = window
        self.closing = False
        self.actors = set()
        self.letter_sets = defaultdict(set)
        self.selection = []
        self.batch = pyglet.graphics.Batch()
        self.score = 0

        self.screen_time = 0.
        self.world_time = 0.

        self.level = 1
        self.time_limit = config.time_limit

        self.letter_count = 0

        self.world = self._create_world()
        self.boundary_listener = MyBoundaryListener()
        self.world.SetBoundaryListener(self.boundary_listener)

        self.circle_vertex_list = self._create_circle_vertex_list()

        self._init_labels()

        pyglet.clock.schedule_interval(self.step, config.time_step)
        pyglet.clock.schedule_interval(self.create_letter,
                                       config.creation_interval)

    def close(self):
        pyglet.clock.unschedule(self.step)
        pyglet.clock.unschedule(self.create_letter)
        self.window.my_screen = TitleScreen(self.window)

    def _init_labels(self):
        font_size = self.window.scale / 1.5
        self.level_label = pyglet.text.Label(font_size=font_size, bold=True,
                                             anchor_x='left', anchor_y='top',
                                             batch=self.batch)
        self.letters_label = pyglet.text.Label(font_size=font_size, bold=True,
                                               anchor_x='right',
                                               anchor_y='top',
                                               batch=self.batch)
        self.score_label = pyglet.text.Label(font_size=font_size, bold=True,
                                             batch=self.batch)
        self.time_label = pyglet.text.Label(font_size=font_size, bold=True,
                                            anchor_x='right',
                                            batch=self.batch)
        self._update_labels()

    def _create_world(self):
        aabb = b2AABB()
        aabb.lowerBound = -config.world_radius, -config.world_radius
        aabb.upperBound = config.world_radius, config.world_radius
        return b2World(aabb, (0., 0.), True)

    def format_time(self):
        seconds = max(int(self.time_limit - self.world_time), 0)
        minutes, seconds = divmod(seconds, 60)
        return '%d:%02d' % (minutes, seconds)

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.ESCAPE:
            self.close()
        elif symbol == pyglet.window.key.BACKSPACE:
            if self.selection:
                self.selection.pop()
        elif symbol == pyglet.window.key.ENTER:
            word = u''.join(a.letter for a in self.selection)
            if u'' in self.window.dictionary.complete(word):
                print word
                multiplier = 1
                score = len(self.selection)
                self.letter_count += len(self.selection)
                for i, actor in enumerate(self.selection):
                    for other in self.selection[i + 1:]:
                        if ((actor.body.GetWorldCenter() -
                             other.body.GetWorldCenter()).LengthSquared()
                             < (actor.radius + other.radius + 0.5) ** 2):
                             multiplier += 1
                for actor in list(self.selection):
                    self._clear_letter(actor)
                self.score += multiplier * score
            else:
                del self.selection[:]

    def on_text(self, text):
        for letter in text.upper():
            actors = self.letter_sets[letter] - set(self.selection)
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
        if self.closing or letter_count >= config.letter_count:
            return

        letter = self.window.dictionary.random_letter()
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
        glyph = self.window.font.get_glyphs(letter)[0]
        glyph.anchor_x = glyph.width // 2
        glyph.anchor_y = glyph.height // 2
        sprite = pyglet.sprite.Sprite(glyph, batch=self.batch,
                                      subpixel=config.subpixel)
        if config.scale_letters:
            sprite.scale = radius
        actor = Actor(body, letter, sprite, radius)
        body.userData = actor
        self.actors.add(actor)
        self.letter_sets[letter].add(actor)

    def on_draw(self):
        self.window.clear()
        self._update_sprites()
        self._update_labels()
        self.batch.draw()
        if config.debug_draw:
            self._debug_draw()

    def _update_sprites(self):
        prefix = u''.join(a.letter for a in self.selection)
        hint_letters = self.window.dictionary.complete(prefix)
        hint_actors = set()
        if config.hint:
            for letter in next_letters:
                actors = self.letter_sets[letter] - set(self.selection)
                if actors:
                    hint_actors.add(min(actors, key=self.get_actor_key))
        for body in self.world.bodyList:
            actor = body.userData
            if actor is not None:
                if actor.letter is None:
                    actor.sprite.color = config.destroy_color
                elif actor in self.selection:
                    if u'' in hint_letters:
                        actor.sprite.color = config.word_color
                    elif hint_letters:
                        actor.sprite.color = config.prefix_color
                    else:
                        actor.sprite.color = config.error_color
                elif actor in hint_actors:
                    actor.sprite.color = config.hint_color
                else:
                    actor.sprite.color = config.color
                world_x, world_y = body.position.tuple()
                screen_x = world_x * self.window.scale + self.window.width // 2
                screen_y = (world_y * self.window.scale +
                            self.window.height // 2)
                actor.sprite.position = screen_x, screen_y
                if config.rotate_letters:
                    actor.sprite.rotation = -body.angle * 180. / pi

    def _update_labels(self):
        self._update_level_label()
        self._update_letters_label()
        self._update_score_label()
        self._update_time_label()

    def _update_level_label(self):
        self.level_label.text = u'%s %d' % (config.level_label, self.level)
        self.level_label.x = self.window.scale / 2.
        self.level_label.y = self.window.height - self.window.scale / 2.

    def _update_letters_label(self):
        if self.level <= len(config.levels):
            self.letters_label.text = u'%s %d/%d' % (config.letters_label,
                                                     self.letter_count,
                                                     config.levels[self.level -
                                                                   1])
        else:
            self.letters_label.text = u'%s %d' % (config.letters_label,
                                                  self.letter_count)
        self.letters_label.x = self.window.width - self.window.scale / 2.
        self.letters_label.y = self.window.height - self.window.scale / 2.

    def _update_score_label(self):
        self.score_label.text = u'%s %d' % (config.score_label, self.score)
        self.score_label.x = self.window.scale / 2.
        self.score_label.y = self.window.scale / 2.

    def _update_time_label(self):
        self.time_label.text = '%s %s' % (config.time_label,
                                          self.format_time())        
        self.time_label.x = self.window.width - self.window.scale / 2.
        self.time_label.y = self.window.scale / 2.

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
        glTranslatef(float(self.window.width // 2),
                     float(self.window.height // 2), 0.)
        glScalef(self.window.scale, self.window.scale, self.window.scale)
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
            if self.world_time > self.time_limit:
                self.closing = True
                self.clear_letters()
            elif (self.level <= len(config.levels) and
                  self.letter_count >= config.levels[self.level - 1]):
                self.level += 1
                self.time_limit += config.extra_time
                self.clear_letters()
            for body in self.world.bodyList:
                actor = body.userData
                if actor is not None:
                    if actor.letter is not None:
                        force = -(config.spring_constant *
                                  body.GetWorldCenter() +
                                  config.damping * body.GetLinearVelocity())
                    else:
                        direction = body.GetWorldCenter().copy()
                        direction.Normalize()
                        force = (config.destroy_force * direction -
                                config.damping * body.GetLinearVelocity())
                    body.ApplyForce(force, body.GetWorldCenter())
            self.world.Step(config.time_step, 10, 8)
            for actor in self.boundary_listener.violators:
                self._destroy_actor(actor)
            self.boundary_listener.violators.clear()
        if self.closing and not self.actors:
            self.close()

    def clear_letters(self):
        for body in self.world.bodyList:
            actor = body.userData
            if actor is not None:
                self._clear_letter(actor)

    def _clear_letter(self, actor):
        if actor in self.selection:
            self.selection.remove(actor)
        if actor.letter is not None:
            self.letter_sets[actor.letter].remove(actor)
            actor.letter = None

    def _destroy_actor(self, actor):
        self._clear_letter(actor)
        self.world.DestroyBody(actor.body)
        actor.sprite.delete()
        self.actors.remove(actor)

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
    pyglet.app.run()
    
if __name__ == '__main__':
    main()
