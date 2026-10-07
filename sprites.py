"""RETRO RACER DELUXE - sprites.py
Pixel-art sprite data and builder functions, plus the garage car
catalogue (stats, prices, colors). Canonical version: if your local
copy was modified, replace it with this one."""
import pygame

from core import PIX, load_profile


# ------------------------------- sprites ------------------------------------
# 11x16 pixel car facing up. 1 body, 2 window glass, 4 headlight,
# 5 wheel, 6 taillight. Shared by both modes.
CAR_PX = [
    "..1111111..",   # square nose (sharp corners)
    ".441111144.",
    ".111111111.",   # headlights
    "51111111115",   # front axle (wheel nubs)
    "51222222215",
    ".122222221.",   # windshield
    ".122222221.",   # roof
    ".111111111.",
    ".111111111.",
    ".111111111.",
    ".111111111.",   # rear window
    ".122222221.",   # trunk
    "51222222215",   # rear axle (wheel nubs)
    "51111111115",
    ".111111111.",
    ".661111166.",   # taillights
]

FUEL_PX = [          # blue jerrycan
    "............",
    "....7777....",
    "....7887....",
    "..77777777..",
    "..77888777..",
    "..77888777..",
    "..77777777..",
    "..77777777..",
    "..77777777..",
    "..77777777..",
    "..77777777..",
    "............",
]

BOOST_PX = [         # yellow lightning bolt
    "........88..",
    ".......888..",
    "......888...",
    ".....888....",
    "....88888...",
    "......888...",
    ".....888....",
    "....888.....",
    "...888......",
    "..888.......",
    "..88........",
    "..8.........",
]

WRENCH_PX = [        # green cross (repair kit)
    "............",
    "....9999....",
    "....9999....",
    "....9999....",
    "999999999999",
    "999999999999",
    "....9999....",
    "....9999....",
    "....9999....",
    "....9999....",
    "............",
    "............",
]

CASH_PX = [          # green dollar bill with a $ squiggle
    "............",
    "..44444444..",
    ".4222222224.",
    ".4221221224.",
    ".4222122224.",
    ".4222212224.",
    ".4221222224.",
    ".4221221224.",
    ".4222222224.",
    "..44444444..",
    "............",
    "............",
]

CASH_PAL = {"4": (20, 83, 45), "2": (74, 222, 128), "1": (255, 255, 255)}

# circuit mode: body, dark, accent
CAR_COLORS = {
    "red":    ((212, 58, 47), (143, 32, 24), (255, 210, 74)),
    "white":  ((232, 232, 232), (154, 154, 154), (159, 216, 255)),
    "teal":   ((47, 168, 160), (26, 106, 100), (255, 224, 138)),
    "purple": ((138, 79, 200), (90, 47, 136), (255, 210, 74)),
}

# scroll mode: body, dark
SC_CAR_COLORS = {
    "red":    ((212, 58, 47), (143, 32, 24)),
    "white":  ((230, 230, 230), (160, 160, 160)),
    "teal":   ((52, 211, 153), (16, 132, 92)),
    "purple": ((138, 79, 200), (90, 47, 136)),
}


def make_car_surface(color):
    """Circuit sprite: darker window glass."""
    body, dark, light = CAR_COLORS[color]
    surf = pygame.Surface((11 * PIX, 16 * PIX), pygame.SRCALPHA)
    lookup = {"1": body, "2": (58, 58, 90), "4": (255, 250, 180),
              "5": (28, 28, 32), "6": (255, 90, 80)}
    for r, row in enumerate(CAR_PX):
        for c, ch in enumerate(row):
            if ch in lookup:
                surf.fill(lookup[ch], (c * PIX, r * PIX, PIX, PIX))
    return surf


def sprite(px, pal, pix=PIX):
    w, h = len(px[0]), len(px)
    s = pygame.Surface((w * pix, h * pix), pygame.SRCALPHA)
    for y, row in enumerate(px):
        for x, ch in enumerate(row):
            if ch in pal:
                s.fill(pal[ch], (x * pix, y * pix, pix, pix))
    return s


