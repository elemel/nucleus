# encoding: UTF-8

# Debug draw.
debug_draw = False
debug_color = 0, 255, 0

# Physics simulation.
world_radius = 100.
time_step = 1. / 60.
friction = 1.
restitution = 0.
density = 1.
spring_constant = 10.
damping = 5.
destroy_force = 500.

# Presentation.
rotate_letters = True
scale_letters = True
subpixel = True
circle_vertex_count = 64
fullscreen = True
view_height = 25.

# Gameplay.
letter_count = 46
hint = False
time_limit = 30.
creation_distance = 30.
creation_interval = 0.2
min_radius = 0.8
max_radius = 1.2
levels = [10, 30, 60, 100, 150, 210, 280, 360, 450, 550, 660, 780, 910, 1050]
extra_time = 30.

# Data files.
word_list_file = 'enable.txt'
word_list_encoding = 'ASCII'
alphabet = u'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
cache_word_list = True

# Font.
font_name = None
font_bold = True
font_scale = 1.

# Colors.
color = 255, 255, 255
background_color = 0, 0, 0
hint_color = 0, 255, 255
prefix_color = 255, 255, 0
word_color = 0, 255, 0
error_color = 255, 0, 0
destroy_color = 255, 0, 255
