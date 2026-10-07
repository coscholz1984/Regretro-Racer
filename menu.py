"""RETRO RACER DELUXE - menu.py
Menu screens: the main menu (PLAY / GARAGE), the mini-game picker
and the garage (car showroom).

GAMES is the single registry of mini-games: each entry holds the menu
card name, the game class, its leaderboard file and an animated
preview scene for the picker (one page per game, LEFT/RIGHT flips).
Adding a new mini-game means writing the module and adding one entry
here - main.py needs no changes at all.

The previews and the screens rot with the haunt (see core.py): grass
turns red, wrecks and bodies appear in the previews, the garage
becomes an impound lot, and the profile shop sells medicine instead
of hats. active_games() swaps the races for the regret scenes."""
import math
import random

import pygame

from core import (FPS, LB_CIRCUIT, LB_DRAGSTER, LB_SCROLL, VH, VW,
                  arcade_mode, haunt_stage, haunt_title, load_board,
                  load_haunt, load_profile, load_skin, play, play_haunt,
                  save_profile, save_skin)
from sprites import (CARS, CLOTHES_COLORS, HAIR_COLORS, HATS, MEDS,
                     body_surface, car_sprite, dragster_surface,
                     make_car_surface, med_surface, person_surface,
                     player_car_surface, wreck_surface)
from circuit import CircuitGame
from scroll import ScrollGame
from dragster import (GAS_KEYS, KEY_NAMES, SHIFT_KEYS, DragsterGame)
from regret import (CourtScene, FlashbackGame, HospitalScene, MemorialScene,
                    MedsScene, preview_court, preview_hospital, preview_meds,
                    preview_memorial, preview_truth)
import music

# ============================================================================
# MINI-GAME PREVIEWS - one animated scene per game, drawn inside a rect
# (the caller clips to the rect). t is seconds since startup. The
# previews rot with the haunt: grass turns red, wrecks and bodies appear
# where the races happen, and every few seconds the picture jumps.
# ============================================================================
_st_cache = [0.0, 0]       # [when read, stage] - previews call per frame


def _haunt_st():
    """play_haunt(), cached for a second (the previews ask every frame).
    In arcade mode the previews show the innocent games again."""
    now = pygame.time.get_ticks() / 1000.0
    if now - _st_cache[0] > 1.0:
        _st_cache[0], _st_cache[1] = now, play_haunt()
    return _st_cache[1]