def car_sprite(color, pix=PIX):
    """Scroll sprite: body-colored roof (pix: optional larger scale)."""
    body, dark = SC_CAR_COLORS[color]
    return sprite(CAR_PX, {"1": body, "2": dark, "4": (255, 255, 200),
                           "5": (30, 30, 30), "6": (255, 80, 80)}, pix)


# a silhouette lying face-down, seen from above: head, arms flung out,
# torso, legs - one of the people who never got home from a race
BODY_PX = [
    "............",
    "....111.....",
    ".11.111.11..",
    ".11.111.11..",
    "....111.....",
    "....1.1.....",
    "....1.1.....",
    "............",
]


def body_surface(pix=PIX):
    """A dark body lying in the grass / on the road (haunted scenery)."""
    return sprite(BODY_PX, {"1": (26, 24, 28)}, pix)


def wreck_surface(color, pix=PIX):
    """A burnt-out car, tilted the way it was left after the crash -
    the charred paint still remembers which car it used to be."""
    body, dark = SC_CAR_COLORS[color]
    surf = sprite(CAR_PX, {"1": _gloom(body, 4), "2": _gloom(dark, 4),
                           "4": (110, 40, 26), "5": (18, 16, 18),
                           "6": (60, 30, 26)}, pix)
    return pygame.transform.rotate(surf, 24)


# side-view dragster facing right: 1 body, 2 driver, 4 exhaust, 5 wheels
DRAG_PX = [
    "....222...........",
    "...1222...........",
    ".1111112222111144.",
    "155511111111111444",
    "555551111111111144",
    "55555..........55.",
    ".555..............",
]


def dragster_surface(body, dark):
    """Build a dragster sprite in the given body color."""
    pal = {"1": body, "2": dark, "4": (40, 40, 44), "5": (24, 24, 28)}
    return sprite(DRAG_PX, pal)


# ------------------------------- the garage ---------------------------------
# player cars: better stats cost more cash. "max" is a top-speed bonus (px/s),
# "steer" a steering-rate bonus (fraction), the two top cars have spoilers.
CARS = [
    {"name": "PONY", "price": 0, "max": 0, "steer": 0.00, "spoiler": False,
     "body": (212, 58, 47), "dark": (143, 32, 24), "desc": "stock all-rounder"},
    {"name": "VIPER", "price": 4000, "max": 30, "steer": 0.15, "spoiler": False,
     "body": (47, 168, 160), "dark": (26, 106, 100), "desc": "sharper steering"},
    {"name": "STING", "price": 12000, "max": 60, "steer": 0.25, "spoiler": True,
     "body": (138, 79, 200), "dark": (90, 47, 136), "desc": "light chassis, spoiler"},
    {"name": "RAZOR", "price": 30000, "max": 100, "steer": 0.40, "spoiler": True,
     "body": (230, 230, 230), "dark": (140, 140, 140), "desc": "top-class racer"},
]


def player_car_surface(spec, pix=PIX):
    """Player car sprite for a garage spec: own body color (+ spoiler).
    pix: optional larger scale (the scroll game draws chunkier cars)."""
    px = list(CAR_PX)
    if spec.get("spoiler"):
        px.append("5.........5")     # spoiler struts
        px.append("33333333333")     # spoiler wing
    pal = {"1": spec["body"], "2": spec["dark"], "3": spec["dark"],
           "4": (255, 255, 200), "5": (30, 30, 30), "6": (255, 80, 80)}
    return sprite(px, pal, pix)


def selected_car():
    return CARS[load_profile()[2]]


# --------------------------- the driver (profile) ----------------------------
# pixel person, front view: 1 hair, 2 skin, 6 eyes, 3 clothes, 9 pants,
# 5 shoes. Colors come from CLOTHES_COLORS / HAIR_COLORS below.
PERSON_PX = [
    "....1111....",   # hair
    "..11111111..",
    "..11111111..",
    "..22222222..",   # forehead
    "..26222262..",   # eyes
    "..22222222..",   # face
    "...222222...",   # chin
    "..33333333..",   # shoulders (racing suit)
    ".3333333333.",
    "333333333333",   # arms
    "233333333332",
    "2.33333333.2",
    "..33333333..",
    "..99999999..",   # pants
    "..999..999..",   # legs
    "..999..999..",
    "..99....99..",
    ".555....555.",   # shoes
    "5555....5555",
]

