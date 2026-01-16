import os, sys, math, random, pygame

# ---------------- Config ----------------
BASE_W, BASE_H = 540, 900   # retrato
FPS = 60

# ---------------- Assets resolver (robusto para EXE + assets ao lado OU --add-data) ----------------
def _resolve_assets():
    cands = []
    if getattr(sys, "frozen", False):  # rodando como EXE
        mp = getattr(sys, "_MEIPASS", None)              # assets embutidos (onefile com --add-data)
        exe_dir = os.path.dirname(sys.executable)        # pasta do .exe
        if mp:
            cands.append(os.path.join(mp, "assets"))     # 1) embutido
        cands.append(os.path.join(exe_dir, "assets"))    # 2) assets do lado do .exe
        cands.append(os.path.join(os.path.dirname(exe_dir), "assets"))  # 3) dist\assets (fallback)
    else:  # rodando via python
        cands.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))
    for d in cands:
        if os.path.isdir(d):
            return d
    return cands[0] if cands else "assets"

ASSETS_DIR = _resolve_assets()
IMG_DIR = os.path.join(ASSETS_DIR, "images")
SND_DIR = os.path.join(ASSETS_DIR, "sounds")

# ---------------- Util ----------------
def load_image(name):
    p = os.path.join(IMG_DIR, name)
    if os.path.exists(p):
        return pygame.image.load(p).convert_alpha()
    return None

def load_sound(name):
    p = os.path.join(SND_DIR, name)
    if os.path.exists(p):
        try:
            return pygame.mixer.Sound(p)
        except pygame.error:
            return None
    return None

def scale_surface(img, factor):
    if not img:
        return None
    w, h = img.get_width(), img.get_height()
    return pygame.transform.smoothscale(img, (max(1, int(w*factor)), max(1, int(h*factor))))

def slice_sheet(img, rows, cols):
    w = img.get_width() // cols
    h = img.get_height() // rows
    frames = []
    for r in range(rows):
        for c in range(cols):
            frames.append(img.subsurface((c*w, r*h, w, h)).copy())
    return frames

