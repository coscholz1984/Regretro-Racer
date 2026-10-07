"""RETRO RACER DELUXE - scroll.py
Mini-game: vertical 3000 m dash with traffic, pickups, gas stations
and nitro."""
import math
import random
import time

import pygame

from core import (CASH_BILL, FPS, LB_SCROLL, BaseGame, VH, VW,
                  add_cash, load_board, note_finish,
                  note_play, play_haunt, reward_multiplier, save_board)
from sprites import (BOOST_PX, CASH_PAL, CASH_PX, FUEL_PX, SC_CAR_COLORS,
                     WRENCH_PX, body_surface, car_sprite,
                     player_car_surface, selected_car, sprite,
                     wreck_surface)
import music


# ============================================================================
# MODE 2: SCROLL (vertical scrolling dash, fixed 3000 m)
# ============================================================================
SRW = 360                  # scroll: road width in px (4 lanes)
LANE = SRW // 4             # scroll: width of one lane in px
LANE_OFFS = [-LANE * 1.5, -LANE * 0.5,
             LANE * 0.5, LANE * 1.5]   # lane centers, relative to road center
SC_PIX = 4                 # scroll: car sprite scale (chunkier cars)
SEG = 400                   # control-point spacing of the centerline
STATION_EVERY = 1400        # world distance between gas stations
STATION_LEN = 260           # length of a gas station zone
NPC_GAP = 90                # min gap traffic keeps along the road
MAX_BASE = 390              # normal top speed (px/s)
MAX_BOOST = 520             # top speed with nitro
FINISH_D = 30000            # finish line at 3000 m

GRASS = (58, 125, 21)
GRASS_DARK = (47, 102, 18)
ROAD = (68, 68, 74)
ROAD_DARK = (52, 52, 58)
LINE = (255, 255, 255)
BARRIER = (239, 68, 68)
BARRIER_ALT = (245, 245, 245)