CLOTHES_COLORS = [
    ("red", (212, 58, 47)), ("teal", (47, 168, 160)),
    ("purple", (138, 79, 200)), ("white", (230, 230, 230)),
    ("gold", (255, 210, 74)), ("blue", (56, 189, 248)),
    ("green", (74, 222, 128)), ("black", (30, 30, 30)),
]
HAIR_COLORS = [
    ("brown", (75, 50, 33)), ("black", (25, 25, 25)),
    ("blond", (235, 195, 95)), ("ginger", (190, 80, 40)),
    ("gray", (160, 160, 165)), ("punk purple", (150, 80, 220)),
]

# hats: 12-wide pixel overlays drawn on top of the head (4 rows)
CAP_PX = [
    "....3333....",
    "..33333333..",
    ".3333333333.",
    "3333........",    # brim to the left
]
BEANIE_PX = [
    "....3333....",
    "..33333333..",
    ".3333333333.",
    ".4444444444.",    # folded rim
]
COWBOY_PX = [
    "....3333....",
    "....3443....",    # band
    "....3333....",
    "333333333333",    # wide brim
]
CROWN_PX = [
    ".3...3...3..",    # points
    ".3...3...3..",
    ".3333333333.",
    ".3434343434.",    # jewel band
]

HATS = [
    {"name": "NONE", "price": 0, "px": None, "pal": None},
    {"name": "CAP", "price": 300, "px": CAP_PX,
     "pal": {"3": (212, 58, 47), "4": (143, 32, 24)}},
    {"name": "BEANIE", "price": 800, "px": BEANIE_PX,
     "pal": {"3": (47, 168, 160), "4": (26, 106, 100)}},
    {"name": "COWBOY", "price": 2500, "px": COWBOY_PX,
     "pal": {"3": (120, 82, 48), "4": (90, 62, 30)}},
    {"name": "CROWN", "price": 10000, "px": CROWN_PX,
     "pal": {"3": (255, 210, 74), "4": (143, 110, 30)}},
]


# ------------------------------ the medicine ---------------------------------
# once the story turns (haunt stage 4) the hat shop sells only pills.
# They cannot fix what happened - buying them just deepens the gloom.
PILL_BOTTLE_PX = [     # orange bottle, white cap
    "............",
    "....8888....",
    "....8888....",
    "..77777777..",
    "..77777777..",
    "..77177177..",
    "..77177177..",
    "..77777777..",
    "..77777777..",
    "..77777777..",
    "............",
]

BLISTER_PX = [         # foil pack with a grid of pills
    "............",
    "..22222222..",
    "..21121121..",
    "..21121121..",
    "..22222222..",
    "..21121121..",
    "..21121121..",
    "..22222222..",
    "............",
]

JAR_PX = [             # squat jar of sleeping pills
    "............",
    "....8888....",
    "..77777777..",
    ".7777777777.",
    ".7711771177.",
    ".7711771177.",
    ".7777777777.",
    ".7777777777.",
    "..77777777..",
    "............",
]

MEDS = [
    {"name": "ST. JOHN'S WORT", "price": 300, "px": BLISTER_PX,
     "pal": {"1": (200, 225, 160), "2": (150, 170, 130)}},
    {"name": "ANTIDEPRESSANT", "price": 800, "px": PILL_BOTTLE_PX,
     "pal": {"7": (222, 140, 60), "8": (235, 235, 235), "1": (240, 200, 120)}},
    {"name": "SLEEPING PILLS", "price": 2500, "px": JAR_PX,
     "pal": {"7": (70, 110, 170), "8": (200, 200, 210), "1": (170, 200, 240)}},
    {"name": "HEAVY SEDATIVE", "price": 10000, "px": PILL_BOTTLE_PX,
     "pal": {"7": (110, 40, 60), "8": (60, 60, 70), "1": (200, 120, 140)}},
]