# ---------------- Sprites ----------------
class Player(pygame.sprite.Sprite):
    def __init__(self, scale=1.0):
        super().__init__()
        base = load_image("player.png")
        if base is None:
            base = pygame.Surface((84, 84), pygame.SRCALPHA)
            pygame.draw.polygon(base, (200, 200, 210), [(42, 6), (8, 78), (76, 78)])
            pygame.draw.line(base, (255, 255, 255), (42, 6), (42, 60), 2)
        self.image_raw = base
        self.image = scale_surface(base, scale)
        self.rect = self.image.get_rect(midbottom=(WIDTH//2, HEIGHT-40))
        self.speed = int(7*scale)
        self.lives = 3
        self.invuln = 0
        self.shield_timer = 0
        self.missiles = 20     # 20 mísseis guiados
        self.missile_cd = 0

    def update(self, keys=None):
        if keys is None:
            keys = pygame.key.get_pressed()
        vx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        vy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        self.rect.x += int(vx * self.speed)
        self.rect.y += int(vy * self.speed)
        self.rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
        if self.invuln > 0: self.invuln -= 1
        if self.shield_timer > 0: self.shield_timer -= 1
        if self.missile_cd > 0: self.missile_cd -= 1

    def draw_afterburner(self, surface):
        # duas turbinas pequenas saindo dos motores
        cx, by = self.rect.centerx, self.rect.bottom
        off = int(12 * GFX_SCALE)
        for dx in (-off, off):
            x = cx + dx
            y = by - int(10 * GFX_SCALE)
            flame = [(x-3, y+8), (x+3, y+8), (x, y+16)]
            pygame.draw.polygon(surface, (255, 180, 40), flame)
        if self.shield_timer > 0:
            t = pygame.time.get_ticks() / 120.0
            radius = max(self.rect.width, self.rect.height)//2 + 3 + int(3*math.sin(t))
            pygame.draw.circle(surface, (120, 200, 255), self.rect.center, radius, 2)

class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, speed=-14*1.0, scale=1.0):
        super().__init__()
        img = load_image("bullet.png")
        if img is None:
            img = pygame.Surface((6, 18), pygame.SRCALPHA)
            pygame.draw.rect(img, (255, 255, 0), (2, 0, 2, 18))
        self.image = scale_surface(img, scale)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = int(speed * scale)

    def update(self):
        self.rect.y += self.speed
        if self.rect.bottom < 0 or self.rect.top > HEIGHT:
            self.kill()

class HomingMissile(pygame.sprite.Sprite):
    def __init__(self, x, y, scale=1.0):
        super().__init__()
        img = load_image("missile.png")
        if img is None:
            img = pygame.Surface((8, 24), pygame.SRCALPHA)
            pygame.draw.rect(img, (220, 220, 220), (2, 0, 4, 24), border_radius=2)
            pygame.draw.polygon(img, (200, 0, 0), [(2, 20), (6, 20), (4, 24)])
        self.image = scale_surface(img, scale)
        self.rect = self.image.get_rect(center=(x, y))
        self.vx, self.vy = 0, -8*scale
        self.turn_rate = 0.10
        self.speed = 8 * scale
        self.target = None

    def update(self):
        if self.target and self.target.alive():
            tx, ty = self.target.rect.centerx, self.target.rect.centery
            dx, dy = tx - self.rect.centerx, ty - self.rect.centery
            dist = math.hypot(dx, dy) + 1e-5
            ndx, ndy = dx/dist, dy/dist
            self.vx = (1-self.turn_rate)*self.vx + self.turn_rate*ndx*self.speed
            self.vy = (1-self.turn_rate)*self.vy + self.turn_rate*ndy*self.speed
        else:
            self.vy = -self.speed
        self.rect.x += int(self.vx)
        self.rect.y += int(self.vy)
        if self.rect.bottom < -40 or self.rect.top > HEIGHT+40:
            self.kill()

class Enemy(pygame.sprite.Sprite):
    def __init__(self, kind="drone", scale=1.0):
        super().__init__()
        name = {"drone": "enemy_drone.png", "ufo": "enemy_ufo.png", "fighter": "enemy_fighter.png"}[kind]
        base = load_image(name)
        if base is None:
            size = (int(44*scale), int(44*scale))
            base = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.circle(base, (200, 100, 100), (size[0]//2, size[1]//2), min(size)//2-3)
        self.image = scale_surface(base, scale)
        self.rect = self.image.get_rect(midtop=(random.randint(24, WIDTH-24), -40))
        self.speedy = random.randint(2, 5)
        self.speedx = random.choice([-2, -1, 0, 1, 2]) if kind != "drone" else 0
        self.hp = {"drone": 2, "ufo": 3, "fighter": 12}.get(kind, 2)
        self.shoot_cd = random.randint(60, 120) if kind in ("drone", "ufo") else 9999

    def update(self):
        self.rect.y += self.speedy
        self.rect.x += self.speedx
        if self.rect.top > HEIGHT + 50 or self.rect.right < -50 or self.rect.left > WIDTH + 50:
            self.kill()
        self.shoot_cd -= 1

class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, scale=1.0):
        super().__init__()
        img = load_image("enemy_bullet.png")
        if img is None:
            img = pygame.Surface((5, 14), pygame.SRCALPHA)
            pygame.draw.rect(img, (255, 80, 120), (2, 0, 2, 14))
        self.image = scale_surface(img, scale)
        self.rect = self.image.get_rect(center=(x, y))
        self.speed = int(6 * scale)

    def update(self):
        self.rect.y += self.speed
        if self.rect.top > HEIGHT:
            self.kill()

class Boss(pygame.sprite.Sprite):
    def __init__(self, scale=1.0):
        super().__init__()
        base = load_image("enemy_fighter.png")  # B-17 como boss
        if base is None:
            base = pygame.Surface((200, 150), pygame.SRCALPHA)
            pygame.draw.rect(base, (90, 110, 80), (0, 0, 200, 150), border_radius=12)
        self.image = scale_surface(base, 3.0*scale)  # grandão
        self.rect = self.image.get_rect(midtop=(WIDTH//2, -int(160*scale)))
        self.max_hp = 150
        self.hp = self.max_hp
        self.t = 0
        self.entered = False
        self.shoot_cd = 45

    def update(self):
        self.t += 1
        if not self.entered:
            self.rect.y += 2
            if self.rect.top >= int(20 * GFX_SCALE):
                self.entered = True
        else:
            self.rect.x = WIDTH//2 + int(140 * math.sin(self.t/60))
        self.shoot_cd -= 1

class Explosion(pygame.sprite.Sprite):
    def __init__(self, center, scale=1.0):
        super().__init__()
        sheet = load_image("explosion_atlas_512x512.png")
        if sheet:
            frames = slice_sheet(sheet, 3, 3)
            frames = [scale_surface(f, 0.28*scale) for f in frames]
            self.frames = frames
        else:
            surf = pygame.Surface((int(64*scale), int(64*scale)), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 200, 0), (surf.get_width()//2, surf.get_height()//2), surf.get_width()//2-4)
            self.frames = [surf]
        self.image = self.frames[0]
        self.rect = self.image.get_rect(center=center)
        self.idx = 0
        self.timer = 0

    def update(self):
        self.timer += 1
        if self.timer % 3 == 0:
            self.idx += 1
            if self.idx >= len(self.frames):
                self.kill()
            else:
                self.image = self.frames[self.idx]
                self.rect = self.image.get_rect(center=self.rect.center)

# ---------------- Game ----------------
class Game:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

        # janela menor que a tela (90% da altura)
        info = pygame.display.Info()
        scale_h = (info.current_h * 0.9) / BASE_H
        self.scale = GFX_SCALE = min(1.0, scale_h)
        globals()['GFX_SCALE'] = self.scale
        globals()['WIDTH'] = int(BASE_W * self.scale)
        globals()['HEIGHT'] = int(BASE_H * self.scale)

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("F-14 vs WWII — Sky Patrol")
        icon = load_image("player.png")
        if icon:
            pygame.display.set_icon(icon)

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", int(20*self.scale))
        self.bigfont = pygame.font.SysFont("consolas", int(30*self.scale), bold=True)
        self.state = "menu"

        # sons
        self.snd_shoot = load_sound("shoot.wav") or load_sound("shoot.ogg")
        self.snd_missile = load_sound("missile.wav") or load_sound("missile.ogg")
        self.snd_lock = load_sound("lock.wav") or load_sound("lock.ogg")
        self.snd_explosion = load_sound("explosion.wav") or load_sound("explosion.ogg")
        self.snd_flak = load_sound("flak.wav") or load_sound("flak.ogg")
        self.snd_flyby = load_sound("flyby.wav") or load_sound("flyby.ogg")

        bgm_path_ogg = os.path.join(SND_DIR, "bgm_war.ogg")
        bgm_path_wav = os.path.join(SND_DIR, "bgm_war.wav")
        self.music_bgm = bgm_path_ogg if os.path.exists(bgm_path_ogg) else bgm_path_wav

        self.engine_loop = load_sound("engine_loop.wav") or load_sound("engine_loop.ogg")
        self.ch_engine = pygame.mixer.Channel(1)
        self.ch_sfx = pygame.mixer.Channel(2)

        self.bg = load_image("background.png")
        self.bg2 = load_image("background_clouds.png")
        self.bg_y = 0
        self.bg2_y = -HEIGHT//2

        self.next_boss_score = 400
        self.best = 0

        # ------------ BGM toca UMA vez ------------
        if self.music_bgm and os.path.exists(self.music_bgm) and not pygame.mixer.music.get_busy():
            try:
                pygame.mixer.music.load(self.music_bgm)
                pygame.mixer.music.set_volume(0.35)
                pygame.mixer.music.play(-1)  # loop infinito; só para no fim do programa
            except pygame.error:
                pass

        self.reset()

    # sair limpando a música
    def hard_quit(self):
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        pygame.quit()
        sys.exit()

    def reset(self):
        self.all = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.enemy_bullets = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()
        self.missiles = pygame.sprite.Group()
        self.effects = pygame.sprite.Group()
        self.boss_group = pygame.sprite.Group()

        self.player = Player(scale=self.scale)
        self.all.add(self.player)
        self.score = 0
        self.combo = 0
        self.combo_timer = 0
        self.fire_cooldown = 0
        self.spawn_timer = 0
        self.diff = 0

        # NÃO recarrega a BGM aqui; ela já está tocando desde o __init__
        if self.engine_loop:
            self.ch_engine.play(self.engine_loop, loops=-1)
            self.ch_engine.set_volume(0.25)
        self.ch_sfx.set_volume(0.8)

    def draw_bg(self):
        if self.bg:
            b1 = pygame.transform.smoothscale(self.bg, (WIDTH, HEIGHT))
            self.bg_y = (self.bg_y + int(2*self.scale)) % HEIGHT
            self.screen.blit(b1, (0, self.bg_y - HEIGHT))
            self.screen.blit(b1, (0, self.bg_y))
        else:
            self.screen.fill((18, 24, 42))
        if self.bg2:
            b2 = pygame.transform.smoothscale(self.bg2, (WIDTH, HEIGHT))
            self.bg2_y = (self.bg2_y + int(1*self.scale)) % HEIGHT
            self.screen.blit(b2, (0, self.bg2_y - HEIGHT))
            self.screen.blit(b2, (0, self.bg2_y))

    def run(self):
        while True:
            if self.state == "menu":
                self.menu_loop()
            elif self.state == "game":
                self.game_loop()
            elif self.state == "pause":
                self.pause_loop()
            elif self.state == "over":
                self.over_loop()

    def menu_loop(self):
        while self.state == "menu":
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.hard_quit()
                if e.type == pygame.KEYDOWN:
                    if e.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.state = "game"
                    if e.key == pygame.K_ESCAPE:
                        self.hard_quit()
            self.draw_bg()
            title = self.bigfont.render("F-14 vs WWII", True, (255, 255, 255))
            tip = self.font.render("ENTER/SPACE: jogar e atirar  |  M: míssil guiado  |  P: pausa", True, (200, 200, 200))
            sig = self.font.render("Desenvolvido por MrSistemas (MATHEUS ANTUNES REIS)", True, (210, 210, 210))
            self.screen.blit(title, title.get_rect(center=(WIDTH//2, HEIGHT//2 - int(60*self.scale))))
            self.screen.blit(tip,   tip.get_rect(center=(WIDTH//2, HEIGHT//2 - int(20*self.scale))))
            self.screen.blit(sig,   sig.get_rect(center=(WIDTH//2, HEIGHT//2 + int(20*self.scale))))
            pygame.display.flip()
            self.clock.tick(FPS)

    def pause_loop(self):
        while self.state == "pause":
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.hard_quit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_p:
                        self.state = "game"
                    if e.key == pygame.K_ESCAPE:
                        self.hard_quit()
            self.draw_bg()
            txt = self.bigfont.render("PAUSADO (P para voltar)", True, (255, 255, 255))
            self.screen.blit(txt, txt.get_rect(center=(WIDTH//2, HEIGHT//2)))
            pygame.display.flip()
            self.clock.tick(FPS)

    def over_loop(self):
        while self.state == "over":
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.hard_quit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_RETURN:
                        self.reset()
                        self.state = "game"
                    if e.key == pygame.K_ESCAPE:
                        self.hard_quit()
            self.draw_bg()
            over = self.bigfont.render("GAME OVER", True, (255, 80, 120))
            sc   = self.font.render(f"Score: {self.score}", True, (230, 230, 230))
            best = self.font.render(f"Melhor: {self.best}", True, (220, 220, 140))
            tip  = self.font.render("ENTER: jogar de novo  |  ESC: sair", True, (200, 200, 200))
            sig  = self.font.render("Desenvolvido por MrSistemas (MATHEUS ANTUNES REIS)", True, (210, 210, 210))
            self.screen.blit(over, over.get_rect(center=(WIDTH//2, HEIGHT//2 - int(60*self.scale))))
            self.screen.blit(sc,   sc.get_rect(center=(WIDTH//2, HEIGHT//2 - int(20*self.scale))))
            self.screen.blit(best, best.get_rect(center=(WIDTH//2, HEIGHT//2 + int(10*self.scale))))
            self.screen.blit(tip,  tip.get_rect(center=(WIDTH//2, HEIGHT//2 + int(40*self.scale))))
            self.screen.blit(sig,  sig.get_rect(center=(WIDTH//2, HEIGHT//2 + int(70*self.scale))))
            pygame.display.flip()
            self.clock.tick(FPS)

    def game_loop(self):
        while self.state == "game":
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.hard_quit()
                if e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_p:
                        self.state = "pause"
                    if e.key == pygame.K_ESCAPE:
                        self.hard_quit()
                    if e.key == pygame.K_m:
                        if self.player.missiles > 0 and self.player.missile_cd == 0:
                            m = HomingMissile(self.player.rect.centerx, self.player.rect.top, scale=self.scale)
                            target = self.find_nearest_target(m.rect.center)
                            if target:
                                m.target = target
                                if self.snd_lock: self.ch_sfx.play(self.snd_lock)
                            self.missiles.add(m); self.all.add(m)
                            self.player.missiles -= 1
                            self.player.missile_cd = int(40*self.scale)
                            if self.snd_missile: self.ch_sfx.play(self.snd_missile)
                            if self.snd_flyby:   self.ch_sfx.play(self.snd_flyby)

            keys = pygame.key.get_pressed()
            self.player.update(keys)

            # tiro infinito
            if self.fire_cooldown > 0: self.fire_cooldown -= 1
            if keys[pygame.K_SPACE] and self.fire_cooldown == 0:
                self.shoot()
                self.fire_cooldown = int(6*self.scale)

            # spawns e boss
            self.diff += 1
            self.spawn_timer += 1
            if self.spawn_timer >= max(int(14*self.scale), int(28*self.scale) - self.diff//150):
                self.spawn_timer = 0
                kind = random.choices(["drone", "ufo"], weights=[6, 4])[0]
                e = Enemy(kind, scale=self.scale)
                self.enemies.add(e); self.all.add(e)

            if self.score >= self.next_boss_score and len(self.boss_group) == 0:
                b = Boss(scale=self.scale)
                self.boss_group.add(b); self.all.add(b)
                self.next_boss_score += 500

            # updates
            self.bullets.update(); self.missiles.update()
            self.enemies.update(); self.enemy_bullets.update()
            self.effects.update(); self.boss_group.update()

            # inimigos atiram
            for e in self.enemies:
                if e.shoot_cd <= 0 and e.rect.top > 0:
                    e.shoot_cd = random.randint(60, 120)
                    b = EnemyBullet(e.rect.centerx, e.rect.bottom, scale=self.scale)
                    self.enemy_bullets.add(b); self.all.add(b)
                    if self.snd_flak and random.random() < 0.3:
                        self.ch_sfx.play(self.snd_flak)

            # boss atira
            for b in self.boss_group:
                if b.entered and b.shoot_cd <= 0:
                    b.shoot_cd = 40
                    for dx in (-60, -30, 0, 30, 60):
                        eb = EnemyBullet(b.rect.centerx + dx, b.rect.bottom, scale=self.scale)
                        self.enemy_bullets.add(eb); self.all.add(eb)

            # colisões
            for enemy in pygame.sprite.groupcollide(self.enemies, self.bullets, False, True):
                enemy.hp -= 1
                if enemy.hp <= 0:
                    self.kill_enemy(enemy)
            for enemy in pygame.sprite.groupcollide(self.enemies, self.missiles, False, True):
                enemy.hp -= 3
                if enemy.hp <= 0:
                    self.kill_enemy(enemy)

            for b in self.boss_group:
                if pygame.sprite.spritecollide(b, self.bullets, True):
                    b.hp -= 1
                if pygame.sprite.spritecollide(b, self.missiles, True):
                    b.hp -= 5
                if b.hp <= 0:
                    self.score += 350
                    for _ in range(6):
                        boom = Explosion((b.rect.centerx + random.randint(-40, 40),
                                          b.rect.centery + random.randint(-20, 20)), scale=self.scale)
                        self.effects.add(boom); self.all.add(boom)
                    if self.snd_explosion: self.ch_sfx.play(self.snd_explosion)
                    b.kill()

            # dano no player
            if self.player.invuln == 0:
                if (pygame.sprite.spritecollide(self.player, self.enemies, True) or
                    pygame.sprite.spritecollide(self.player, self.boss_group, False) or
                    pygame.sprite.spritecollide(self.player, self.enemy_bullets, True)):
                    if self.player.shield_timer > 0:
                        self.player.shield_timer = 0
                    else:
                        self.player.lives -= 1
                        self.player.invuln = int(90*self.scale)
                        self.combo = 0; self.combo_timer = 0
                        if self.player.lives <= 0:
                            if self.score > self.best:
                                self.best = self.score
                            self.state = "over"

            # draw
            self.draw_bg()
            for spr in self.all:
                self.screen.blit(spr.image, spr.rect)
            self.player.draw_afterburner(self.screen)

            hud = self.font.render(f"Score {self.score}  Vidas {self.player.lives}  Mísseis {self.player.missiles}", True, (230, 230, 230))
            self.screen.blit(hud, (10, 10))
            pygame.display.flip()
            self.clock.tick(FPS)

    def find_nearest_target(self, pos):
        candidates = list(self.enemies) + list(self.boss_group)
        if not candidates:
            return None
        px, py = pos
        best = min(candidates, key=lambda s: (s.rect.centerx - px)**2 + (s.rect.centery - py)**2)
        return best

    def kill_enemy(self, enemy):
        self.score += 10
        boom = Explosion(enemy.rect.center, scale=self.scale)
        self.effects.add(boom); self.all.add(boom)
        if self.snd_explosion:
            self.ch_sfx.play(self.snd_explosion)
        enemy.kill()

    def shoot(self):
        cx, cy = self.player.rect.centerx, self.player.rect.top
        b1 = Bullet(cx - int(8*self.scale), cy, scale=self.scale)
        b2 = Bullet(cx + int(8*self.scale), cy, scale=self.scale)
        self.bullets.add(b1, b2); self.all.add(b1, b2)
        if self.snd_shoot:
            self.ch_sfx.play(self.snd_shoot)

if __name__ == "__main__":
    Game().run()
