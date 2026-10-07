"""RETRO RACER DELUXE - circuit.py
Mini-game: 3-lap race on a closed circuit against three AI cars,
with a fuel pit and random cash bundles on the track.
Canonical version: if your local copy was modified, replace it
with this one."""
import math
import random
import time

import pygame

from core import (CASH_BILL, FPS, LB_CIRCUIT, BaseGame, VH, VW,
                  add_cash, load_board, note_finish,
                  note_play, play_haunt, reward_multiplier, save_board)
from sprites import (CAR_COLORS, CAR_PX, CASH_PAL, CASH_PX, body_surface,
                     make_car_surface, player_car_surface, selected_car,
                     sprite, wreck_surface)
import music


# ============================================================================
# MODE 1: CIRCUIT (closed quasi-circular track, 3 laps)
# ============================================================================
LAPS = 3
ROAD_W = 130               # circuit: full road width in px

COLORS = {
    "grass": (58, 125, 44),
    "grass_dark": (49, 109, 37),
    "road": (90, 90, 90),
    "road_dark": (76, 76, 76),
    "line": (216, 216, 216),
    "barrier": (232, 232, 232),
    "barrier_alt": (224, 90, 26),
    "tree": (30, 90, 20),
    "tree_dark": (22, 64, 14),
    "trunk": (107, 74, 42),
    "station": (200, 200, 200),
    "station_roof": (212, 58, 47),
}

CONTROL = [
    (420, 1150), (700, 1150), (980, 1150),    # start/finish straight
    (1190, 1010), (1230, 800), (1190, 550),   # right sweeper (long curve)
    (1050, 300), (850, 190),                  # smooth right corner
    (600, 150), (350, 160),                    # top straight
    (170, 280), (90, 520), (95, 800),          # left side going down
    (95, 900), (129, 1025), (220, 1117),       # closing quarter-circle arc
    (345, 1150),                               # arc exit onto the straight
]