# ============================================================================
# SCROLL GAME
# ============================================================================
class ScrollGame(BaseGame):
    def __init__(self, app):
        super().__init__(app)
        self.car_sprites = {c: car_sprite(c, SC_PIX) for c in SC_CAR_COLORS}
        self.wreck_sprites = {c: wreck_surface(c, SC_PIX)
                              for c in SC_CAR_COLORS}
        self.body_surf = body_surface(SC_PIX)
        self.pick_sprites = {
            "fuel": sprite(FUEL_PX, {"7": (56, 189, 248), "8": (255, 255, 255)}),
            "boost": sprite(BOOST_PX, {"8": (255, 210, 74)}),
            "wrench": sprite(WRENCH_PX, {"9": (74, 222, 128)}),
            "cash": sprite(CASH_PX, CASH_PAL),
        }
        self.reset()

    def reset(self):
        self.dist = 0.0            # world distance driven (px)
        self.pxoff = 0.0            # player offset from the road center
        self.px = VW / 2            # player x (screen space)
        self.tilt = 0.0             # visual steering tilt (degrees)
        self.race_time = 0.0
        self.speed = 0.0
        self.fuel = 100.0
        self.dmg = 0.0
        self.boost = 0.0           # seconds of nitro left
        self.npcs = []
        self.pickups = []
        self.decos = []
        self.smoke = []
        self.cash_pops = []     # floating "+$20" indicators
        self.offs = [0.0]          # road centerline offsets per SEG
        self.next_npc_d = 700.0
        self.next_pick_d = 500.0
        self.next_deco_d = 60.0
        self.spooks = []             # wrecks - and worse - along the way
        self.next_spook_d = 900.0
        self.hit_cd = 0.0
        self.scrape_cd = 0.0
        self.warn_t = 0.0
        self.refueling = False
        self.started = False
        self.over = False
        self.reason = ""
        self.board = load_board(LB_SCROLL)
        self.new_lb = None
        self.cash_won = 0
        self.repair_cost = 0
        # the haunt: how far the story has crept in
        self.haunt = play_haunt()
        # the player drives the car selected in the garage
        self.car_spec = selected_car()
        self.player_surf = player_car_surface(self.car_spec, SC_PIX)
        self.reset_fx()
        self.stop_loops()
        music.start_music(self.app, "scroll", haunt=min(self.haunt, 3))

    # ------------------------------------------------------------- road shape
    def ensure_offs(self, idx):
        """Extend the offset random walk until index idx exists."""
        while len(self.offs) <= idx:
            rng = random.Random(1234 + len(self.offs))  # deterministic per index
            prev = self.offs[-1]
            nxt = max(-250.0, min(250.0, prev + rng.uniform(-150, 150)))
            self.offs.append(nxt)

    def center(self, d):
        """Road center x at world distance d (smooth cosine interpolation)."""
        d = max(0.0, d)
        i = int(d // SEG)
        t = (d - i * SEG) / SEG
        self.ensure_offs(i + 1)
        a, b = self.offs[i], self.offs[i + 1]
        return VW / 2 + a + (b - a) * (0.5 - 0.5 * math.cos(math.pi * t))

    # ------------------------------------------------------------------ update
    def update(self, dt, keys):
        if keys[pygame.K_q]:
            self.exited = True
            return
        if not self.started:
            if keys[pygame.K_RETURN]:
                self.started = True
                self.snd("blip")
                self.driver_hud_say(self.race_start_line())
            return
        if self.over:
            if keys[pygame.K_r]:
                self.reset()
            self.update_fx(dt, active=False)     # the fireball burns out
            return
        self.update_fx(dt, active=True)
        self.driver_cheer(dt)
        p_d = self.dist + 90       # player's world distance (car center row)
        cx = self.center(p_d)

        # --- steering: pure screen-space, the road slides beneath the car ---
        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        steer = (right - left)
        if self.haunt >= 2:            # the wheel remembers: mirrored
            steer = -steer
        vx = steer * (170 + self.speed * 0.45) * (1 + self.car_spec["steer"])
        self.px = max(30.0, min(VW - 30.0, self.px + vx * dt))
        self.pxoff = self.px - cx

        # surface effects (never move the car, only slow/hurt it)
        half_w = SRW / 2
        car_half = self.player_surf.get_width() / 2.0
        car_edge = abs(self.pxoff) + car_half
        fully_past = abs(self.pxoff) - car_half > half_w + 10.0
        self.scrape_cd = max(0.0, self.scrape_cd - dt)
        if not fully_past and car_edge > half_w:
            self.speed *= 1 - 4 * dt
            self.dmg = min(100, self.dmg + dt * 16)
            if self.scrape_cd <= 0:
                self.scrape_cd = 0.4
                self.snd("crash", 0.5)
                for _ in range(3):
                    self.smoke.append((self.px + random.uniform(-12, 12),
                                       VH - 90 + random.uniform(-16, 16), 0.5))
        elif fully_past:
            self.speed *= 1 - 1.6 * dt
        target = steer * 14 if self.speed > 30 else 0.0
        self.tilt += (target - self.tilt) * min(1.0, 10 * dt)

        if self.dmg >= 100:
            self.game_over("WRECKED")
            return

        # --- throttle / brake ---
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        # the emptier the tank, the faster the car:
        # full tank tops out at 390, an almost empty one at up to 470
        fuel_boost = (1.0 - self.fuel / 100.0) * 80.0
        top = ((MAX_BOOST if self.boost > 0 else MAX_BASE + fuel_boost)
               + self.car_spec["max"])
        accel = 260 * (1.5 if self.boost > 0 else 1.0)
        if up and self.fuel > 0:
            self.speed += accel * dt
        elif down:
            self.speed -= 320 * dt
        else:
            self.speed *= 1 - 0.7 * dt
        self.speed = max(0.0, min(top, self.speed))

        self.boost = max(0.0, self.boost - dt)

        # --- fuel ---
        if self.fuel > 0:
            self.fuel = max(0.0, self.fuel
                            - dt * (1.0 + self.speed / MAX_BASE * 2.6))
            if self.fuel <= 0:
                self.snd("thud")
        else:
            self.speed *= 1 - 0.9 * dt   # coasting on fumes
            if self.speed < 8:
                self.game_over("OUT OF FUEL")
        if self.fuel < 25 and self.fuel > 0:
            self.warn_t += dt
            if self.warn_t > 1.2:
                self.warn_t = 0.0
                self.snd("warn", 0.6)

        # --- drive ---
        self.race_time += dt
        self.dist += self.speed * dt
        if self.dist >= FINISH_D:
            self.finish_race()
            return
        # stage 3: sometimes the car simply decides to explode
        if (self.haunt >= 3 and self.race_time > 12.0
                and random.random() < dt * 0.022):
            self.explode_at(self.px, VH - 90)
            self.game_over("THE CAR EXPLODED")
            for _ in range(14):
                self.smoke.append((self.px + random.uniform(-16, 16),
                                   VH - 90 + random.uniform(-16, 16),
                                   random.uniform(0.5, 1.0)))
            return

        # --- spawn traffic ahead (denser with distance) ---
        gap = max(150.0, 380.0 - self.dist * 0.004)
        while self.next_npc_d < self.dist + 1600:
            if random.random() < 0.8:
                # spawn without overlaps: try the lanes in random
                # order and skip the car entirely if every lane is
                # already taken at this spot
                d_new = self.next_npc_d + random.uniform(0, 200)
                lanes = list(range(len(LANE_OFFS)))
                random.shuffle(lanes)
                for li in lanes:
                    if any(abs(n["d"] - d_new) < 150
                           and abs(n["xoff"] - LANE_OFFS[li]) < 50
                           for n in self.npcs):
                        continue          # lane busy at this spot
                    # stage 3: some oncoming cars are hunters - red,
                    # fast, and they home in on the player's lane
                    chase = (self.haunt >= 3 and li < len(LANE_OFFS) // 2
                             and random.random() < 0.35)
                    self.npcs.append({
                        "d": d_new,
                        "xoff": LANE_OFFS[li] + random.uniform(-16, 16),
                        # left two lanes: oncoming traffic (drives at
                        # you), right two lanes: slower traffic you
                        # overtake
                        "dir": 1 if li >= len(LANE_OFFS) // 2 else -1,
                        "speed": random.uniform(300, 380) if chase
                                 else random.uniform(110, 240),
                        "color": "red" if chase
                                 else random.choice(["white", "teal",
                                                     "purple"]),
                        "chase": chase,
                    })
                    break
            self.next_npc_d += gap
        self.npcs = [n for n in self.npcs if n["d"] > self.dist - 150]

        # --- spawn pickups (fuel cans are rare: gas stations matter) ---
        while self.next_pick_d < self.dist + 1600:
            if random.random() < 0.7:
                r = random.random()
                kind = ("fuel" if r < 0.22 else
                        "boost" if r < 0.62 else
                        "wrench" if r < 0.86 else "cash")
                self.pickups.append({"d": self.next_pick_d,
                                     "xoff": random.choice(LANE_OFFS)
                                     + random.uniform(-20, 20),
                                     "kind": kind})
            self.next_pick_d += 520
        self.pickups = [p for p in self.pickups if p["d"] > self.dist - 150]

        # --- roadside decorations ---
        while self.next_deco_d < self.dist + 700:
            side = random.choice([-1, 1])
            self.decos.append({"d": self.next_deco_d,
                               "xoff": side * (SRW / 2 + 40 + random.uniform(0, 160)),
                               "kind": random.choice(["tree", "tree", "rock"])})
            self.next_deco_d += random.uniform(50, 130)
        self.decos = [t for t in self.decos if t["d"] > self.dist - 150]

        # --- the haunt: crashed wrecks on the shoulders - and from
        # stage 3, silhouettes lying in the road where they were hit ---
        while self.haunt >= 2 and self.next_spook_d < self.dist + 1600:
            body = self.haunt >= 3 and random.random() < 0.4
            self.spooks.append({
                "d": self.next_spook_d + random.uniform(0, 200),
                "xoff": (random.uniform(20, SRW / 2 - 30) if body else
                         random.choice([-1, 1]) *
                         (SRW / 2 + random.uniform(45, 140))),
                "kind": "body" if body else "wreck",
                "color": random.choice(["white", "teal", "purple"]),
                "ang": random.uniform(-40, 40)})
            self.next_spook_d += random.uniform(700, 1500)
        self.spooks = [k for k in self.spooks if k["d"] > self.dist - 150]

        # --- NPC movement + collision ---
        self.hit_cd = max(0.0, self.hit_cd - dt)
        for n in self.npcs:
            n["d"] += n["dir"] * n["speed"] * dt
            if n.get("chase"):
                # hunters slide across the road toward the player
                step = 90.0 * dt
                n["xoff"] += max(-step, min(step, self.pxoff - n["xoff"]))
        # traffic keeps its distance: no car drives through the car
        # ahead of it in its lane - it falls in behind and matches its
        # speed (queuing up, like real traffic)
        for a in self.npcs:
            for b in self.npcs:
                if a is b or a["dir"] != b["dir"]:
                    continue
                if abs(a["xoff"] - b["xoff"]) > 40:
                    continue          # different lanes
                ahead = (b["d"] - a["d"]) * a["dir"]
                if 0 < ahead < NPC_GAP:
                    a["d"] = b["d"] - NPC_GAP * a["dir"]
                    a["speed"] = min(a["speed"], b["speed"])
        if self.hit_cd <= 0:
            for n in self.npcs[:]:
                nx = self.center(n["d"]) + n["xoff"]
                ny = VH - (n["d"] - self.dist)
                if abs(nx - self.px) <= 36 and abs(ny - (VH - 90)) <= 56:
                    # head-on crash with oncoming traffic hurts a lot
                    head_on = n["dir"] < 0
                    self.dmg = min(100, self.dmg + (45 if head_on else 16))
                    self.speed *= 0.15 if head_on else 0.4
                    self.hit_cd = 1.0 if head_on else 0.8
                    self.snd("crash", 1.0 if head_on else 0.8)
                    # in the innocent version the other car just breaks
                    # down in a puff of smoke; only the haunted version
                    # blows it up (a head-on hit is a small explosion
                    # of its own)
                    if self.haunt >= 1:
                        self.explode_at(nx, ny, big=head_on)
                    for _ in range(10 if head_on else 6):
                        self.smoke.append((nx + random.uniform(-14, 14),
                                           ny + random.uniform(-14, 14),
                                           random.uniform(0.3, 0.7)))
                    if self.haunt < 1:
                        for _ in range(4):
                            self.smoke.append((nx + random.uniform(-18, 18),
                                               ny + random.uniform(-10, 10),
                                               random.uniform(0.6, 1.2)))
                    self.npcs.remove(n)
                    if self.dmg >= 100:
                        self.game_over("WRECKED")

        # --- pickups ---
        for p in self.pickups[:]:
            x = self.center(p["d"]) + p["xoff"]
            y = VH - (p["d"] - self.dist)
            if abs(x - self.px) <= 24 and abs(y - (VH - 90)) <= 30:
                if p["kind"] == "fuel":
                    self.fuel = min(100, self.fuel + 35)
                    self.driver_hud_say("Good fill-up!")
                elif p["kind"] == "boost":
                    self.boost = 5.0
                    self.driver_hud_say("Nitro power!")
                elif p["kind"] == "cash":
                    add_cash(CASH_BILL)
                    self.cash_pops.append((x, y, 1.0))
                    self.driver_hud_say("Money in the bank!")
                else:
                    self.dmg = max(0, self.dmg - 30)
                    self.driver_hud_say("Pit crew magic!")
                self.snd("blip", 0.7)
                self.pickups.remove(p)

        # --- gas station refuel strip (right lane, station zones) ---
        self.refueling = False
        rel = p_d - 600
        if rel >= 0:
            k = int(rel // STATION_EVERY)
            off = rel - k * STATION_EVERY
            if 20 <= off <= STATION_LEN - 20 and self.px > cx + SRW / 2 - LANE:
                self.refueling = True
                self.fuel = min(100, self.fuel + dt * 30)

        self.smoke = [(x, y, l - dt) for (x, y, l) in self.smoke if l - dt > 0]
        self.cash_pops = [(x, y, l - dt) for (x, y, l) in self.cash_pops if l - dt > 0]

        # --- engine sound ---
        if self.sfx.ok and not self.app.muted:
            spd = self.speed
            eng_idx = min(9, int(spd / MAX_BOOST * 9.999)) if self.boost <= 0 else 9
            if eng_idx != self._eng_idx:
                if self.engine_ch:
                    self.engine_ch.stop()
                self._eng_idx = eng_idx
                self.engine_ch = self.sfx.engines[eng_idx].play(loops=-1)
                self.engine_ch.set_volume(0.12)
            if self.engine_ch:
                self.engine_ch.set_volume(0.16 if spd > 5 else 0.07)

    def finish_race(self):
        self.over = True
        self.reason = "FINISH!"
        self.stop_loops()
        self.snd("ding")
        # cash reward for finishing, multiplied by speed (up to 2x)
        mult = reward_multiplier(self.race_time, par=80.0)
        gross = int(round(150 * mult))
        # repair bill: damage percentage is deducted from the winnings
        self.repair_cost = int(round(gross * self.dmg / 100.0))
        self.cash_won = gross - self.repair_cost
        add_cash(self.cash_won)
        note_finish()
        note_play(self.race_time)
        entry = {"time": round(self.race_time, 1),
                 "when": time.strftime("%Y-%m-%d %H:%M")}
        self.board = load_board(LB_SCROLL)
        self.board.append(entry)
        self.board.sort(key=lambda e: e["time"])
        self.board = self.board[:10]
        save_board(LB_SCROLL, self.board)
        self.new_lb = entry

    def game_over(self, reason):
        self.over = True
        self.reason = reason
        self.stop_loops()
        self.snd("thud")

    def lb_lines(self, rows=5):
        lines = [("LEADERBOARD (best times)", self.font, (255, 210, 74))]
        if not self.board:
            lines.append(("no finishes yet - set the first one!", self.font,
                          (180, 180, 180)))
            return lines
        for i, e in enumerate(self.board[:rows]):
            txt = f"{i + 1}.  {e['time']:.1f}s    {e['when']}"
            color = (255, 50, 50) if e is self.new_lb else (255, 255, 255)
            lines.append((txt, self.font, color))
        return lines

    # -------------------------------------------------------------------- draw
    def draw_world(self):
        s = self.screen
        if self.haunt >= 3:          # the grass remembers what rained on it
            s.fill((98, 34, 26))
        elif self.haunt == 2:        # sickly, quietly dying
            s.fill((74, 108, 32))
        else:
            s.fill(GRASS)

        for sy in range(0, VH + 4, 4):
            d = self.dist + (VH - sy)
            cx = self.center(d)
            left, right = cx - SRW / 2, cx + SRW / 2
            pygame.draw.rect(s, ROAD, (left, sy, SRW, 4))
            pygame.draw.rect(s, ROAD_DARK, (left + 8, sy, SRW - 16, 4))
            bcol = BARRIER if int(d / 40) % 2 == 0 else BARRIER_ALT
            pygame.draw.rect(s, bcol, (left - 8, sy, 8, 4))
            pygame.draw.rect(s, bcol, (right, sy, 8, 4))
            if int(d) % 52 < 24:
                for lo in (-LANE, 0, LANE):
                    pygame.draw.rect(s, LINE, (cx + lo - 2, sy, 4, 4))
            if FINISH_D <= d <= FINISH_D + 36:
                for cxi in range(int(left), int(right), 24):
                    c = (20, 20, 20) if (cxi // 24) % 2 == 0 else (245, 245, 245)
                    pygame.draw.rect(s, c, (cxi, sy, 24, 4))
            rel = d - 600
            if rel >= 0 and int(rel) % STATION_EVERY <= STATION_LEN and int(d) % 24 < 12:
                pygame.draw.rect(s, (255, 210, 74),
                                 (left + SRW / 2 + 2, sy, 4, 4))
                pygame.draw.rect(s, (255, 210, 74), (right - 14, sy, 4, 4))

        for t in self.decos:
            x = self.center(t["d"]) + t["xoff"]
            y = VH - (t["d"] - self.dist)
            if -40 < y < VH + 40:
                if t["kind"] == "tree":
                    pygame.draw.rect(s, (90, 62, 30), (x - 3, y + 6, 6, 12))
                    pygame.draw.circle(s, (34, 90, 24), (x, y - 4), 14)
                    pygame.draw.circle(s, (26, 70, 18), (x - 4, y - 8), 8)
                else:
                    pygame.draw.circle(s, (120, 120, 120), (x, y), 9)
                    pygame.draw.circle(s, (90, 90, 90), (x - 3, y - 2), 5)

        # the haunt: crashed wrecks on the shoulders, bodies in the road
        for k in self.spooks:
            x = self.center(k["d"]) + k["xoff"]
            y = VH - (k["d"] - self.dist)
            if -40 < y < VH + 40:
                if k["kind"] == "wreck":
                    spr = pygame.transform.rotate(
                        self.wreck_sprites[k["color"]], k["ang"])
                    s.blit(spr, spr.get_rect(center=(x, y)))
                    if random.random() < 0.3:       # embers still glow
                        pygame.draw.circle(
                            s, (255, 120 + random.randint(0, 80), 30),
                            (int(x + random.uniform(-12, 12)),
                             int(y + random.uniform(-8, 8))), 3)
                else:
                    pygame.draw.ellipse(s, (46, 10, 12),
                                        (int(x - 26), int(y - 4), 52, 12))
                    s.blit(self.body_surf, (int(x - 24), int(y - 16)))

        kmin = max(0, int((self.dist - STATION_LEN - 600) // STATION_EVERY))
        kmax = int((self.dist + VH - 600) // STATION_EVERY) + 1
        for k in range(kmin, kmax):
            d0 = k * STATION_EVERY + 600
            yb = VH - (d0 - self.dist)
            if yb < -40 or yb - STATION_LEN > VH + 40:
                continue
            bx = self.center(d0) + SRW / 2 + 90
            pygame.draw.rect(s, (110, 110, 116),
                             (bx - 90, yb - 200, 90, 200))
            pygame.draw.rect(s, (170, 120, 70), (bx, yb - 200, 96, 200))
            pygame.draw.rect(s, (212, 58, 47), (bx, yb - 200, 96, 22))
            pygame.draw.rect(s, (120, 82, 48), (bx, yb - 200, 96, 200), 3)
            s.blit(self.font.render("GAS", True, (255, 255, 255)), (bx + 26, yb - 196))
            for py_ in (yb - 60, yb - 150):
                pygame.draw.rect(s, (56, 189, 248), (bx - 62, py_, 10, 22))
                pygame.draw.rect(s, (30, 30, 30), (bx - 62, py_, 10, 22), 2)

        for p in self.pickups:
            x = self.center(p["d"]) + p["xoff"]
            y = VH - (p["d"] - self.dist)
            if -40 < y < VH + 40:
                s.blit(self.pick_sprites[p["kind"]], (x - 18, y - 18))

        # floating "+$20" indicators for collected bills
        for (x, y, l) in self.cash_pops:
            pop = self.font.render(f"+${CASH_BILL}", True, (74, 222, 128))
            rise = (1.0 - l) * 36
            s.blit(pop, (x - pop.get_width() / 2, y - 46 - rise))

        for n in self.npcs:
            x = self.center(n["d"]) + n["xoff"]
            y = VH - (n["d"] - self.dist)
            if -60 < y < VH + 60:
                slope = (self.center(n["d"] + 24) - self.center(n["d"] - 24)) / 48
                lean = max(-14.0, min(14.0, math.degrees(math.atan(slope)) * 0.6))
                # oncoming cars face the player (rotated 180 degrees)
                rot = 180 - lean if n["dir"] < 0 else -lean
                spr = pygame.transform.rotate(self.car_sprites[n["color"]], rot)
                s.blit(spr, spr.get_rect(center=(x, y)))

        for (x, y, l) in self.smoke:
            r = int((1 - l) * 10) + 3
            col = (90, 90, 90) if l > 0.25 else (160, 160, 160)
            pygame.draw.circle(s, col, (int(x), int(y - (0.5 - l) * 30)), r)

        if self.boost > 0:
            for fx in (-13, 0, 13):
                l = random.uniform(10, 22)
                pygame.draw.rect(s, (255, 210, 74),
                                 (self.px + fx - 4, VH - 90 + 34, 8, int(l)))
        spr = pygame.transform.rotate(self.player_surf, -self.tilt)
        s.blit(spr, spr.get_rect(center=(self.px, VH - 90)))

    def draw_hud(self):
        s = self.screen
        self.draw_driver_hud((12, 12))

        def bar(y, label, frac, color, x, w):
            s.blit(self.font.render(label, True, (255, 255, 255)), (x + 12, y))
            pygame.draw.rect(s, (68, 68, 68), (x + 12, y + 22, w, 10))
            pygame.draw.rect(s, color, (x + 12, y + 22, w * frac, 10))

        # top-right: distance + race time (wide enough for the BEST label)
        top = pygame.Rect(VW - 320, 10, 300, 66)
        self.panel_rect(top)
        best = f"{self.board[0]['time']:.1f}s" if self.board else "-"
        s.blit(self.font.render(
            f"DIST {int(self.dist / 10):4d} / {FINISH_D // 10} m", True,
            (255, 255, 255)), (top.x + 12, 16))
        s.blit(self.font.render(f"TIME {self.race_time:5.1f}s  BEST {best}", True,
                                (255, 210, 74)), (top.x + 12, 38))

        stats = pygame.Rect(VW - 270, VH - 196, 250, 186)
        self.panel_rect(stats)
        bar(stats.y + 16, f"SPD {int(self.speed):3d}",
            self.speed / (MAX_BOOST + self.car_spec["max"]),
            (74, 222, 128), stats.x, 226)
        bar(stats.y + 54, f"DMG {int(self.dmg):3d}%", self.dmg / 100,
            (239, 68, 68) if self.dmg > 60 else (250, 204, 21) if self.dmg > 30 else (74, 222, 128),
            stats.x, 226)
        bar(stats.y + 92, f"FUEL {int(self.fuel):3d}%", self.fuel / 100,
            (56, 189, 248) if self.fuel >= 25 else (239, 68, 68), stats.x, 226)
        bar(stats.y + 130, f"NITRO {self.boost:3.1f}", self.boost / 5,
            (255, 210, 74) if self.boost > 0 else (120, 120, 120), stats.x, 226)
        if self.refueling and pygame.time.get_ticks() // 300 % 2 == 0:
            s.blit(self.font.render("REFUELING", True, (74, 222, 128)),
                   (stats.x + 60, stats.y + 134))

        # vertical track progress bar (right edge, fills bottom-up)
        bx, by0, by1 = VW - 30, 96, VH - 210
        pygame.draw.rect(s, (20, 20, 30, 110), (bx - 8, by0 - 24, 36, by1 - by0 + 48),
                         border_radius=6)
        pygame.draw.rect(s, (68, 68, 68), (bx, by0, 14, by1 - by0))
        frac = min(1.0, self.dist / FINISH_D)
        fy = by1 - (by1 - by0) * frac
        pygame.draw.rect(s, (74, 222, 128), (bx, fy, 14, by1 - fy))
        for i in range(2):
            c = (20, 20, 20) if i % 2 == 0 else (245, 245, 245)
            pygame.draw.rect(s, c, (bx, by0 - 12 + i * 6, 14, 6))
        pygame.draw.rect(s, (212, 58, 47), (bx - 7, fy - 5, 28, 9))
        s.blit(self.font_small.render(f"{FINISH_D // 10}", True, (255, 255, 255)),
               (bx - 4, by0 - 36))
        s.blit(self.font_small.render("0", True, (255, 255, 255)), (bx + 2, by1 + 8))

    def draw(self):
        self.draw_world()
        self.draw_hud()
        if not self.started:
            lines = [
                ("SORROW SCROLL" if self.haunt >= 2
                 else "RETRO RACER SCROLL",
                 self.font_big, (255, 210, 74)),
                ("ARROWS / WASD - tonight the wheel is MIRRORED"
                 if self.haunt >= 2 else
                 "ARROWS / WASD to drive - dodge the traffic",
                 self.font,
                 (239, 68, 68) if self.haunt >= 2 else (255, 255, 255)),
                ("RED cars hunt in the LEFT lanes. they want you."
                 if self.haunt >= 3 else
                 "beware of ONCOMING traffic in the two LEFT lanes",
                 self.font, (239, 68, 68)),
                ("the pickups watch you back tonight" if self.haunt >= 1
                 else "collect FUEL cans, NITRO bolts and repair kits",
                 self.font, (180, 180, 190) if self.haunt >= 1
                 else (255, 255, 255)),
                ("refuel in the GAS stations on the right lane",
                 self.font, (255, 255, 255)),
                ("ENTER start - R repeat after race - ESC menu",
                 self.font, (74, 222, 128)),
                ("M toggles sound - Q quits",
                 self.font, (74, 222, 128)),
            ]
            self.overlay(*lines, *self.lb_lines())
        elif self.over:
            head = (self.reason, self.font_big,
                    (74, 222, 128) if self.reason == "FINISH!" else (239, 68, 68))
            lines = [head]
            if self.reason == "FINISH!":
                lines.append((f"TIME {self.race_time:.1f}s", self.font, (255, 255, 255)))
                lines.append((f"CASH +${self.cash_won}", self.font, (74, 222, 128)))
                if self.repair_cost:
                    lines.append((f"REPAIRS -${self.repair_cost} "
                                  f"({int(self.dmg)}% damage)",
                                  self.font, (239, 68, 68)))
                if self.haunt >= 1:
                    lines.append(("the cheering sounds a little like sirens",
                                  self.font, (180, 180, 190)))
            else:
                lines.append((f"managed {int(self.dist / 10)} m", self.font,
                              (255, 255, 255)))
            if self.reason == "THE CAR EXPLODED":
                lines.append(("no warning. no reason. it has happened before.",
                              self.font, (239, 68, 68)))
            lines.append(("press R to repeat - ESC for the menu", self.font, (74, 222, 128)))
            self.overlay(*lines, *self.lb_lines())
        self.draw_boom(self.screen)
        self.draw_scare(self.screen)

    # ---------------------------------- run ----------------------------------
    def run(self):
        while not self.exited:
            dt = min(0.05, self.app.clock.tick(FPS) / 1000)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.exited = True
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_m:
                    self.stop_loops()
                    music.toggle_mute(self.app)
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.app.toggle_fullscreen()
            keys = pygame.key.get_pressed()
            if keys[pygame.K_ESCAPE]:
                self.stop_loops()
                return          # back to the menu
            self.update(dt, keys)
            self.draw()
            pygame.display.flip()
        self.stop_loops()