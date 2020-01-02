import os
import sys
from math import ceil
import pygame as pg

# инициализация pygame
FPS = 60
pg.init()
size = WIDTH, HEIGHT = 512, 512
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

class Tile(pg.sprite.Sprite):
    tile_images = {'wall': load_image('wall.png'), 'empty': load_image('empty.png')}

    def __init__(self, image_type, is_collide, pos_x, pos_y, level):
        if is_collide:
            super().__init__(level.tiles_group, level.all_sprites, level.collided_sprites)
        else:
            super().__init__(level.tiles_group, level.all_sprites)
        self.level = level
        self.image = Tile.tile_images[image_type]
        self.rect = self.image.get_rect().move(level.tile_width * pos_x, level.tile_height * pos_y)


class Player(pg.sprite.Sprite):
    default_rect, frames = cut_sheet(load_image('player.png'), 1, 1)

    def __init__(self, pos_x, pos_y, level):
        super().__init__(level.all_sprites, level.player_group)
        self.level = level
        self.rect = Player.default_rect.copy().move(level.tile_width * pos_x,
                                                    level.tile_height * pos_y)
        self.cur_frame = 0
        self.update_speed = 1 / 10
        self.image = Player.frames[int(self.cur_frame)]
        self.real_pos = [self.rect.x, self.rect.y]  # для вещественных координат
        self.speed = 4

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

        if dx and dy:
            # Выравниваем скорость
            dx = dx / (2 ** .5)
            dy = dy / (2 ** .5)

        # изменяем координаты
        self.real_pos[0] += dx
        self.real_pos[1] += dy
        self.rect.x = ceil(self.real_pos[0])
        self.rect.y = ceil(self.real_pos[1])

        # изменяем кадр
        self.cur_frame += self.update_speed
        self.cur_frame %= len(Player.frames)
        self.image = Player.frames[int(self.cur_frame)]


class Level(pg.Surface):
    tile_width = tile_height = 64

    def __init__(self, level_num):
        # группы спрайтов
        self.all_sprites = pg.sprite.Group()
        self.collided_sprites = pg.sprite.Group()
        self.tiles_group = pg.sprite.Group()
        self.player_group = pg.sprite.Group()
        self.enemies_group = pg.sprite.Group()

        self.level_map = self.load_level(level_num)
        self.player, self.cols, self.rows = None, None, None
        self.generate_level()

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

    def generate_level(self):
        level = self.level_map
        self.cols = 0
        self.rows = len(level)
        for y in range(len(level)):
            self.cols = max(self.cols, len(level[y]))
            for x in range(len(level[y])):
                if level[y][x] == '.':
                    Tile('empty', False, x, y, self)
                elif level[y][x] == '#':
                    Tile('wall', True, x, y, self)
                elif level[y][x] == '@':
                    Tile('empty', False, x, y, self)
                    self.player = Player(x, y, self)

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
        x = min(self.width - rect.width, max(0, target.x + target.width // 2 - rect.width // 2))
        y = min(self.height - rect.height, max(0, target.y + target.height // 2 - rect.height // 2))

        screen.blit(self, rect, rect.copy().move(x, y))


level = Level(1)
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
