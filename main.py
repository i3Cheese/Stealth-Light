import os
import sys
from math import ceil, sqrt
from typing import Tuple, Set, Any, List

import pygame as pg

# инициализация pygame
FPS = 60
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
    def __init__(self, *groups):
        super().__init__(*groups)
        self.real_image = None
        self._image = None
        self._light = 0

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
        r = self._image.get_rect()
        dark = self._image.copy()
        dark.fill((0, 0, 0, max(0, min(255, 255 - self.light))))
        self._image.blit(dark, (0, 0))

    @property
    def tracking_points(self):
        return [self.rect.topleft,
                self.rect.topright,
                self.rect.bottomleft,
                self.rect.bottomright]


class Tile(LightedSprite):
    tile_images = {'wall': load_image('wall.png'), 'empty': load_image('empty.png')}

    def __init__(self, image_type, is_collide, pos_x, pos_y, level):
        if is_collide:
            super().__init__(level.tiles_group, level.all_sprites, level.collided_sprites)
        else:
            super().__init__(level.tiles_group, level.all_sprites)
        self.is_collide = is_collide
        self.level = level
        self.image = Tile.tile_images[image_type]
        self.light = 0
        self.rect = self.image.get_rect().move(level.tile_width * pos_x, level.tile_height * pos_y)


class Player(LightedSprite):
    default_rect, frames = cut_sheet(load_image('player.png'), 1, 1)
    update_light_speed = 5

    def __init__(self, pos_x, pos_y, level):
        super().__init__(level.all_sprites, level.player_group)
        self.level = level
        self.rect = Player.default_rect.copy().move(level.tile_width * pos_x,
                                                    level.tile_height * pos_y)
        self.cur_frame = 0
        self.update_speed = 1 / 10
        self.image = Player.frames[int(self.cur_frame)]
        self.speed = 4

        self.light_power = 255
        self.count_move_frames = 0
        self.last_light_pos = self.rect.center
        self.level.add_light(self.last_light_pos, self.light_power)

    def update(self):
        dx = 0
        dy = 0
        if pg.key.get_pressed()[pg.K_UP]:
            dy -= self.speed
        if pg.key.get_pressed()[pg.K_DOWN]:
            dy += self.speed
        if pg.key.get_pressed()[pg.K_LEFT]:
            dx -= self.speed
        if pg.key.get_pressed()[pg.K_RIGHT]:
            dx += self.speed

        if dx and dy:  # Выравниваем скорость
            dx = dx / (2 ** .5)
            dy = dy / (2 ** .5)

        # изменяем координаты
        if dx or dy:
            dx, dy = ceil(dx), ceil(dy)
            self.rect.x += dx
            while pg.sprite.spritecollideany(self, self.level.collided_sprites):
                if dx == 0:
                    break
                self.rect.x -= dx // abs(dx)  # выталкивает персонажа из стен
            self.rect.y += dy
            while pg.sprite.spritecollideany(self, self.level.collided_sprites):
                if dy == 0:
                    break
                self.rect.y -= dy // abs(dy)  # выталкивает персонажа из стен

            # Пересчёт света
            self.count_move_frames += 1
            if self.count_move_frames == self.update_light_speed:
                self.count_move_frames = 0
                self.level.remove_light(self.last_light_pos, self.light_power)
                self.level.add_light(self.rect.center, self.light_power)
                self.last_light_pos = self.rect.center
            self.level.relight_it(self)

        # изменяем кадр
        self.cur_frame += self.update_speed
        self.cur_frame %= len(Player.frames)
        self.image = Player.frames[int(self.cur_frame)]


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
        self.enemies_group.draw(self)
        self.player_group.draw(self)

        # вычисляем координаты прямоугольника, который будем рисовать
        target = self.player.rect  # фокус на игроке
        x = max(0, min(self.width - rect.width, target.x + target.width // 2 - rect.width // 2))
        y = max(0, min(self.height - rect.height, target.y + target.height // 2 - rect.height // 2))

        screen.blit(self, rect, rect.copy().move(x, y))

    def count_light_between(self, pos, light_power, target: LightedSprite):
        ray_step = 64
        light_step = 5

        # просто константы для более бытрого счёта
        rs_ls = ray_step * light_step
        rs_ls2 = rs_ls ** 2
        sp_c = find_center(target)
        r = (pos[0] - sp_c[0]) ** 2 + (pos[1] - sp_c[1]) ** 2
        if r >= rs_ls2:
            return None
        r = sqrt(r)
        dl = int(light_power * (1 - r / rs_ls))
        for point in target.tracking_points:
            if self.ray_tracing(target, pos, point, r):
                target.light += dl
                break

    def count_light_for_source(self, pos, light_power):
        for sprite in self.all_sprites:
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
        sprite.light = 0
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
        m = 8  # Модификатор. Ускоряет просчёт
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


level = Level(2)
start_screen()
while running:
    for event in pg.event.get():
        if event.type == pg.QUIT:
            terminate()
        elif event.type == pg.MOUSEBUTTONDOWN:
            pass
    level.update()

    screen.fill(pg.Color("black"))
    level.draw_on(screen, pg.Rect(0, 0, WIDTH, HEIGHT))
    pg.display.flip()

    clock.tick(FPS)
    print("\rFPS:", clock.get_fps(), end='')
