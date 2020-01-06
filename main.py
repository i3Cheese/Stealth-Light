import os
import sys
from math import ceil, sqrt
from typing import Tuple, Set, Any, List

import pygame as pg

# инициализация pygame
FPS = 60
MINIMUM_LIGHT = 255
pg.init()
size = WIDTH, HEIGHT = 600, 600
screen = pg.display.set_mode(size)
clock = pg.time.Clock()
running = True


# IMAGE TOOLS


def load_image(name, colorkey=None):
    fullname = os.path.join('data', name)
    image = pg.image.load(fullname)
    if colorkey is not None:
        image = image.convert()
        if colorkey == -1:
            colorkey = image.get_at((0, 0))
        if colorkey == -2:
            colorkey = (0, 0, 0)
        image.set_colorkey(colorkey)
    else:
        image = image.convert_alpha()
    return image


def cut_sheet(sheet, columns, rows):
    rect = pg.Rect(0, 0, sheet.get_width() // columns, sheet.get_height() // rows)
    frames = []
    for j in range(rows):
        for i in range(columns):
            frame_location = (rect.w * i, rect.h * j)
            # self.rect.size - это кортеж (w, h)
            frames.append(sheet.subsurface(pg.Rect(frame_location, rect.size)))
    return rect, frames


def find_center(s: pg.sprite.Sprite):
    return s.rect.center


# WINDOW TOOLS


def terminate():
    pg.quit()
    sys.exit()


def start_screen():
    intro_text = ["ЗАСТАВКА", "",
                  "Правила игры",
                  "Если в правилах несколько строк,",
                  "приходится выводить их построчно"]

    fon = pg.transform.scale(load_image('fon.png'), (WIDTH, HEIGHT))
    screen.blit(fon, (0, 0))
    font = pg.font.Font(None, 30)
    text_coord = 50
    for line in intro_text:
        string_rendered = font.render(line, 1, pg.Color('black'))
        intro_rect = string_rendered.get_rect()
        text_coord += 10
        intro_rect.top = text_coord
        intro_rect.x = 10
        text_coord += intro_rect.height
        screen.blit(string_rendered, intro_rect)

    while True:
        for event in pg.event.get():
            if event.type == pg.QUIT:
                terminate()
            elif event.type == pg.KEYDOWN or event.type == pg.MOUSEBUTTONDOWN:
                return  # начинаем игру
        pg.display.flip()
        clock.tick(FPS)


# CLASSES


class LightedSprite(pg.sprite.Sprite):
    monochrome = True

    def __init__(self, *groups):
        super().__init__(*groups)
        self.real_image = None
        self._image = None
        self.black_image = None
        self._light = MINIMUM_LIGHT

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value: pg.Surface):
        self.real_image = value
        self.put_light()

    @property
    def light(self):
        return self._light

    @light.setter
    def light(self, value):
        self._light = value
        self.put_light()

    def put_light(self):
        self._image = self.real_image.copy()
        dark_image = self._image.copy()
        r = dark_image.get_rect()
        dark = 255 - max(0, min(255, self.light))
        if self.monochrome:
            dark_image.fill((0, 0, 0, dark))
        else:
            # сохраняем отношения прозрачности. В частности прозрачное остаётся прозрачным
            for i in range(r.h):
                for j in range(r.w):
                    dark_image.set_at((j, i), (0, 0, 0, dark_image.get_at((j, i)).a * dark // 255))
        self._image.blit(dark_image, (0, 0))

    @property
    def tracking_points(self):
        return [self.rect.topleft,
                self.rect.topright,
                self.rect.bottomleft,
                self.rect.bottomright]


class AnimationSprite:
    def __init__(self, update_image_speed, cur_frame=0):
        self.cur_frame = 0
        self.update_image_speed = 10
        self.image = self.frames[self.cur_frame]

    def update(self):
        self.cur_frame = (self.cur_frame + 1) % (len(self.frames) * self.update_image_speed)
        self.image = self.frames[self.cur_frame // self.update_image_speed]


class Tile(LightedSprite):
    tile_images = {'wall': load_image('wall.png'), 'empty': load_image('empty.png')}
    monochrome = True

    def __init__(self, image_type, is_collide, pos_x, pos_y, level):
        if is_collide:
            super().__init__(level.tiles_group, level.all_sprites, level.collided_sprites)
        else:
            super().__init__(level.tiles_group, level.all_sprites)
        self.is_collide = is_collide
        self.level = level
        self.image = Tile.tile_images[image_type]
        self.rect = pg.Rect(level.tile_width * pos_x, level.tile_height * pos_y,
                            level.tile_width, level.tile_height, )


class Player(LightedSprite, AnimationSprite):
    default_rect, frames = cut_sheet(load_image('player16x20.png'), 4, 1)
    monochrome = False
    update_light_speed = 30

    def __init__(self, pos_x, pos_y, level):
        super().__init__(level.all_sprites, level.player_group)
        self.level = level
        self.rect = Player.default_rect.copy().move(level.tile_width * pos_x,
                                                    level.tile_height * pos_y)

        AnimationSprite.__init__(self, update_image_speed=10, cur_frame=0)

        self.real_pos = list(self.rect.topleft)
        self.speed = 1

        self.inventory = {"torch": 3}

        self.level.relight_it(self)

    def update(self, *args):
        if args:
            if isinstance(args[0], pg.event.EventType):
                event = args[0]
                if event.type == pg.KEYUP and event.key == pg.K_e:
                    use_that = pg.sprite.spritecollideany(self, level.useable_objects_group)
                    if use_that is None:
                        self.place_torch()
                    else:
                        use_that.use(self)

        else:
            dx = 0
            dy = 0
            if pg.key.get_pressed()[pg.K_w]:
                dy -= self.speed
            if pg.key.get_pressed()[pg.K_s]:
                dy += self.speed
            if pg.key.get_pressed()[pg.K_a]:
                dx -= self.speed
            if pg.key.get_pressed()[pg.K_d]:
                dx += self.speed

            if dx and dy:  # Выравниваем скорость
                dx = dx / (2 ** .5)
                dy = dy / (2 ** .5)

            # изменяем координаты
            if dx or dy:
                if dx:
                    self.real_pos[0] += dx
                    self.rect.x = ceil(self.real_pos[0])
                    ox = int(dx // abs(dx))
                    while pg.sprite.spritecollideany(self, self.level.collided_sprites):
                        self.real_pos[0] -= ox
                        self.rect.x -= ox  # выталкивает персонажа из стен
                if dy:
                    self.real_pos[1] += dy
                    self.rect.y = ceil(self.real_pos[1])
                    oy = int(dy // abs(dy))
                    while pg.sprite.spritecollideany(self, self.level.collided_sprites):
                        self.real_pos[1] -= oy
                        self.rect.y -= oy  # выталкивает персонажа из стен

                self.level.relight_it(self)

            # изменяем кадр
            AnimationSprite.update(self)

    def add_torch(self):
        self.inventory["torch"] += 1

    def place_torch(self):
        if self.inventory["torch"]:
            Torch(find_center(self), self.level)
            self.inventory["torch"] -= 1


class Torch(LightedSprite, AnimationSprite):
    default_rect, frames = cut_sheet(load_image("torch_sheet.png"), 4, 1)
    monochrome = False

    def __init__(self, pos_of_center: Tuple[int, int], level):
        super().__init__(level.all_sprites, level.objects_group, level.useable_objects_group)
        self.level = level

        AnimationSprite.__init__(self, update_image_speed=10, cur_frame=0)

        self.rect = self.default_rect.copy().move(pos_of_center[0] - self.default_rect.w // 2,
                                                  pos_of_center[1] - self.default_rect.h // 2)

        self.level.relight_it(self)
        self.light_power = 255
        self.level.add_light(self.rect.center, self.light_power)

    def use(self, player):
        self.level.remove_light(self.rect.center, self.light_power)
        player.add_torch()
        self.kill()

    def update(self, *args):
        # изменяем кадр
        AnimationSprite.update(self)


class Level(pg.Surface):
    width: int
    height: int
    rows: int
    cols: int
    player: Player
    tiles: List[List[Tile]]
    light_sources: Set[Tuple[Tuple[int, int], int]]

    tile_width = tile_height = 64

    def __init__(self, level_num):
        # группы спрайтов
        self.all_sprites = pg.sprite.Group()
        self.collided_sprites = pg.sprite.Group()
        self.tiles_group = pg.sprite.Group()
        self.player_group = pg.sprite.Group()
        self.enemies_group = pg.sprite.Group()
        self.objects_group = pg.sprite.Group()
        self.useable_objects_group = pg.sprite.Group()
        self.light_sources = set()

        self.player, self.cols, self.rows = None, None, None
        self.tiles = []
        self.generate_level(self.load_level(level_num))

        self.width, self.height = Level.tile_width * self.cols, Level.tile_height * self.rows
        super().__init__((self.width, self.height))

    @staticmethod
    def load_level(level_num: int):
        filename = os.path.join('levels', f'l{level_num}.txt')
        # читаем уровень, убирая символы перевода строки
        with open(filename, 'r') as mapFile:
            level_map = [line.strip() for line in mapFile]

        # и подсчитываем максимальную длину
        max_width = max(map(len, level_map))

        # дополняем каждую строку пустыми клетками ('.')
        return list(map(lambda x: x.ljust(max_width, '.'), level_map))

    def generate_level(self, level):
        self.tiles.clear()
        self.cols = 0
        self.rows = len(level)
        player_pos = (0, 0)
        for y in range(len(level)):
            self.tiles.append([])
            self.cols = max(self.cols, len(level[y]))
            for x in range(len(level[y])):
                tile = None
                if level[y][x] == '.':
                    tile = Tile('empty', False, x, y, self)
                elif level[y][x] == '#':
                    tile = Tile('wall', True, x, y, self)
                elif level[y][x] == '@':
                    tile = Tile('empty', False, x, y, self)
                    player_pos = x, y
                self.tiles[-1].append(tile)
        self.player = Player(*player_pos, self)

    def update(self, *args):
        self.all_sprites.update(*args)

    def draw_on(self, screen: pg.Surface, rect: pg.Rect):
        """Рисует все свои спрайты на себе, затем блитает на screen часть себя.
        Фокусируется на игроке, но не выходя за границы. (У краёв игрок будет не в центре)"""
        self.fill(pg.Color("black"))

        # Рисуем спрайты в определёной последовательности
        self.tiles_group.draw(self)
        self.objects_group.draw(self)
        self.enemies_group.draw(self)
        self.player_group.draw(self)

        # вычисляем координаты прямоугольника, который будем рисовать
        target = self.player.rect  # фокус на игроке
        x = max(0, min(self.width - rect.width, target.x + target.width // 2 - rect.width // 2))
        y = max(0, min(self.height - rect.height, target.y + target.height // 2 - rect.height // 2))

        screen.blit(self, rect, rect.copy().move(x, y))

    def count_light_between(self, pos, light_power, target: LightedSprite):
        ray_step = 32
        light_step = 5

        # просто константы для более бытрого счёта
        rs_ls = ray_step * light_step
        rs_ls2 = rs_ls ** 2
        sp_c = find_center(target)
        r = (pos[0] - sp_c[0]) ** 2 + (pos[1] - sp_c[1]) ** 2
        if r >= rs_ls2:
            return None
        r = sqrt(r)
        dl = round(light_power * (1 - r / rs_ls))
        for point in target.tracking_points:
            if self.ray_tracing(target, pos, point, r):
                target.light += dl
                break

    def count_light_for_source(self, pos, light_power):
        for sprite in self.all_sprites:
            if isinstance(sprite, Torch):
            self.count_light_between(pos, light_power, sprite)

    def add_light(self, pos, light_power):
        self.light_sources.add((pos, light_power))
        self.count_light_for_source(pos, light_power)

    def remove_light(self, pos, light_power):
        if (pos, light_power) in self.light_sources:
            self.light_sources.remove((pos, light_power))
        else:
            self.light_sources.add((pos, -light_power))

        self.count_light_for_source(pos, -light_power)

    def relight_it(self, sprite: LightedSprite):
        sprite.light = MINIMUM_LIGHT
        for pos, light_power in self.light_sources:
            self.count_light_between(pos, light_power, sprite)

    def ray_tracing(self, target: LightedSprite, a, b=None, r=None):
        """Проверяет доходит ли луч от a до target."""
        if b is None:
            b = find_center(target)

        dx = b[0] - a[0]
        dy = b[1] - a[1]
        if r is None:
            r = sqrt(dx ** 2 + dy ** 2)
        if r == 0:
            return True
        m = 16  # Модификатор. Ускоряет просчёт
        r /= m
        dx = dx / r
        dy = dy / r
        now_cord = list(a)
        for _ in range(int(r) + 2):
            if now_cord[0] == b[0] and now_cord[1] == b[1]:
                return True
            if target.rect.collidepoint(*now_cord):
                return True

            tile = self.cords_to_tile(now_cord)
            if tile is None:
                continue
            if tile is target:
                return True
            if tile.is_collide:
                return False
            now_cord[0] += dx
            now_cord[1] += dy
        return False

    def cords_to_tile(self, cords):
        x = int(cords[0] // self.tile_width)
        y = int(cords[1] // self.tile_height)
        if (0 <= y < len(self.tiles)) and (0 <= x < len(self.tiles[y])):
            return self.tiles[y][x]
        else:
            return None


level = Level(1)
start_screen()
while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            terminate()
        elif event.type == pg.MOUSEBUTTONDOWN:
            pass
        elif event.type == pg.KEYUP:
            level.update(event)
    level.update()

    screen.fill(pg.Color("black"))
    level.draw_on(screen, pg.Rect(0, 0, WIDTH, HEIGHT))
    pg.display.flip()

    clock.tick(FPS)
    print("\rFPS:", clock.get_fps(), end='')