def med_surface(i, pix=PIX):
    """One of the medicines from the (haunted) profile shop."""
    m = MEDS[i % len(MEDS)]
    return sprite(m["px"], m["pal"], pix)


def _gloom(c, mood):
    """Blend a color toward grey - the driver's colours fade with guilt."""
    if mood <= 0:
        return tuple(c)
    f = 0.22 * min(mood, 4)
    g = sum(c) / 3.0
    return tuple(int(v + (g - v) * f) for v in c)


def _draw_gloom(surf, pix, mood, headroom):
    """Overdraw a gloomier face: heavy eyelids, downturned mouth."""
    skin = _gloom((234, 192, 134), mood)
    dark = (40, 40, 44)
    ey = headroom + 4 * pix              # the eye row of PERSON_PX
    for ex in (3, 8):                    # the two eye columns
        surf.fill(skin, (ex * pix, ey, pix, pix))
        surf.fill(dark, (ex * pix, ey + pix // 2, pix, pix - pix // 2))
    if mood >= 2:                        # a flat, unhappy line of a mouth
        surf.fill(dark, (5 * pix, ey + pix, 2 * pix, max(1, pix // 2)))


def person_surface(clothes_i, hair_i, hat_i=0, pix=PIX, mood=0):
    """The driver for the profile screen: own clothes and hair colors
    plus the selected hat (with headroom above the head for the hat).
    mood (haunt stage, 0-4) drains the colours and the face."""
    body = CLOTHES_COLORS[clothes_i % len(CLOTHES_COLORS)][1]
    hair = HAIR_COLORS[hair_i % len(HAIR_COLORS)][1]
    pal = {"1": _gloom(hair, mood), "2": _gloom((234, 192, 134), mood),
           "6": (40, 40, 44), "3": _gloom(body, mood),
           "9": _gloom(tuple(int(c * 0.6) for c in body), mood),
           "5": (50, 50, 55)}
    body_surf = sprite(PERSON_PX, pal, pix)
    headroom = 2 * pix        # space above the head so a hat fits
    surf = pygame.Surface((body_surf.get_width(),
                           body_surf.get_height() + headroom), pygame.SRCALPHA)
    surf.blit(body_surf, (0, headroom))
    hat = HATS[hat_i % len(HATS)]
    if hat["px"]:
        surf.blit(sprite(hat["px"], hat["pal"], pix), (0, 0))
    if mood:
        _draw_gloom(surf, pix, mood, headroom)
    return surf


def driver_face_surface(clothes_i, hair_i, hat_i=0, pix=PIX, mood=0):
    """Face + torso crop of the driver for the in-game corner HUD
    (head, hair and torso rows of PERSON_PX only - no legs).
    mood (haunt stage, 0-4) drains the colours and the face."""
    body = CLOTHES_COLORS[clothes_i % len(CLOTHES_COLORS)][1]
    hair = HAIR_COLORS[hair_i % len(HAIR_COLORS)][1]
    pal = {"1": _gloom(hair, mood), "2": _gloom((234, 192, 134), mood),
           "6": (40, 40, 44), "3": _gloom(body, mood),
           "9": _gloom(tuple(int(c * 0.6) for c in body), mood),
           "5": (50, 50, 55)}
    body_surf = sprite(PERSON_PX[:13], pal, pix)   # head + torso rows
    headroom = 2 * pix        # space above the head so a hat fits
    surf = pygame.Surface((body_surf.get_width(),
                           body_surf.get_height() + headroom), pygame.SRCALPHA)
    surf.blit(body_surf, (0, headroom))
    hat = HATS[hat_i % len(HATS)]
    if hat["px"]:
        surf.blit(sprite(hat["px"], hat["pal"], pix), (0, 0))
    if mood:
        _draw_gloom(surf, pix, mood, headroom)
    return surf