def _check_loop():
    """Sanity check: simple closed loop, turning radius above road width."""
    pts = [(p[0], p[1]) for p in TRACK]
    n = len(pts)
    min_radius = float("inf")
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        ab = (b[0] - a[0], b[1] - a[1])
        cb = (c[0] - b[0], c[1] - b[1])
        ca = (a[0] - c[0], a[1] - c[1])
        cross = ab[0] * cb[1] - ab[1] * cb[0]
        if abs(cross) > 1e-9:
            r = (math.hypot(*ab) * math.hypot(*cb) * math.hypot(*ca)) / (2 * abs(cross))
            min_radius = min(min_radius, r)

    def seg_inter(p1, p2, p3, p4):
        d1 = (p2[0] - p1[0], p2[1] - p1[1])
        d2 = (p4[0] - p3[0], p4[1] - p3[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:
            return False
        t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
        u = ((p3[0] - p1[0]) * d1[1] - (p3[1] - p1[1]) * d1[0]) / den
        return 0 < t < 1 and 0 < u < 1

    STRIDE = 4
    segs = [i for i in range(0, n, STRIDE)]
    simple = True
    for ii, i in enumerate(segs):
        for j in segs[ii + 1:]:
            if (j - i) % n <= STRIDE or (i - j) % n <= STRIDE:
                continue
            if seg_inter(pts[i], pts[(i + STRIDE) % n], pts[j], pts[(j + STRIDE) % n]):
                simple = False
    print(f"[track] min turning radius: {min_radius:.0f}px (road width {ROAD_W}px), "
          f"non-self-intersecting: {simple}")
    assert min_radius > ROAD_W * 0.8, "track corner too tight for the road width"
    assert simple, "track centerline self-intersects"


def catmull(p0, p1, p2, p3, s):
    """Centripetal Catmull-Rom spline (square-root parameterization)."""
    def d(a, b):
        return max(1e-6, math.hypot(b[0] - a[0], b[1] - a[1]) ** 0.5)
    t0, t1, t2, t3 = 0.0, d(p0, p1), 0.0, 0.0
    t2 = t1 + d(p1, p2)
    t3 = t2 + d(p2, p3)
    t = t1 + (t2 - t1) * s
    A1 = [((t1 - t) / (t1 - t0)) * p0[k] + ((t - t0) / (t1 - t0)) * p1[k] for k in range(2)]
    A2 = [((t2 - t) / (t2 - t1)) * p1[k] + ((t - t1) / (t2 - t1)) * p2[k] for k in range(2)]
    A3 = [((t3 - t) / (t3 - t2)) * p2[k] + ((t - t2) / (t3 - t2)) * p3[k] for k in range(2)]
    B1 = [((t2 - t) / (t2 - t0)) * A1[k] + ((t - t0) / (t2 - t0)) * A2[k] for k in range(2)]
    B2 = [((t3 - t) / (t3 - t1)) * A2[k] + ((t - t1) / (t3 - t1)) * A3[k] for k in range(2)]
    return tuple(((t2 - t) / (t2 - t1)) * B1[k] + ((t - t1) / (t2 - t1)) * B2[k] for k in range(2))


def build_track():
    pts, n, steps = [], len(CONTROL), 40
    for i in range(n):
        p0, p1 = CONTROL[i - 1], CONTROL[i]
        p2, p3 = CONTROL[(i + 1) % n], CONTROL[(i + 2) % n]
        for s in range(steps):
            pts.append(catmull(p0, p1, p2, p3, s / steps))
    trk = []
    for i, (x, y) in enumerate(pts):
        a, b = pts[i - 1], pts[(i + 1) % len(pts)]
        trk.append((x, y, math.atan2(b[1] - a[1], b[0] - a[0])))
    return trk


TRACK = build_track()
N = len(TRACK)
_check_loop()

WORLD = pygame.Rect(-160, -160, 1480, 1600)

STATION = pygame.Rect(650, 1310, 130, 100)
APRON = pygame.Rect(640, 1225, 150, 95)
REFUEL_ZONE = pygame.Rect(630, 1150, 180, 65)  # right half of the road width


def track_info(x, y):
    best, best_d = 0, float("inf")
    for i in range(0, N, 2):
        dx, dy = TRACK[i][0] - x, TRACK[i][1] - y
        d = dx * dx + dy * dy
        if d < best_d:
            best_d, best = d, i
    return best, math.sqrt(best_d)


def build_decos():
    rng = random.Random(1337)
    decos = []
    while len(decos) < 70:
        x = rng.uniform(-40, 1100)
        y = rng.uniform(-70, 1180)
        if track_info(x, y)[1] > ROAD_W / 2 + 55:
            decos.append((x, y, "tree" if rng.random() > 0.35 else "bush",
                          rng.randint(14, 26)))
    return decos


DECOS = build_decos()


def edge_points(half):
    left, right = [], []
    for x, y, ang in TRACK:
        nx, ny = math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2)
        left.append((x + nx * half, y + ny * half))
        right.append((x - nx * half, y - ny * half))
    return left, right


def arclength_table(pts):
    table = [0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        table.append(table[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return table


def point_at_dist(pts, table, d):
    total = table[-1]
    d = d % total
    i = 0
    while table[i + 1] < d:
        i += 1
    a, b = pts[i], pts[(i + 1) % len(pts)]
    f = (d - table[i]) / (table[i + 1] - table[i])
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def render_world(haunt=0):
    """Pre-render the entire static circuit world once off-screen.
    The haunt rots it from the ground up: the grass sickens at stage 2,
    turns the colour of dried blood at stage 3, and burnt-out wrecks
    (and from stage 3, bodies) appear on the infield."""
    bg = pygame.Surface((WORLD.w, WORLD.h))
    ox, oy = -WORLD.x, -WORLD.y

    def to_surf(pts):
        return [(x + ox, y + oy) for x, y in pts]

    if haunt >= 3:            # the grass turned the colour of that night
        grass, grass_dark = (122, 44, 32), (98, 34, 26)
    elif haunt == 2:          # sickly, quietly dying
        grass, grass_dark = (86, 104, 34), (70, 86, 28)
    else:
        grass, grass_dark = COLORS["grass"], COLORS["grass_dark"]
    bg.fill(grass)
    TILE = 64
    for tx in range(WORLD.left // TILE, (WORLD.right + TILE) // TILE):
        for ty in range(WORLD.top // TILE, (WORLD.bottom + TILE) // TILE):
            if (tx + ty) % 2 == 0:
                bg.fill(grass_dark,
                        (tx * TILE + ox, ty * TILE + oy, TILE, TILE))

    L, R = edge_points(ROAD_W // 2)
    poly = to_surf(L + R[::-1])
    for x, y, ang in TRACK:
        pygame.draw.circle(bg, COLORS["road"], (int(x + ox), int(y + oy)), ROAD_W // 2)
    pygame.draw.polygon(bg, COLORS["road"], poly)
    Li, Ri = edge_points(ROAD_W // 2 - 10)
    poly_i = to_surf(Li + Ri[::-1])
    for x, y, ang in TRACK:
        pygame.draw.circle(bg, COLORS["road_dark"], (int(x + ox), int(y + oy)), ROAD_W // 2 - 10)
    pygame.draw.polygon(bg, COLORS["road_dark"], poly_i)

    # center dashes: constant arc-length period
    center = [(p[0], p[1]) for p in TRACK]
    c_tab = arclength_table(center)
    c_total = c_tab[-1]
    d = 24.0
    while d < c_total - 24:
        p1 = point_at_dist(center, c_tab, d)
        p2 = point_at_dist(center, c_tab, d + 22)
        pygame.draw.line(bg, COLORS["line"],
                         (p1[0] + ox, p1[1] + oy), (p2[0] + ox, p2[1] + oy), 4)
        d += 46

    # barriers: red/white stripes, constant arc-length period
    STRIPE = 30.0
    for edge in (L, R):
        e_tab = arclength_table(edge)
        e_total = e_tab[-1]
        d = 0.0
        while d < e_total:
            color = COLORS["barrier_alt"] if int(d / STRIPE) % 2 else COLORS["barrier"]
            p1 = point_at_dist(edge, e_tab, d)
            p2 = point_at_dist(edge, e_tab, min(d + STRIPE, e_total))
            pygame.draw.line(bg, color, (p1[0] + ox, p1[1] + oy),
                             (p2[0] + ox, p2[1] + oy), 6)
            d += STRIPE

    # start/finish checkers
    t0 = TRACK[0]
    nx, ny = math.cos(t0[2] + math.pi / 2), math.sin(t0[2] + math.pi / 2)
    for i in range(-ROAD_W // 2, ROAD_W // 2, 12):
        for j in range(2):
            c = (255, 255, 255) if (i // 12 + j) % 2 == 0 else (30, 30, 30)
            bg.fill(c, (t0[0] + nx * i - math.cos(t0[2]) * j * 12 + ox,
                        t0[1] + ny * i - math.sin(t0[2]) * j * 12 + oy, 12, 12))

    # gas station pit area
    ap = APRON.move(ox, oy)
    pygame.draw.rect(bg, (120, 120, 118), ap)
    pygame.draw.rect(bg, (95, 95, 93), ap, 3)
    r = STATION.move(ox, oy)
    pygame.draw.rect(bg, (122, 122, 122), r.inflate(8, 8))
    pygame.draw.rect(bg, COLORS["station"], r)
    pygame.draw.rect(bg, COLORS["station_roof"], (r.x, r.y, r.w, 26))
    for px_ in (ap.x + 30, ap.x + ap.w - 40):
        pygame.draw.rect(bg, (51, 51, 51), (px_, ap.y + 18, 14, 30))
        pygame.draw.rect(bg, (242, 193, 78), (px_ + 3, ap.y + 24, 8, 18))
    font = pygame.font.SysFont("monospace", 18, bold=True)
    sign = font.render("GAS", True, (255, 255, 255))
    bg.blit(sign, sign.get_rect(centerx=r.centerx, top=r.y + 4))
    zx = REFUEL_ZONE.move(ox, oy)
    for i in range(0, zx.w, 20):
        pygame.draw.rect(bg, (255, 210, 74), (zx.x + i, zx.y, 10, 4))
        pygame.draw.rect(bg, (255, 210, 74), (zx.x + i, zx.bottom - 4, 10, 4))

    for x, y, kind, size in DECOS:
        sx, sy = x + ox, y + oy
        if kind == "tree":
            pygame.draw.rect(bg, COLORS["trunk"], (sx - 3, sy + size // 2, 6, 10))
            pygame.draw.rect(bg, COLORS["tree_dark"], (sx - size // 2, sy - size // 2, size, size))
            pygame.draw.rect(bg, COLORS["tree"],
                             (sx - size // 2 + 4, sy - size // 2 + 4, size - 8, size - 10))
        else:
            pygame.draw.rect(bg, COLORS["tree_dark"], (sx - 7, sy - 4, 14, 9))

    # the haunt: burnt-out wrecks scattered on the grass (stage 2+),
    # and from stage 3 the people who were never pulled out in time
    if haunt >= 2:
        rng = random.Random(17)
        body_s = body_surface(3)
        wreck_s = {c: wreck_surface(c, 3)
                   for c in ("white", "teal", "purple")}
        for i in range(6 if haunt >= 3 else 4):
            while True:             # keep the wrecks off the asphalt
                x = rng.uniform(WORLD.left + 80, WORLD.right - 80)
                y = rng.uniform(WORLD.top + 80, WORLD.bottom - 80)
                _, tdist = track_info(x, y)
                if tdist > ROAD_W / 2 + 70:
                    break
            ang = rng.uniform(0, 360)
            spr = pygame.transform.rotate(
                wreck_s[rng.choice(["white", "teal", "purple"])], ang)
            bg.blit(spr, spr.get_rect(center=(x + ox, y + oy)))
            if haunt >= 3 and i % 2 == 0:      # a body beside the wreck
                bx = x + rng.uniform(70, 150)
                by = y + rng.uniform(70, 150)
                _, tdist = track_info(bx, by)
                if tdist > ROAD_W / 2 + 60:
                    pygame.draw.ellipse(bg, (46, 10, 12),
                                        (int(bx - 24 + ox),
                                         int(by - 5 + oy), 48, 11))
                    bg.blit(body_s, (bx - 18 + ox, by - 12 + oy))
    return bg


# ============================================================================
# CIRCUIT GAME
# ============================================================================
class Car:
    def __init__(self, color, x, y, ang, is_player=False, offset=0):
        self.color = color
        self.surf = make_car_surface(color)
        self.shadow_base = None
        self.hit_cooldown = 0.0
        self.x, self.y, self.ang = x, y, ang
        self.speed = 0.0
        self.is_player = is_player
        self.offset = offset        # AI lateral offset from centerline
        self.wp = 0                # AI waypoint index
        self.lap = 1
        self.prev_idx = 0
        self.passed_half = False   # mid-track checkpoint for lap counting

    @property
    def progress(self):
        return (self.lap - 1) * N + self.prev_idx


WORLD_BGS = {}     # cached pre-rendered circuit worlds, one per haunt


def world_bg(haunt):
    """The pre-rendered circuit world for the given haunt level (the
    grass rots and the wrecks appear as the story darkens)."""
    key = min(max(int(haunt), 0), 3)
    if key not in WORLD_BGS:
        WORLD_BGS[key] = render_world(key)
    return WORLD_BGS[key]


class CircuitGame(BaseGame):
    def __init__(self, app):
        super().__init__(app)
        self.world = pygame.Surface((VW, VH))
        self.bg = world_bg(min(self.haunt, 3))
        self.cash_sprite = sprite(CASH_PX, CASH_PAL)
        self.reset()

    def reset(self):
        start = TRACK[0]
        nx, ny = math.cos(start[2] + math.pi / 2), math.sin(start[2] + math.pi / 2)

        def place(back, lat):
            return (start[0] - math.cos(start[2]) * back + nx * lat,
                    start[1] - math.sin(start[2]) * back + ny * lat)

        self.player = Car("red", *place(80, -25), start[2], is_player=True)
        self.ais = []
        pace_by_color = {"white": 1.00, "teal": 1.31, "purple": 1.60}
        for i, c in enumerate(["white", "teal", "purple"]):
            x, y = place(80 - (i + 1) * 60, (i % 2 == 0 and 1 or -1) * 25)
            ai = Car(c, x, y, start[2], offset=(i - 1) * 35)
            ai.pace = pace_by_color[c]
            self.ais.append(ai)
        # the player drives the car selected in the garage
        self.car_spec = selected_car()
        self.player.surf = player_car_surface(self.car_spec)
        # tiny 11x16 car sprites for the ranking panel: the AIs in
        # their own colors, the player in its garage body color
        def _mini(body):
            return sprite(CAR_PX, {"1": body, "2": (58, 58, 90),
                                    "4": (255, 250, 180), "5": (28, 28, 32),
                                    "6": (255, 90, 80)}, 1)
        self.order_minis = {"player": _mini(self.car_spec["body"])}
        for c in ("white", "teal", "purple"):
            self.order_minis[c] = _mini(CAR_COLORS[c][0])
        self.cam_x, self.cam_y = self.player.x, self.player.y
        self.fuel, self.dmg = 100.0, 0.0
        self.refueling = False
        self.refuel_snd_timer = 0.0
        self.reset_fx()
        self.stop_loops()
        music.start_music(self.app, "circuit",
                          haunt=min(play_haunt(), 3))
        self.race_time = 0.0
        self.started = False
        self.finished = False
        self.exploded = False
        self.finish_pos = 0
        self.smoke = []
        self.cash_pops = []      # floating "+$20" indicators
        self.board = load_board(LB_CIRCUIT)
        self.new_lb = None
        self.cash_won = 0
        self.repair_cost = 0
        # the haunt: how far the story has crept in, plus the way the
        # wheel pulls on its own at stage 3 (SPACE steadies it)
        self.haunt = play_haunt()
        self.pull = 0.0
        self.pull_t = 0.0
        # random cash bundles scattered on the track this race
        rng = random.Random()
        self.cash_items = []
        used = set()
        while len(self.cash_items) < 3:
            i = rng.randrange(N // 6, N - N // 6)   # keep clear of the line
            if i in used:
                continue
            used.add(i)
            self.cash_items.append({"idx": i, "lat": rng.uniform(-40, 40),
                                    "got": False})

    # ------------------------------ update ----------------------------------
    def update(self, dt, keys):
        if keys[pygame.K_q]:
            self.exited = True
            return
        if not self.started:
            if keys[pygame.K_RETURN]:
                self.started = True
                self.snd("go")
                self.driver_hud_say(self.race_start_line())
            return
        if self.finished:
            if keys[pygame.K_r]:
                self.stop_loops()
                self.reset()
            self.update_fx(dt, active=False)     # the fireball burns out
            return
        self.update_fx(dt, active=True)

        self.driver_cheer(dt)
        self.race_time += dt
        # stage 3: sometimes the car simply decides to explode
        if (self.haunt >= 3 and self.race_time > 12.0
                and random.random() < dt * 0.022):
            self.explode()
            return
        p = self.player
        idx, dist = track_info(p.x, p.y)
        on_road = dist < ROAD_W / 2 - 6

        # the emptier the tank, the faster the car (less weight to haul):
        # full tank tops out at 340 (+ car bonus), an almost empty one more
        fuel_boost = (1.0 - self.fuel / 100.0) * 70.0
        max_spd = (340 + self.car_spec["max"] + fuel_boost) if on_road else 130
        accel = 210 if on_road else 110
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]

        if up and self.fuel > 0:
            p.speed += accel * dt
            self.fuel = max(0, self.fuel - dt * 1.6)
        elif down:
            p.speed -= 230 * dt
        else:
            p.speed *= 1 - 1.2 * dt
        p.speed = max(-120, min(max_spd, p.speed))
        if self.dmg >= 100:
            p.speed = min(p.speed, 80)

        steer = (right - left)
        if self.haunt >= 2:            # the wheel remembers: mirrored
            steer = -steer
        if abs(p.speed) > 15:
            p.ang += (steer * 2.6 * (1 + self.car_spec["steer"]) * dt
                      * (1 if p.speed > 0 else -1) * min(1, abs(p.speed) / 200))

        # stage 3: the wheel pulls on its own - hold SPACE to steady it
        if self.haunt >= 3:
            self.pull_t -= dt
            if self.pull_t <= 0:
                self.pull = random.choice((-0.5, 0.0, 0.5))
                self.pull_t = random.uniform(2.5, 5.0)
            if self.pull and not keys[pygame.K_SPACE]:
                p.ang += (self.pull * dt
                          * min(1.0, abs(p.speed) / 200))

        if not on_road and abs(p.speed) > 80:
            self.dmg = min(100, self.dmg + dt * 9)
            if random.random() < dt * 30:
                self.smoke.append((p.x + random.uniform(-8, 8),
                                   p.y + random.uniform(-8, 8), random.uniform(0, 0.6)))

        p.x += math.cos(p.ang) * p.speed * dt
        p.y += math.sin(p.ang) * p.speed * dt

        # engine sound: pitch rises with speed
        if self.sfx.ok and not self.app.muted:
            spd = abs(p.speed)
            eng_idx = min(9, int(spd / 340 * 9.999))
            if eng_idx != self._eng_idx:
                if self.engine_ch:
                    self.engine_ch.stop()
                self._eng_idx = eng_idx
                self.engine_ch = self.sfx.engines[eng_idx].play(loops=-1)
                self.engine_ch.set_volume(0.12)
            if self.engine_ch:
                self.engine_ch.set_volume(0.15 if spd > 5 else 0.08)
            off = (not on_road) and spd > 40
            if off and not self.offroad_ch:
                self.offroad_ch = self.sfx.offroad.play(loops=-1)
                self.offroad_ch.set_volume(0.3)
            elif not off and self.offroad_ch:
                self.offroad_ch.stop()
                self.offroad_ch = None

        # refuel at the pit area
        self.refueling = False
        if REFUEL_ZONE.collidepoint(p.x, p.y):
            self.refueling = True
            if self.fuel < 100:
                self.fuel = min(100, self.fuel + dt * 30)
                self.refuel_snd_timer += dt
                if self.refuel_snd_timer > 0.12:
                    self.refuel_snd_timer = 0.0
                    self.snd("blip", 0.5)

        # cash bundles on the track
        for it in self.cash_items:
            if it["got"]:
                continue
            x, y, ang = TRACK[it["idx"]]
            nx_, ny_ = math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2)
            bx_ = x + nx_ * it["lat"]
            by_ = y + ny_ * it["lat"]
            if math.hypot(p.x - bx_, p.y - by_) < 24:
                it["got"] = True
                add_cash(CASH_BILL)
                self.snd("blip", 0.7)
                self.smoke.append((bx_, by_, 0.4))
                self.cash_pops.append((bx_, by_, 1.0))

        # lap counting (mid-track checkpoint must be passed first)
        if N // 4 < idx < 3 * N // 4:
            p.passed_half = True
        if p.prev_idx > N - 6 and idx < 6 and p.passed_half:
            p.lap += 1
            p.passed_half = False
            if p.lap > LAPS:
                self.stop_loops()
                self.snd("ding")
                self.finish()
            else:
                self.snd("ding")
        elif p.prev_idx < 6 and idx > N - 6:
            p.lap = max(1, p.lap - 1)
            p.passed_half = True
        p.prev_idx = idx

        # AI: look-ahead steering, curvature slowdown, avoidance
        for a in self.ais:
            a_idx, _ = track_info(a.x, a.y)
            look = 12 + int(a.speed * dt * 2)
            t = TRACK[(a_idx + look) % N]
            av_x, av_y = 0.0, 0.0
            for o in [self.player] + self.ais:
                if o is a:
                    continue
                rx, ry = o.x - a.x, o.y - a.y
                d = math.hypot(rx, ry)
                if d < 90 and d > 0.01:
                    fx, fy = math.cos(a.ang), math.sin(a.ang)
                    if rx * fx + ry * fy > 0.5 * d:
                        side = -1 if (rx * fy - ry * fx) > 0 else 1
                        av_x += (ry / d) * side * (90 - d) * 0.8
                        av_y += (-rx / d) * side * (90 - d) * 0.8
            tx = t[0] + math.cos(t[2] + math.pi / 2) * a.offset + av_x
            ty = t[1] + math.sin(t[2] + math.pi / 2) * a.offset + av_y
            want = math.atan2(ty - a.y, tx - a.x)
            diff = math.remainder(want - a.ang, 2 * math.pi)
            a.ang += max(-3 * dt, min(3 * dt, diff))
            t2 = TRACK[(a_idx + 2 * look) % N]
            curve = abs(math.remainder(t2[2] - t[2], 2 * math.pi))
            corner_max = 300 if curve < 0.35 else 190 if curve < 0.8 else 130
            ai_max = (corner_max + (a.offset % 7) * 8) * getattr(a, "pace", 1.0)
            if a.speed < ai_max:
                a.speed = min(ai_max, a.speed + 150 * dt)
            else:
                a.speed = max(ai_max, a.speed - 260 * dt)
            a.x += math.cos(a.ang) * a.speed * dt
            a.y += math.sin(a.ang) * a.speed * dt
            if N // 4 < a_idx < 3 * N // 4:
                a.passed_half = True
            if a.prev_idx > N - 6 and a_idx < 6 and a.passed_half:
                a.lap += 1
                a.passed_half = False
            a.prev_idx = a_idx
            a.wp = a_idx

        # car-vs-car collisions
        cars = [self.player] + self.ais
        CAR_R = 16
        for i in range(len(cars)):
            for j in range(i + 1, len(cars)):
                c1, c2 = cars[i], cars[j]
                dx, dy = c2.x - c1.x, c2.y - c1.y
                dist = math.hypot(dx, dy)
                if dist < CAR_R * 2 and dist > 0.001:
                    push = (CAR_R * 2 - dist) / 2
                    nx_, ny_ = dx / dist, dy / dist
                    c1.x -= nx_ * push
                    c1.y -= ny_ * push
                    c2.x += nx_ * push
                    c2.y += ny_ * push
                    if c1.hit_cooldown <= 0 and c2.hit_cooldown <= 0:
                        c1.speed *= 0.9
                        c2.speed *= 0.9
                        c1.hit_cooldown = c2.hit_cooldown = 0.5
                        self.snd("crash", 0.7)
                        if c1.is_player or c2.is_player:
                            self.dmg = min(100, self.dmg + 2)
                            self.smoke.append((self.player.x, self.player.y, 0.5))
                        c1.ang += random.uniform(-0.03, 0.03)
                        c2.ang += random.uniform(-0.03, 0.03)

        for a in self.ais:
            if a.lap > LAPS and not hasattr(a, "fin_pos"):
                a.fin_pos = self.finish_pos + 1
                self.finish_pos = getattr(self, "_ai_fin", 0) + 1
                self._ai_fin = self.finish_pos

        for c in [self.player] + self.ais:
            c.hit_cooldown = max(0, c.hit_cooldown - dt)

        # camera
        k = min(1, 5 * dt)
        self.cam_x = int(self.cam_x + (p.x - self.cam_x) * k)
        self.cam_y = int(self.cam_y + (p.y - self.cam_y) * k)
        self.cam_x = max(WORLD.left + VW / 2, min(WORLD.right - VW / 2, self.cam_x))
        self.cam_y = max(WORLD.top + VH / 2, min(WORLD.bottom - VH / 2, self.cam_y))

        self.smoke = [(x, y, l - dt) for (x, y, l) in self.smoke if l - dt > 0]
        self.cash_pops = [(x, y, l - dt) for (x, y, l) in self.cash_pops if l - dt > 0]

    def finish(self):
        self.finished = True
        self.finish_pos = 1 + sum(1 for a in self.ais if a.progress > self.player.progress)
        # cash reward: base + position bonus, multiplied by speed (up to 2x)
        mult = reward_multiplier(self.race_time, par=90.0)
        pos_bonus = {1: 100, 2: 50, 3: 25}.get(self.finish_pos, 0)
        gross = int(round((100 + pos_bonus) * mult))
        # repair bill: damage percentage is deducted from the winnings
        self.repair_cost = int(round(gross * self.dmg / 100.0))
        self.cash_won = gross - self.repair_cost
        add_cash(self.cash_won)
        note_finish()
        note_play(self.race_time)
        entry = {"time": round(self.race_time, 1),
                 "when": time.strftime("%Y-%m-%d %H:%M")}
        self.board = load_board(LB_CIRCUIT)
        self.board.append(entry)
        self.board.sort(key=lambda e: e["time"])
        self.board = self.board[:10]
        save_board(LB_CIRCUIT, self.board)
        self.new_lb = entry

    def explode(self):
        """Haunt stage 3: the car explodes for no reason. The race is
        over, there is no prize, and the driver knows why."""
        self.finished = True
        self.exploded = True
        self.stop_loops()
        self.snd("crash", 1.0)
        # the fireball swallows the car (the player is always centred)
        self.explode_at(VW / 2, VH / 2)
        for _ in range(16):
            self.smoke.append((self.player.x + random.uniform(-16, 16),
                               self.player.y + random.uniform(-16, 16),
                               random.uniform(0.5, 1.0)))

    def lb_lines(self, rows=5):
        lines = [("LEADERBOARD", self.font, (255, 210, 74))]
        if not self.board:
            lines.append(("no times yet - set the first one!", self.font,
                          (180, 180, 180)))
            return lines
        for i, e in enumerate(self.board[:rows]):
            txt = f"{i + 1}.  {e['time']:.1f}s    {e['when']}"
            color = (255, 50, 50) if e is self.new_lb else (255, 255, 255)
            lines.append((txt, self.font, color))
        return lines

    @property
    def position(self):
        prog = self.player.progress
        return 1 + sum(1 for a in self.ais if a.progress > prog)

    # ------------------------------- draw ------------------------------------
    def draw_world(self):
        w = self.world
        w.fill(COLORS["grass"])
        ox, oy = int(VW / 2 - self.cam_x), int(VH / 2 - self.cam_y)
        sx = int(self.cam_x - VW / 2) - WORLD.x
        sy = int(self.cam_y - VH / 2) - WORLD.y
        w.blit(self.bg, (0, 0), (sx, sy, VW, VH))

        for x, y, l in self.smoke:
            c = 120 + int(80 * l)
            s = pygame.Surface((6, 6), pygame.SRCALPHA)
            s.fill((c, c, c, 120))
            w.blit(s, (x + ox - 3, y + oy - 3))

        # cash bundles on the track
        for it in self.cash_items:
            if it["got"]:
                continue
            x, y, ang = TRACK[it["idx"]]
            nx_, ny_ = math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2)
            bx_ = x + nx_ * it["lat"] + ox
            by_ = y + ny_ * it["lat"] + oy
            bob = math.sin(pygame.time.get_ticks() / 300.0 + it["idx"]) * 4
            w.blit(self.cash_sprite, (bx_ - 18, by_ - 18 + bob))

        # floating "+$20" indicators for collected bills
        for (x, y, l) in self.cash_pops:
            pop = self.font.render(f"+${CASH_BILL}", True, (74, 222, 128))
            rise = (1.0 - l) * 36
            w.blit(pop, (x + ox - pop.get_width() / 2,
                         y + oy - 46 - rise))

        for a in self.ais:
            self.blit_car(a, ox, oy)
        self.blit_car(self.player, ox, oy)

    def blit_car(self, car, ox, oy):
        deg = -90 - math.degrees(car.ang)
        rot = pygame.transform.rotate(car.surf, deg)
        if car.shadow_base is None:
            base = pygame.Surface(car.surf.get_size(), pygame.SRCALPHA)
            pygame.draw.ellipse(base, (0, 0, 0, 60), base.get_rect().inflate(-8, -8))
            car.shadow_base = base
        sh = pygame.transform.rotate(car.shadow_base, deg)
        self.world.blit(sh, sh.get_rect(center=(car.x + ox + 3, car.y + oy + 4)))
        self.world.blit(rot, rot.get_rect(center=(car.x + ox, car.y + oy)))

    def draw_hud(self):
        s = self.screen

        def bar(y, label, frac, color, x, w):
            s.blit(self.font.render(label, True, (255, 255, 255)), (x + 12, y))
            pygame.draw.rect(s, (68, 68, 68), (x + 12, y + 22, w, 10))
            pygame.draw.rect(s, color, (x + 12, y + 22, w * frac, 10))

        stats = pygame.Rect(10, VH - 160, 200, 150)
        self.panel_rect(stats)
        top_now = 340 + self.car_spec["max"] + (1.0 - self.fuel / 100.0) * 70.0
        spd = int(min(top_now, abs(self.player.speed)))
        bar(stats.y + 16, f"SPD {spd:3d}", spd / top_now,
            (74, 222, 128), stats.x, 176)
        bar(stats.y + 54, f"DMG {int(self.dmg):3d}%", self.dmg / 100,
            (239, 68, 68) if self.dmg > 60 else (250, 204, 21) if self.dmg > 30 else (74, 222, 128),
            stats.x, 176)
        bar(stats.y + 92, f"FUEL {int(self.fuel):3d}%", self.fuel / 100,
            (56, 189, 248) if self.fuel >= 20 else (239, 68, 68), stats.x, 176)
        if self.refueling and not self.finished:
            if pygame.time.get_ticks() // 300 % 2 == 0:
                s.blit(self.font.render("REFUELING", True, (74, 222, 128)),
                       (stats.x + 44, stats.y + 96))

        panel = pygame.Rect(VW - 210, 10, 200, 120)
        self.panel_rect(panel)
        s.blit(self.font.render("RACE ORDER", True, (255, 210, 74)),
               (panel.x + 12, panel.y + 6))
        order = sorted([self.player] + self.ais,
                       key=lambda c: c.progress, reverse=True)
        rank_col = ((255, 210, 74),     # gold, silver, bronze...
                   (205, 205, 215),
                   (205, 127, 50),
                   (150, 150, 150))
        for i, c in enumerate(order):
            y = panel.y + 28 + i * 20
            # the player's row gets a soft highlight box so the eye
            # finds it instantly, even mid-corner
            if c is self.player:
                pygame.draw.rect(s, (62, 40, 40),
                                 (panel.x + 6, y - 2, panel.w - 12, 20),
                                 border_radius=4)
                pygame.draw.rect(s, (255, 50, 50),
                                 (panel.x + 6, y - 2, panel.w - 12, 20), 1,
                                 border_radius=4)
            s.blit(self.font.render(f"{i + 1}", True, rank_col[i]),
                   (panel.x + 14, y))
            mini = self.order_minis["player" if c is self.player
                                   else c.color]
            s.blit(mini, (panel.x + 32, y + 1))
            name = "YOU" if c is self.player else c.color.upper()
            s.blit(self.font.render(name, True,
                                    (255, 50, 50) if c is self.player
                                    else (235, 235, 235)),
                   (panel.x + 50, y))

        topleft = pygame.Rect(10, 10, 220, 46)
        self.panel_rect(topleft)
        s.blit(self.font.render(f"LAP {min(self.player.lap, LAPS)}/{LAPS}", True, (255, 255, 255)), (18, 14))
        s.blit(self.font.render(f"POS {self.finish_pos if self.finished else self.position}/4", True, (255, 255, 255)), (120, 14))
        s.blit(self.font_small.render(f"{self.race_time:.1f}s", True, (251, 191, 36)), (18, 32))

        # the driver cheers from below the lap panel (corner, clear of the pack)
        self.draw_driver_hud((12, 66))

        # haunt warnings, top centre, clear of the lap panel
        if self.haunt >= 3 and not self.finished:
            warn = self.font.render("the wheel pulls - hold SPACE to steady it",
                                    True, (239, 68, 68))
            s.blit(warn, warn.get_rect(midtop=(VW / 2, 8)))

        mm_w, mm_h = 150, 170
        mm = pygame.Rect(VW - mm_w - 14, VH - mm_h - 14, mm_w, mm_h)
        self.panel_rect(mm.inflate(8, 8))
        pygame.draw.rect(s, (102, 102, 102), mm.inflate(8, 8), 2, border_radius=6)
        mx = lambda x: mm.x + (x - WORLD.x) / WORLD.w * mm.w
        my = lambda y: mm.y + (y - WORLD.y) / WORLD.h * mm.h
        mpts = [(mx(t[0]), my(t[1])) for t in TRACK]
        pygame.draw.lines(s, (154, 154, 154), True, mpts, 5)
        for a in self.ais:
            pygame.draw.rect(s, CAR_COLORS[a.color][0], (mx(a.x) - 3, my(a.y) - 3, 6, 6))
        pygame.draw.rect(s, (255, 0, 0), (mx(self.player.x) - 4, my(self.player.y) - 4, 8, 8))

        if not self.started:
            lines = [
                ("GUILT CIRCUIT" if self.haunt >= 2
                 else "RETRO RACER - CIRCUIT",
                 self.font_big, (255, 210, 74)),
                ("ARROWS / WASD to drive - 3 laps, refuel in the GAS pit",
                 self.font, (255, 255, 255)),
            ]
            if self.haunt == 1:
                lines.append(("the track remembers you",
                              self.font, (180, 180, 190)))
            elif self.haunt >= 2:
                lines.append(("tonight the wheel is MIRRORED - left is right",
                              self.font, (239, 68, 68)))
            if self.haunt >= 3:
                lines.append(("the wheel pulls on its own - hold SPACE to steady",
                              self.font, (239, 68, 68)))
            lines.append(("ENTER start - R repeat after race - ESC menu",
                          self.font, (74, 222, 128)))
            lines.append(("M toggles sound - Q quits",
                          self.font, (74, 222, 128)))
            self.overlay(*lines, *self.lb_lines())
        elif self.finished:
            if self.exploded:
                self.overlay(
                    ("THE CAR EXPLODED", self.font_big, (239, 68, 68)),
                    ("no warning. no reason. it has happened before.",
                     self.font, (239, 68, 68)),
                    ("press R to repeat - ESC for the menu",
                     self.font, (74, 222, 128)),
                    *self.lb_lines(),
                )
                return
            win = self.finish_pos == 1
            lines = [
                ("YOU WIN!" if win else f"FINISHED P{self.finish_pos}",
                 self.font_big,
                 (255, 210, 74) if win else (255, 255, 255)),
                (f"TIME {self.race_time:.1f}s", self.font, (255, 255, 255)),
                (f"CASH +${self.cash_won}", self.font, (74, 222, 128)),
            ]
            if self.repair_cost:
                lines.append((f"REPAIRS -${self.repair_cost} "
                              f"({int(self.dmg)}% damage)",
                              self.font, (239, 68, 68)))
            if self.haunt >= 2:
                lines.append(("the trophy feels heavier than it should",
                              self.font, (180, 180, 190)))
            elif self.haunt == 1:
                lines.append(("the cheering sounds a little like static",
                              self.font, (180, 180, 190)))
            lines.append(("press R to repeat - ESC for the menu",
                          self.font, (74, 222, 128)))
            self.overlay(*lines, *self.lb_lines())

        # the shared haunt fx, over everything: explosion fireballs
        # and the sudden jump frames that flip back to normal
        self.draw_boom(s)
        self.draw_scare(s)

    # -------------------------------- run ------------------------------------
    def run(self):
        while not self.exited:
            dt = min(0.05, self.app.clock.tick(FPS) / 1000)
            keys = pygame.key.get_pressed()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.exited = True
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                    self.stop_loops()
                    music.toggle_mute(self.app)
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.app.toggle_fullscreen()
            if keys[pygame.K_ESCAPE]:
                self.stop_loops()
                return          # back to the menu
            self.update(dt, keys)
            self.draw_world()
            self.screen.blit(self.world, (0, 0))
            self.draw_hud()
            pygame.display.flip()
        self.stop_loops()