def _preview_scare(s, rect, t, st):
    """A deterministic jump-frame in the haunted previews: every 7 s
    the picture washes blood red or blacks out for a heartbeat, one
    word from the past stamped across it - then it flips back."""
    if st < 2:
        return
    ph = t % 7.0
    if ph >= 0.2:
        return
    wash = pygame.Surface(rect.size, pygame.SRCALPHA)
    if int(t // 7.0) % 2:
        wash.fill((6, 6, 10, 210))           # the lights go out
    else:
        wash.fill((160, 20, 20, 150))        # everything washes blood red
    s.blit(wash, rect.topleft)
    word = ("REMEMBER", "NOVEMBER", "THE BYPASS")[int(t // 7.0) % 3]
    txt = pygame.font.SysFont("monospace", 34, bold=True).render(
        word, True, (255, 46, 40))
    s.blit(txt, txt.get_rect(center=rect.center))


def _preview_circuit(s, rect, t):
    """Grass infield, asphalt oval and three cars lapping it. The
    grass sickens at stage 2, dries to blood at stage 3, and the
    infield fills with what the racing left behind."""
    st = _haunt_st()
    if st >= 3:                  # the grass remembers what rained on it
        grass = (122, 44, 32)
    elif st == 2:                # sickly, quietly dying
        grass = (86, 104, 34)
    else:
        grass = (49, 109, 37)
    pygame.draw.rect(s, grass, rect, border_radius=10)
    cx, cy = rect.center
    rx, ry = rect.w // 2 - 60, rect.h // 2 - 44
    half = 18                                   # asphalt ring half-width
    pygame.draw.ellipse(
        s, (90, 90, 90),
        (cx - rx - half, cy - ry - half, 2 * (rx + half), 2 * (ry + half)))
    pygame.draw.ellipse(
        s, grass,
        (cx - rx + half, cy - ry + half, 2 * (rx - half), 2 * (ry - half)))
    # dashed racing line along the oval
    for i in range(40):
        a = i * (2 * math.pi / 40)
        pygame.draw.circle(
            s, (216, 216, 216),
            (int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a))), 2)
    # the haunt: burnt-out wrecks abandoned on the infield (stage 2+),
    # and from stage 3 the people who never got out of the way
    if st >= 2:
        for wx, wy, col, ang in ((cx - 70, cy - 8, "white", 24),
                                 (cx + 66, cy + 22, "teal", -38)):
            spr = pygame.transform.rotate(wreck_surface(col), ang)
            s.blit(spr, spr.get_rect(center=(wx, wy)))
            if random.random() < 0.35:         # embers still glow
                pygame.draw.circle(
                    s, (255, 120 + random.randint(0, 80), 30),
                    (int(wx + random.uniform(-10, 10)),
                     int(wy + random.uniform(-6, 6))), 3)
    if st >= 3:
        pygame.draw.ellipse(s, (46, 10, 12),
                            (int(cx - 34), int(cy - 46), 48, 11))
        s.blit(body_surface(), (int(cx - 24), int(cy - 58)))
    # three cars lapping the oval, nose along the tangent - at stage
    # 3 the red one keeps drifting toward the edge of the track
    for col, speed, off in (("red", 0.9, 0.0), ("white", 0.8, 2.2),
                            ("teal", 0.7, 4.4)):
        a = off + t * speed
        wobble = (math.sin(t * 3.7) * 9 if (st >= 3 and col == "red")
                  else 0.0)
        x = cx + (rx - 14 + wobble) * math.cos(a)
        y = cy + (ry - 14 + wobble) * math.sin(a)
        dx, dy = -(rx - 14) * math.sin(a), (ry - 14) * math.cos(a)
        ang = -math.degrees(math.atan2(dx, -dy)) + wobble * 1.6
        car = pygame.transform.rotate(make_car_surface(col), ang)
        s.blit(car, car.get_rect(center=(x, y)))
    _preview_scare(s, rect, t, st)


def _preview_scroll(s, rect, t):
    """Vertical 4-lane highway: dashes, traffic and the player. The
    grass turns as the haunt deepens, a wreck smoulders on the
    shoulder, and at stage 3 the red cars come hunting."""
    st = _haunt_st()
    if st >= 3:                  # the grass remembers what rained on it
        grass = (98, 34, 26)
    elif st == 2:                # sickly, quietly dying
        grass = (74, 108, 32)
    else:
        grass = (58, 125, 21)
    pygame.draw.rect(s, grass, rect, border_radius=10)
    rw = 240
    lane = rw // 4
    road_x = rect.centerx - rw // 2
    pygame.draw.rect(s, (68, 68, 74), (road_x, rect.y, rw, rect.h))
    # three dashed dividers scroll down (the player races up the road)
    gap = 56
    off = int((t * 140) % gap)
    for y in range(rect.y - gap + off, rect.bottom + gap, gap):
        for lo in (-lane, 0, lane):
            pygame.draw.rect(s, (235, 235, 235),
                             (rect.centerx + lo - 2, y, 4, 20))
    # the haunt: a burnt-out wreck smoulders on the shoulder (stage 2+)
    if st >= 2:
        wx = road_x - 62
        wy = (t * -110) % (rect.h + 120) - 60 + rect.y
        spr = pygame.transform.rotate(wreck_surface("purple"), -30)
        s.blit(spr, spr.get_rect(center=(wx, wy)))
        if random.random() < 0.3:              # embers still glow
            pygame.draw.circle(
                s, (255, 120 + random.randint(0, 80), 30),
                (int(wx + random.uniform(-10, 10)),
                 int(wy + random.uniform(-6, 6))), 3)
    # oncoming traffic in the left lanes (faces down, races at you),
    # slower same-direction traffic in the right lanes (drifts past)
    for lane_off, vy, ph, col in ((-lane * 1.5, 210.0, 0.0, "white"),
                                  (lane * 1.5, 40.0, 0.55, "teal")):
        y = rect.y + (t * vy
                      + ph * (rect.h + 80)) % (rect.h + 80) - 40
        car = car_sprite(col, 4)
        if lane_off < 0:
            car = pygame.transform.rotate(car, 180)
        s.blit(car, car.get_rect(center=(rect.centerx + lane_off, y)))
    # player car weaving between the lanes near the bottom - from
    # stage 2 the wheel is MIRRORED: the car leans the wrong way
    px = rect.centerx + math.sin(t * 2.0) * (lane * 0.5)
    tilt = math.cos(t * 2.0) * 10
    if st >= 2:
        tilt = -tilt
    player = pygame.transform.rotate(car_sprite("red", 4), -tilt)
    # stage 3: a red hunter in the oncoming lanes, homing on the player
    if st >= 3:
        hx0 = rect.centerx - lane * 1.5
        frac = (t * 0.28) % 1.0          # slides across, then resets
        hx = hx0 + (px - hx0) * frac * 0.85
        hy = rect.y + (t * 260) % (rect.h + 80) - 40
        hunter = pygame.transform.rotate(car_sprite("red", 4), 180)
        s.blit(hunter, hunter.get_rect(center=(hx, hy)))
        # ...and someone is lying in the road ahead
        by = rect.y + (t * -90 + rect.h * 0.35) % (rect.h + 80)
        pygame.draw.ellipse(s, (46, 10, 12),
                            (int(rect.centerx + lane * 0.5 - 26),
                             int(by - 4), 52, 12))
        s.blit(body_surface(4), (int(rect.centerx + lane * 0.5 - 24),
                                 int(by - 16)))
    s.blit(player, player.get_rect(center=(px, rect.bottom - 40)))
    _preview_scare(s, rect, t, st)


def _preview_dragster(s, rect, t):
    """Night strip: staging tree, two dragsters, launch flames. From
    stage 2 the car demands its own keys (flashing, changing), wrecks
    smoulder behind the guardrails - and at stage 3 it explodes on a
    loop, exactly like the real thing."""
    st = _haunt_st()
    pygame.draw.rect(s, (24, 28, 38), rect, border_radius=10)
    # starfield above the strip
    for i in range(22):
        x = rect.x + 8 + (i * 211) % (rect.w - 16)
        y = rect.y + 8 + (i * 97) % 100
        pygame.draw.rect(s, (150, 150, 160), (x, y, 2, 2))
    cy = rect.centery + 20
    top, bot = cy - 58, cy + 58
    pygame.draw.rect(s, (68, 68, 74), (rect.x, top, rect.w, 48))
    pygame.draw.rect(s, (68, 68, 74), (rect.x, cy + 10, rect.w, 48))
    # red/white guardrails between the lanes and the dark
    for x in range(rect.x, rect.right, 30):
        c = (224, 90, 26) if (x // 30) % 2 == 0 else (235, 235, 235)
        pygame.draw.rect(s, c, (x, top - 6, 30, 6))
        pygame.draw.rect(s, c, (x, bot, 30, 6))
    # the haunt: burnt-out wrecks behind the rails (stage 2+) - and
    # from stage 3, a silhouette that never got across in time
    if st >= 2:
        for wx, wy, col, ang in ((rect.right - 78, top - 30, "white", 30),
                                 (rect.x + rect.w * 0.42, bot + 28,
                                  "teal", -22)):
            spr = pygame.transform.rotate(wreck_surface(col), ang)
            s.blit(spr, spr.get_rect(center=(wx, wy)))
            if random.random() < 0.35:         # embers still glow
                pygame.draw.circle(
                    s, (255, 120 + random.randint(0, 80), 30),
                    (int(wx + random.uniform(-10, 10)),
                     int(wy + random.uniform(-6, 6))), 3)
    if st >= 3:
        bx = rect.x + rect.w * 0.72
        by = bot + 30
        pygame.draw.ellipse(s, (46, 10, 12),
                            (int(bx - 24), int(by - 5), 48, 11))
        s.blit(body_surface(), (int(bx - 18), int(by - 12)))
    # lane dashes scroll to the right
    off = int((t * 160) % 40)
    for x in range(rect.x - 40 + off, rect.right + 40, 40):
        pygame.draw.rect(s, (235, 235, 235), (x, cy - 2, 22, 4))
    # start and finish checker columns
    for xc in (rect.x + 10, rect.right - 18):
        for j in range((bot - top) // 4):
            c = (245, 245, 245) if j % 2 == 0 else (20, 20, 20)
            pygame.draw.rect(s, c, (xc, top + j * 4, 8, 4))
    # staging tree: three ambers, then green, on a 4 s cycle
    phase = t % 4.0
    for k in range(3):
        on = phase > 0.8 * (k + 1)
        pygame.draw.circle(
            s, (255, 180, 40) if on else (90, 80, 50),
            (rect.x + 40, rect.y + 62 + k * 17), 5)
    green = phase > 2.4
    pygame.draw.circle(
        s, (74, 222, 128) if green else (40, 80, 50),
        (rect.x + 40, rect.y + 113), 5)
    # stage 2+: the keys the car demands tonight, flashing red and
    # changing on their own every 5 s - exactly like the real race
    if st >= 2:
        i = int(t // 5.0) % len(GAS_KEYS)
        hint = (f"GAS {KEY_NAMES[GAS_KEYS[i]]}"
                f"  SHIFT {KEY_NAMES[SHIFT_KEYS[i]]}")
        col = (239, 68, 68) if pygame.time.get_ticks() // 250 % 2 \
            else (255, 255, 255)
        f = pygame.font.SysFont("monospace", 20, bold=True)
        txt = f.render(("TONIGHT: " if st >= 3 else "")
                       + hint, True, col)
        s.blit(txt, (rect.right - txt.get_width() - 18, rect.y + 14))
    # two dragsters revving at the line, exhaust flame on green -
    # from stage 2 the flames burn an uneasy, bloodier red
    rival = dragster_surface((138, 79, 200), (90, 47, 136))
    player = dragster_surface((212, 58, 47), (143, 32, 24))
    rx, ry = rect.x + rect.w * 0.58, cy - 34 + math.sin(t * 18) * 1
    px, py = rect.x + rect.w * 0.58 - 60, cy + 34 - math.sin(t * 18) * 1
    flame = (239, 68, 68) if st >= 2 else (255, 210, 74)
    if green:
        for cx_, cy_ in ((rx, ry), (px, py)):
            l = random.uniform(8, 18)
            pygame.draw.rect(s, flame,
                             (int(cx_ - rival.get_width() / 2 - l),
                              int(cy_ - 3), int(l), 6))
    s.blit(rival, rival.get_rect(center=(rx, ry)))
    # stage 3: every 9 s the car decides it has had enough - the
    # fireball swallows it, then only smoke remains, then it starts over
    boom = t % 9.0 if st >= 3 else 99.0
    if boom >= 1.6:
        s.blit(player, player.get_rect(center=(px, py)))
    else:
        if boom < 0.12:
            col, rad = (255, 255, 225), int(10 + 260 * boom)
        elif boom < 0.5:
            col, rad = (255, 170, 40), int(58 + 60 * boom)
        elif boom < 1.0:
            col, rad = (200, 60, 25), int(88 - 20 * boom)
        else:
            col, rad = (70, 62, 60), int(68 + 40 * (boom - 1.0))
        pygame.draw.circle(s, col, (int(px), int(py)), rad)
    _preview_scare(s, rect, t, st)


# ============================================================================
# MINI-GAME REGISTRY - add a new game by appending one entry here
# ============================================================================
GAMES = [
    {"name": "CIRCUIT", "cls": CircuitGame, "lb": LB_CIRCUIT,
     "desc": "3 laps - dodge the AI cars, pit for fuel",
     "preview": _preview_circuit},
    {"name": "SCROLL", "cls": ScrollGame, "lb": LB_SCROLL,
     "desc": "3000 m dash - traffic, pickups, gas stops",
     "preview": _preview_scroll},
    {"name": "DRAGSTER", "cls": DragsterGame, "lb": LB_DRAGSTER,
     "desc": "quarter-mile drag race - shift at the redline",
     "preview": _preview_dragster},
]

MENU_NAMES = ["PLAY", "GARAGE", "PROFILE"]
MENU_DESCS = ["pick a mini-game and race", "spend your cash on faster cars",
              "your name, racing outfit and hats"]
MENU_MODES = ["play", "garage", "profile"]

# stage-flavoured names and descriptions for the three racing cards:
# the unease sets in at stage 1, the corruption at stage 2+
RACE_NAMES = [
    ("CIRCUIT", "SCROLL", "DRAGSTER"),
    ("CIRCUIT", "SCROLL", "DRAGSTER"),
    ("GUILT CIRCUIT", "SORROW SCROLL", "DRUGSTER"),
]
RACE_DESCS = [
    ("3 laps - dodge the AI cars, pit for fuel",
     "3000 m dash - traffic, pickups, gas stops",
     "quarter-mile drag race - shift at the redline"),
    ("3 laps - the track remembers you",
     "3000 m dash - the traffic looks familiar",
     "quarter mile - the exhaust smells old"),
    ("3 laps - the wheel is mirrored",
     "3000 m - they are waiting for you",
     "quarter mile - the car decides the keys"),
]


def active_games():
    """The game registry, haunted: stage 4 replaces the races with the
    courtroom, the hospital room and the nightstand; once those are
    relived the truth unlocks, and after the truth only the memorial
    remains. main.py reads this, so it never changes. In arcade mode
    (unlocked after the truth) the clean versions return - cash, no
    ghosts."""
    if arcade_mode():
        return [dict(g) for g in GAMES]
    st = haunt_stage()
    if st >= 5:
        return [{"name": "MEMORIAL", "cls": MemorialScene, "lb": None,
                 "desc": "what happened, and what it cost",
                 "preview": preview_memorial}]
    if st >= 4:
        entries = [
            {"name": "COURT", "cls": CourtScene, "lb": None,
             "desc": "the people vs. you - relive the verdict",
             "preview": preview_court},
            {"name": "HOSPITAL", "cls": HospitalScene, "lb": None,
             "desc": "room 214 - the sirens, the rain",
             "preview": preview_hospital},
            {"name": "MEDS", "cls": MedsScene, "lb": None,
             "desc": "the nightstand - what you took, and why",
             "preview": preview_meds},
        ]
        if len(load_haunt()["scenes"]) >= 3:
            entries.append({"name": "THE TRUTH", "cls": FlashbackGame,
                            "lb": None, "desc": "remember. all of it.",
                            "preview": preview_truth})
        return entries
    names = RACE_NAMES[min(st, 2)]
    descs = RACE_DESCS[min(st, 2)]
    out = []
    for g, nm, ds in zip(GAMES, names, descs):
        e = dict(g)
        e["name"], e["desc"] = nm, ds
        out.append(e)
    return out


# ============================================================================
# SHARED DRAWING HELPERS
# ============================================================================
def draw_background(s, t):
    """Subtle moving stripes in the background for a retro feel."""
    s.fill((24, 28, 38))
    for x in range(0, VW, 80):
        off = int((t * 30) % 80)
        pygame.draw.rect(s, (30, 35, 48), (x - off + 40, 0, 4, VH))


def draw_wallet(s, app, cash):
    """Persistent cash wallet (top right)."""
    wallet = app.font_big.render(f"${cash}", True, (74, 222, 128))
    s.blit(wallet, (VW - wallet.get_width() - 24, 18))
    wl = app.font.render("CASH", True, (180, 180, 180))
    s.blit(wl, (VW - wallet.get_width() - 24, 62))


def draw_card(s, app, i, sel, y, name, desc, side_text):
    """One 540x96 menu card: name, side info and description line."""
    box = pygame.Rect(VW / 2 - 270, y, 540, 96)
    if i == sel:
        pygame.draw.rect(s, (44, 52, 70), box, border_radius=8)
        pygame.draw.rect(s, (255, 210, 74), box, 3, border_radius=8)
    else:
        pygame.draw.rect(s, (40, 44, 58), box, border_radius=8)
        pygame.draw.rect(s, (90, 96, 120), box, 2, border_radius=8)
    name_col = (255, 210, 74) if i == sel else (200, 200, 200)
    nm = app.font_big.render(name, True, name_col)
    s.blit(nm, (box.x + 24, box.y + 8))
    bs = app.font.render(side_text, True, (120, 200, 255))
    s.blit(bs, (box.right - bs.get_width() - 20, box.y + 22))
    ds = app.font.render(desc, True, (170, 170, 170))
    s.blit(ds, (box.x + 24, box.y + 60))
    if i == sel:
        mk = app.font.render(">", True, (255, 210, 74))
        s.blit(mk, (box.x - 28, box.y + 34))


# ============================================================================
# SCREENS
# ============================================================================
def run_menu(app):
    """Main menu: returns "play", "garage", "profile", "arcade",
    "story" (toggles arcade mode after the truth) or "reset" (erase
    the arc and start over - CTRL+R in the aftermath story menu,
    confirmed with a second press)."""
    sel = 0
    car = pygame.transform.rotate(car_sprite("red"), -90)
    t = 0.0
    cash, owned, _ = load_profile()
    skin = load_skin()
    st = haunt_stage()              # read once per visit (never mid-menu)
    vh = play_haunt()               # what the menu itself looks like
    arcade = arcade_mode()
    n_games = len(active_games())   # how many things there are to face
    names = list(MENU_NAMES)
    modes = list(MENU_MODES)
    descs = list(MENU_DESCS)
    if vh >= 2:
        descs = ["pick a memory and drive it again",
                 "the cars wait quietly in the dark",
                 "your name, your guilt, your medicine"]
    if arcade:
        descs[0] = "the old races, just for cash - no ghosts"
    if st >= 5:
        # after the truth: a door back to the clean, innocent games.
        # (resetting the arc is not a card - there is no room for a
        # fifth one; the hint line offers CTRL+R instead, story mode
        # only)
        if arcade:
            names.append("STORY")
            modes.append("story")
            descs.append("return to the aftermath")
        else:
            names.append("ARCADE")
            modes.append("arcade")
            descs.append("the old races, just for cash - no ghosts")
    confirm = False        # first CTRL+R asks "sure?", the second resets
    while True:
        dt = min(0.05, app.clock.tick(FPS) / 1000)
        t += dt
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_m:
                    music.toggle_mute(app)
                elif e.key == pygame.K_F11:
                    app.toggle_fullscreen()
                elif e.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % len(names)
                    confirm = False
                    play(app, "blip", 0.6)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % len(names)
                    confirm = False
                    play(app, "blip", 0.6)
                elif e.key == pygame.K_RETURN:
                    play(app, "go")
                    return modes[sel]
                elif (e.key == pygame.K_r and st >= 5 and not arcade
                      and pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if confirm:            # second press: do it
                        play(app, "go")
                        return "reset"
                    confirm = True         # first press: ask first
                    play(app, "blip", 0.6)
                elif e.key in (pygame.K_q, pygame.K_ESCAPE):
                    return None

        s = app.screen
        draw_background(s, t)
        # the title rots: RETRO RACER -> REGRETRO RACER -> REGRET RACER
        # (in arcade mode it is the clean RETRO RACER again)
        title_col = (255, 210, 74)
        if vh == 1:
            title_col = (255, 170, 74)
        elif vh >= 2:
            title_col = (200, 60, 60)
            if vh >= 3 and pygame.time.get_ticks() // 600 % 5 == 0:
                title_col = (120, 20, 20)     # a slow, uneasy flicker
        title = app.font_big.render(haunt_title(), True, title_col)
        s.blit(title, title.get_rect(center=(VW / 2, 80)))
        s.blit(app.font.render("MAIN MENU", True, (180, 180, 180)),
               (VW / 2 - app.font.render("MAIN MENU", True, (0, 0, 0)).get_width() / 2, 128))
        draw_wallet(s, app, cash)

        y0, dy = (170, 110) if len(names) == 3 else (132, 100)
        for i, name in enumerate(names):
            if i == 0:
                side = (f"{n_games} race(s) to run" if arcade
                        else f"{n_games} thing(s) to face")
            elif i == 1:
                side = f"{len(owned)} car(s) owned"
            elif i == 3:
                side = ("in arcade mode" if arcade
                        else "unlocked: just for cash")
            else:
                side = f"driver: {skin['name']}"
            draw_card(s, app, i, sel, y0 + i * dy,
                      name, descs[i], side)

        # the aftermath menu can forget the whole arc: the hint line
        # mentions it (story mode only - in arcade, switch back first)
        if confirm:
            hint = ("CTRL+R again: forget the story and start over "
                    "- arrows cancel")
            hint_col = (239, 68, 68)
        elif st >= 5 and not arcade:
            hint = ("ARROWS select - ENTER start - CTRL+R reset story "
                    "- M sound - Q quit")
            hint_col = (120, 220, 140)
        else:
            hint = ("ARROWS select - ENTER start - M sound "
                    "- F11 fullscreen - Q quit")
            hint_col = (120, 220, 140)
        hs = app.font.render(hint, True, hint_col)
        s.blit(hs, hs.get_rect(center=(VW / 2, VH - 56)))

        # little car cruising along the bottom for flavor:
        # rotated 90 degrees clockwise (nose points in the driving
        # direction) with flickering nitro flames at its rear - from
        # stage 2 on the flames burn an uneasy, bloodier red
        cx_ = (t * 160) % (VW + 120) - 60
        cy = VH - 24 + math.sin(t * 6) * 2
        rear = cx_ - car.get_width() / 2       # rear end of the car
        flame_col = (255, 210, 74) if vh < 2 else (239, 68, 68)
        for fy in (-8, 0, 8):
            l = random.uniform(10, 22)
            pygame.draw.rect(s, flame_col,
                             (rear - l, cy + fy - 3, int(l), 6))
        s.blit(car, car.get_rect(center=(cx_, cy)))
        pygame.display.flip()


def run_game_select(app):
    """Mini-game picker: one page per game, LEFT/RIGHT flips through
    them. Returns an index into active_games(), or None to go back to
    the main menu. At haunt stage 4+ the "games" are the regret scenes."""
    games = active_games()
    sel = 0
    boards = [load_board(g["lb"]) if g.get("lb") else []
              for g in games]           # read once per visit
    st = play_haunt()
    while True:
        dt = min(0.05, app.clock.tick(FPS) / 1000)
        t = pygame.time.get_ticks() / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return None
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_m:
                    music.toggle_mute(app)
                elif e.key == pygame.K_F11:
                    app.toggle_fullscreen()
                elif e.key in (pygame.K_LEFT, pygame.K_a):
                    sel = (sel - 1) % len(games)
                    play(app, "blip", 0.6)
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    sel = (sel + 1) % len(games)
                    play(app, "blip", 0.6)
                elif e.key == pygame.K_RETURN:
                    play(app, "go")
                    return sel
                elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                    return None

        s = app.screen
        draw_background(s, t)
        head = "RELIVE" if st >= 4 else "SELECT MINI-GAME"
        title = app.font_big.render(head, True,
                                    (200, 60, 60) if st >= 4
                                    else (255, 210, 74))
        s.blit(title, title.get_rect(center=(VW / 2, 60)))
        draw_wallet(s, app, load_profile()[0])

        # one showcase page: animated preview stage + info below
        g = games[sel]
        stage = pygame.Rect(VW / 2 - 300, 96, 600, 320)
        pygame.draw.rect(s, (40, 44, 58), stage, border_radius=10)
        inner = stage.inflate(-6, -6)
        s.set_clip(inner)
        g["preview"](s, inner, t)
        s.set_clip(None)
        pygame.draw.rect(s, (255, 210, 74), stage, 3, border_radius=10)

        # flip arrows beside the stage (dim when there is nothing to
        # flip to - they light up as soon as a second game exists)
        acol = (255, 210, 74) if len(games) > 1 else (90, 96, 120)
        for x, txt in ((stage.x - 40, "<"), (stage.right + 40, ">")):
            ar = app.font_big.render(txt, True, acol)
            s.blit(ar, ar.get_rect(center=(x, stage.centery)))

        # page dots: one per entry, the current one lit
        for i in range(len(games)):
            dcol = (255, 210, 74) if i == sel else (90, 96, 120)
            dx = VW / 2 + (i - (len(games) - 1) / 2.0) * 24 - 6
            pygame.draw.rect(s, dcol, (int(dx), 430, 12, 12))

        # name, description and best time of the shown game
        nm_col = (200, 60, 60) if st >= 4 else (255, 210, 74)
        nm = app.font_big.render(g["name"], True, nm_col)
        s.blit(nm, nm.get_rect(center=(VW / 2, 474)))
        ds = app.font.render(g["desc"], True, (170, 170, 170))
        s.blit(ds, ds.get_rect(center=(VW / 2, 506)))
        best = boards[sel][0] if boards[sel] else None
        bt = f"best {best['time']:.1f}s" if best else "no record yet"
        bs = app.font.render(bt, True, (120, 200, 255))
        s.blit(bs, bs.get_rect(center=(VW / 2, 528)))

        hint = "LEFT/RIGHT flip - ENTER start - ESC back to the menu"
        hs = app.font.render(hint, True, (120, 220, 140))
        s.blit(hs, hs.get_rect(center=(VW / 2, VH - 26)))
        pygame.display.flip()


def run_impound(app):
    """Haunt stage 4+: the cars have been seized as evidence."""
    while True:
        dt = min(0.05, app.clock.tick(FPS) / 1000)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_m:
                    music.toggle_mute(app)
                elif e.key == pygame.K_F11:
                    app.toggle_fullscreen()
                elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                    return "menu"

        s = app.screen
        s.fill((18, 18, 22))
        # chain-link fence over everything
        for x in range(0, VW + 28, 28):
            pygame.draw.line(s, (60, 62, 70), (x, 90), (x + 14, VH - 40))
            pygame.draw.line(s, (60, 62, 70), (x + 14, 90), (x, VH - 40))
        title = app.font_big.render("IMPOUND LOT", True, (160, 160, 165))
        s.blit(title, title.get_rect(center=(VW / 2, 52)))
        t1 = app.font.render("your cars have been seized as evidence.",
                             True, (220, 220, 220))
        s.blit(t1, t1.get_rect(center=(VW / 2, 280)))
        t2 = app.font.render(
            "they are exactly where you left them: parked, silent, done.",
            True, (170, 170, 170))
        s.blit(t2, t2.get_rect(center=(VW / 2, 312)))
        t3 = app.font.render("the garage is closed. the keys are elsewhere.",
                             True, (140, 140, 150))
        s.blit(t3, t3.get_rect(center=(VW / 2, 344)))
        hint = "ESC back"
        hs = app.font.render(hint, True, (120, 220, 140))
        s.blit(hs, hs.get_rect(center=(VW / 2, VH - 26)))
        pygame.display.flip()


def run_garage(app):
    """Car showroom: buy faster cars with cash, or select an owned one.
    Returns "menu" (ESC) or "quit" (window closed)."""
    if play_haunt() >= 4:
        return run_impound(app)
    _, _, sel = load_profile()
    sprites = [player_car_surface(spec) for spec in CARS]
    while True:
        cash, owned, selected = load_profile()
        dt = min(0.05, app.clock.tick(FPS) / 1000)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_m:
                    music.toggle_mute(app)
                elif e.key == pygame.K_F11:
                    app.toggle_fullscreen()
                elif e.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % len(CARS)
                    play(app, "blip", 0.6)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % len(CARS)
                    play(app, "blip", 0.6)
                elif e.key == pygame.K_RETURN:
                    if sel in owned:
                        save_profile(cash, owned, sel)
                        play(app, "blip")
                    elif cash >= CARS[sel]["price"]:
                        cash -= CARS[sel]["price"]
                        owned.append(sel)
                        save_profile(cash, owned, sel)
                        play(app, "ding")
                    else:
                        play(app, "warn")
                elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                    return "menu"

        s = app.screen
        s.fill((24, 28, 38))
        title = app.font_big.render("GARAGE", True, (255, 210, 74))
        s.blit(title, title.get_rect(center=(VW / 2, 52)))
        draw_wallet(s, app, cash)

        for i, spec in enumerate(CARS):
            y = 108 + i * 104
            box = pygame.Rect(VW / 2 - 300, y, 600, 94)
            if i == sel:
                pygame.draw.rect(s, (44, 52, 70), box, border_radius=8)
                pygame.draw.rect(s, (255, 210, 74), box, 3, border_radius=8)
            else:
                pygame.draw.rect(s, (40, 44, 58), box, border_radius=8)
                pygame.draw.rect(s, (90, 96, 120), box, 2, border_radius=8)
            if i == selected:
                pygame.draw.rect(s, (74, 222, 128), box.inflate(-10, -10), 2,
                                 border_radius=6)
            # preview sprite (bobs a little)
            bob = math.sin(pygame.time.get_ticks() / 400.0 + i) * 3
            s.blit(sprites[i], sprites[i].get_rect(
                center=(box.x + 54, box.centery + bob)))
            # name + description + stats
            name_col = (255, 210, 74) if i == sel else (200, 200, 200)
            nm = app.font.render(spec["name"], True, name_col)
            s.blit(nm, (box.x + 120, box.y + 10))
            ds = app.font.render(spec["desc"], True, (170, 170, 170))
            s.blit(ds, (box.x + 120, box.y + 34))
            st = app.font.render(
                f"TOP +{spec['max']}   STEER +{int(spec['steer'] * 100)}%",
                True, (120, 200, 255))
            s.blit(st, (box.x + 120, box.y + 58))
            # status / price on the right
            if i == selected:
                txt, col = "SELECTED", (74, 222, 128)
            elif i in owned:
                txt, col = "OWNED - press ENTER", (220, 220, 220)
            elif cash >= spec["price"]:
                txt, col = f"buy ${spec['price']}", (255, 210, 74)
            else:
                txt, col = f"need ${spec['price']}", (239, 68, 68)
            ss_ = app.font.render(txt, True, col)
            s.blit(ss_, (box.right - ss_.get_width() - 20, box.y + 34))

        hint = "ARROWS browse - ENTER buy/select - ESC back"
        hs = app.font.render(hint, True, (120, 220, 140))
        s.blit(hs, hs.get_rect(center=(VW / 2, VH - 26)))
        pygame.display.flip()


# ============================================================================
# DRIVER PROFILE (name, clothes, hair and hats)
# ============================================================================
COMPLIMENTS = [
    "You're the fastest thing around!",
    "Your lap times fear YOU.",
    "Champion material, obviously!",
    "Even the AI wants your autograph.",
    "Racing royalty, right here!",
    "Pure speed. Zero fear.",
    "Rivals tremble at your shifts!",
    "The track is your living room.",
    "Ten out of ten - style AND speed!",
    "Simply unstoppable, champ!",
]

# from haunt stage 1 the compliments stop being compliments
CONFESSIONS = [
    "the trophies feel heavy lately.",
    "you still hear the sirens sometimes.",
    "the mirror does not look like you.",
    "it rained again last night. it always does.",
    "the bypass called. you didn't answer.",
    "winning used to feel like something.",
    "the radio only plays that one song.",
    "you park two streets away from home.",
]


def draw_speech_bubble(s, app, x, y, text):
    """Rounded speech bubble with a little tail pointing down-left."""
    txt = app.font_small.render(text, True, (255, 255, 255))
    box = pygame.Rect(x, y, txt.get_width() + 24, txt.get_height() + 18)
    pygame.draw.rect(s, (44, 52, 70), box, border_radius=10)
    pygame.draw.rect(s, (255, 210, 74), box, 2, border_radius=10)
    pygame.draw.polygon(s, (44, 52, 70), [
        (box.x + 28, box.y + box.h - 2),
        (box.x + 84, box.y + box.h - 2),
        (box.x + 52, box.y + box.h + 14)])
    s.blit(txt, (box.x + 12, box.y + 9))


def run_profile(app):
    """Driver profile: name, clothes and hair colors, hat shop - but
    from haunt stage 4 the hats are gone and only medicine is for sale.
    Returns "menu" (ESC) or "quit" (window closed)."""
    skin = load_skin()
    st = play_haunt()               # read once per visit
    if st >= 4:                     # the pharmacy shelf
        shop, shop_label = MEDS, "MEDS"
        k_own, k_sel = "meds", "med"
    else:
        shop, shop_label = HATS, "HAT"
        k_own, k_sel = "hats", "hat"
    shop_sel = skin[k_sel]          # item currently browsed (previewed)
    sel = 0                         # 0 NAME, 1 CLOTHES, 2 HAIR, 3 SHOP
    typing = False
    name_buf = skin["name"]
    # a fresh comment per visit - flattery, or a confession
    bubble = random.choice(CONFESSIONS if st >= 1 else COMPLIMENTS)
    while True:
        cash, _, _ = load_profile()
        dt = min(0.05, app.clock.tick(FPS) / 1000)
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return "quit"
            if e.type == pygame.KEYDOWN:
                if typing:                     # typing a new name
                    if e.key == pygame.K_RETURN:
                        if name_buf:
                            skin["name"] = name_buf
                            save_skin(skin)
                        typing = False
                        play(app, "blip")
                    elif e.key == pygame.K_ESCAPE:
                        name_buf = skin["name"]
                        typing = False
                    elif e.key == pygame.K_BACKSPACE:
                        name_buf = name_buf[:-1]
                    elif (e.unicode and e.unicode.isprintable()
                          and len(name_buf) < 12):
                        name_buf += e.unicode.upper()
                    continue
                if e.key == pygame.K_m:
                    music.toggle_mute(app)
                elif e.key == pygame.K_F11:
                    app.toggle_fullscreen()
                elif e.key in (pygame.K_UP, pygame.K_w):
                    sel = (sel - 1) % 4
                    play(app, "blip", 0.6)
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    sel = (sel + 1) % 4
                    play(app, "blip", 0.6)
                elif e.key in (pygame.K_LEFT, pygame.K_a):
                    if sel == 1:
                        skin["clothes"] = (skin["clothes"] - 1) \
                            % len(CLOTHES_COLORS)
                        save_skin(skin)
                        play(app, "blip", 0.6)
                    elif sel == 2:
                        skin["hair"] = (skin["hair"] - 1) \
                            % len(HAIR_COLORS)
                        save_skin(skin)
                        play(app, "blip", 0.6)
                    elif sel == 3:
                        shop_sel = (shop_sel - 1) % len(shop)
                        play(app, "blip", 0.6)
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    if sel == 1:
                        skin["clothes"] = (skin["clothes"] + 1) \
                            % len(CLOTHES_COLORS)
                        save_skin(skin)
                        play(app, "blip", 0.6)
                    elif sel == 2:
                        skin["hair"] = (skin["hair"] + 1) \
                            % len(HAIR_COLORS)
                        save_skin(skin)
                        play(app, "blip", 0.6)
                    elif sel == 3:
                        shop_sel = (shop_sel + 1) % len(shop)
                        play(app, "blip", 0.6)
                elif e.key == pygame.K_RETURN:
                    if sel == 0:
                        typing = True
                        name_buf = skin["name"]
                        play(app, "blip")
                    elif sel == 3:
                        item = shop[shop_sel]
                        if shop_sel in skin[k_own]:
                            skin[k_sel] = shop_sel       # just select it
                            save_skin(skin)
                            play(app, "blip")
                        else:
                            wallet, owned, cur = load_profile()
                            if wallet >= item["price"]:
                                wallet -= item["price"]
                                save_profile(wallet, owned, cur)
                                skin[k_own].append(shop_sel)
                                skin[k_sel] = shop_sel
                                save_skin(skin)
                                play(app, "ding")
                            else:
                                play(app, "warn")
                elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                    return "menu"

        s = app.screen
        draw_background(s, pygame.time.get_ticks() / 1000.0)
        title = app.font_big.render(
            "THE DRIVER" if st >= 2 else "DRIVER PROFILE", True,
            (200, 60, 60) if st >= 2 else (255, 210, 74))
        s.blit(title, title.get_rect(center=(VW / 2, 52)))
        draw_wallet(s, app, cash)

        # the driver (previewing the browsed hat, or medicine at stage 4)
        # - the deeper the haunt, the more the colour drains away
        surf = person_surface(skin["clothes"], skin["hair"],
                              0 if st >= 4 else shop_sel, 8, mood=min(4, st))
        s.blit(surf, (96, 230))
        if st >= 4:                  # the browsed bottle, beside the driver
            icon = med_surface(shop_sel, 6)
            s.blit(icon, (260, 330))
            nm = app.font.render(shop[shop_sel]["name"], True, (170, 170, 170))
            s.blit(nm, (260, 330 + icon.get_height() + 8))
        draw_speech_bubble(s, app, 60, 160, bubble)

        # option rows on the right
        for i, label in enumerate(("NAME", "CLOTHES", "HAIR", shop_label)):
            y = 130 + i * 95
            box = pygame.Rect(470, y, 460, 70)
            if i == sel:
                pygame.draw.rect(s, (44, 52, 70), box, border_radius=8)
                pygame.draw.rect(s, (255, 210, 74), box, 3, border_radius=8)
            else:
                pygame.draw.rect(s, (40, 44, 58), box, border_radius=8)
                pygame.draw.rect(s, (90, 96, 120), box, 2, border_radius=8)
            lb = app.font_big.render(label, True,
                                     (255, 210, 74) if i == sel
                                     else (200, 200, 200))
            s.blit(lb, (box.x + 20, box.y + 20))
            if i == 0:                     # name (blinking cursor while typing)
                shown = name_buf if typing else skin["name"]
                if typing and pygame.time.get_ticks() // 400 % 2 == 0:
                    shown += "_"
                vs = app.font.render(shown, True, (255, 255, 255))
                s.blit(vs, (box.right - vs.get_width() - 20, box.y + 26))
            elif i == 1:                   # clothes: swatch + name
                col = CLOTHES_COLORS[skin["clothes"]]
                pygame.draw.rect(s, col[1],
                                 (box.right - 150, box.y + 25, 20, 20),
                                 border_radius=4)
                pygame.draw.rect(s, (25, 25, 25),
                                 (box.right - 150, box.y + 25, 20, 20), 2,
                                 border_radius=4)
                vs = app.font.render(col[0], True, (220, 220, 220))
                s.blit(vs, (box.right - vs.get_width() - 180, box.y + 26))
            elif i == 2:                   # hair: swatch + name
                col = HAIR_COLORS[skin["hair"]]
                pygame.draw.rect(s, col[1],
                                 (box.right - 150, box.y + 25, 20, 20),
                                 border_radius=4)
                pygame.draw.rect(s, (25, 25, 25),
                                 (box.right - 150, box.y + 25, 20, 20), 2,
                                 border_radius=4)
                vs = app.font.render(col[0], True, (220, 220, 220))
                s.blit(vs, (box.right - vs.get_width() - 180, box.y + 26))
            else:                          # shop item: name + status / price
                item = shop[shop_sel]
                if skin[k_sel] == shop_sel:
                    txt, col = "SELECTED", (74, 222, 128)
                elif shop_sel in skin[k_own]:
                    txt, col = "OWNED - press ENTER", (220, 220, 220)
                elif cash >= item["price"]:
                    txt, col = f"buy ${item['price']}", (255, 210, 74)
                else:
                    txt, col = f"need ${item['price']}", (239, 68, 68)
                vs = app.font.render(txt, True, col)
                s.blit(vs, (box.right - vs.get_width() - 20, box.y + 26))

        hint = "ARROWS browse/adjust - ENTER name or hat - ESC back"
        hs = app.font.render(hint, True, (120, 220, 140))
        s.blit(hs, hs.get_rect(center=(VW / 2, VH - 26)))
        pygame.display.flip()