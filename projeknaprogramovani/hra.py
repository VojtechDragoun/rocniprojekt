"""
Jedno-souborová demo hra/menu v Python + pygame
Popis: Zobrazí hlavní menu s tlačítky: Hra, Nastavení, Login, Konec.
- Hra: jednoduchá ukázka (ovládání: šipky, ESC do menu)
- Nastavení: ovladač hlasitosti (slider) + návrat
- Login: textové pole pro zadání jména uživatele
- Konec: ukončí program

Spuštění:
1) Nainstaluj pygame: pip install pygame
2) Spusť: python pygame_menu.py

Poznámka: Kód je silně okomentovaný, aby se snadno upravoval.
"""

import pygame
import sys

# --- Konfigurace ---
WIDTH, HEIGHT = 1920, 1080  # velikost okna
FPS = 60
FONT_NAME = None  # pokud chcete jiný font, zadejte cestu

# Barvy (RGB)
BG_COLOR = (30, 30, 40)
PANEL_COLOR = (45, 50, 60)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER = (100, 160, 210)
TEXT_COLOR = (240, 240, 240)
ACCENT = (255, 165, 0)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Menu - Demo hry v pygame")
clock = pygame.time.Clock()

# Základní fonty
def load_font(size):
    return pygame.font.Font(FONT_NAME, size)

font_big = load_font(40)
font_med = load_font(28)
font_small = load_font(18)

# --- Pomocné třídy ---
class Button:
    """Jednoduché tlačítko s textem, hover a callbackem."""
    def __init__(self, rect, text, callback, font=font_med):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.callback = callback
        self.font = font
        self.hovered = False

    def draw(self, surf):
        # Vybere barvu podle toho, jestli nad tímto tlačítkem je myš
        color = BUTTON_HOVER if self.hovered else BUTTON_COLOR
        pygame.draw.rect(surf, color, self.rect, border_radius=8)
        # Outline
        pygame.draw.rect(surf, (20,20,20), self.rect, 2, border_radius=8)
        # Vykreslí text uprostřed tlačítka
        txt_surf = self.font.render(self.text, True, TEXT_COLOR)
        tx = self.rect.x + (self.rect.width - txt_surf.get_width()) // 2
        ty = self.rect.y + (self.rect.height - txt_surf.get_height()) // 2
        surf.blit(txt_surf, (tx, ty))

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                # zavolá callback (akce tlačítka)
                self.callback()


class Slider:
    """Horizontální slider pro nastavení hodnoty (např. hlasitost).
    Vrací hodnotu v rozsahu 0.0 .. 1.0
    """
    def __init__(self, rect, value=0.5):
        self.rect = pygame.Rect(rect)
        self.value = max(0.0, min(1.0, value))
        self.dragging = False

    def draw(self, surf):
        # pozadí slideru
        pygame.draw.rect(surf, (80,80,80), self.rect, border_radius=6)
        # výplň podle hodnoty
        fill_rect = self.rect.copy()
        fill_rect.width = int(self.rect.width * self.value)
        pygame.draw.rect(surf, ACCENT, fill_rect, border_radius=6)
        # kolečko (thumb)
        cx = self.rect.x + int(self.rect.width * self.value)
        cy = self.rect.centery
        pygame.draw.circle(surf, (230,230,230), (cx, cy), 10)
        pygame.draw.circle(surf, (20,20,20), (cx, cy), 11, 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self._update_value_from_pos(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_value_from_pos(event.pos)

    def _update_value_from_pos(self, pos):
        x = pos[0]
        rel = (x - self.rect.x) / max(1, self.rect.width)
        self.value = max(0.0, min(1.0, rel))


class TextInput:
    """Jednoduché textové pole pro login (bez pokročilých funkcí).
    - backspace funguje
    - ENTER potvrdí
    """
    def __init__(self, rect, text=''):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.active = False
        self.cursor_timer = 0.0

    def draw(self, surf):
        pygame.draw.rect(surf, (255,255,255), self.rect, 2, border_radius=6)
        txt_surf = font_med.render(self.text, True, TEXT_COLOR)
        surf.blit(txt_surf, (self.rect.x+8, self.rect.y + (self.rect.height - txt_surf.get_height())//2))
        # vykreslit kurzor blikající
        if self.active:
            self.cursor_timer += 1/FPS
            if (self.cursor_timer % 1.0) < 0.6:
                cx = self.rect.x + 8 + txt_surf.get_width() + 2
                cy1 = self.rect.y + 8
                cy2 = self.rect.y + self.rect.height - 8
                pygame.draw.line(surf, TEXT_COLOR, (cx, cy1), (cx, cy2), 2)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                self.active = False
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                # Zabrání vložení příliš dlouhého jména
                if len(self.text) < 20 and event.unicode.isprintable():
                    self.text += event.unicode


# --- Hlavní stavy aplikace ---
STATE_MENU = 'menu'
STATE_GAME = 'game'
STATE_SETTINGS = 'settings'
STATE_LOGIN = 'login'

state = STATE_MENU

# Globální proměnné pro nastavení / uživatele
volume = 0.5
username = ''

# --- Implementace obrazovek ---
# 1) Menu
buttons = []

def start_game():
    global state
    state = STATE_GAME


def open_settings():
    global state
    state = STATE_SETTINGS


def open_login():
    global state
    state = STATE_LOGIN


def quit_game():
    pygame.quit()
    sys.exit()

# vytvoření tlačítek menu
btn_w, btn_h = 300, 60
start_y = 190
gap = 20
labels = [("Hra", start_game), ("Nastavení", open_settings), ("Login", open_login), ("Konec", quit_game)]
for i, (lab, cb) in enumerate(labels):
    x = (WIDTH - btn_w)//2
    y = start_y + i*(btn_h + gap)
    buttons.append(Button((x, y, btn_w, btn_h), lab, cb))

# 2) Nastavení
slider = Slider((WIDTH//2 - 180, HEIGHT//2 - 20, 360, 40), value=volume)
back_button = Button((20, HEIGHT - 80, 120, 50), "Zpět", lambda: set_state(STATE_MENU))

# 3) Login
input_box = TextInput((WIDTH//2 - 200, HEIGHT//2 - 30, 400, 60))
login_back = Button((20, HEIGHT - 80, 120, 50), "Zpět", lambda: set_state(STATE_MENU))
login_confirm = Button((WIDTH//2 - 70, HEIGHT//2 + 50, 140, 45), "Potvrdit", lambda: confirm_login())

# 4) Game - jednoduchá ukázka: čtverec kterým hýbáme
player_rect = pygame.Rect(WIDTH//2 - 20, HEIGHT//2 - 20, 40, 40)
player_speed = 250  # px/s

def set_state(s):
    global state
    state = s


def confirm_login():
    global username, state
    username = input_box.text.strip()
    # pokud je prázdné, nastavíme náhradní text
    if username == '':
        username = 'Host'
    state = STATE_MENU

# --- Hlavní smyčka ---

def handle_events():
    global volume, state
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            quit_game()
        # deleguj události podle stavu
        if state == STATE_MENU:
            for b in buttons:
                b.handle_event(event)
        elif state == STATE_SETTINGS:
            slider.handle_event(event)
            back_button.handle_event(event)
            # upravíme globální hodnotu hlasitosti
            volume = slider.value
        elif state == STATE_LOGIN:
            input_box.handle_event(event)
            login_back.handle_event(event)
            login_confirm.handle_event(event)
        elif state == STATE_GAME:
            # V herním stavu zaregistrujeme jen klávesy, myš necháme trpět
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # návrat do menu
                state = STATE_MENU


def draw_menu():
    # pozadí a panel
    pygame.draw.rect(screen, PANEL_COLOR, (60, 60, WIDTH-120, HEIGHT-120), border_radius=12)
    title = font_big.render("Hlavní menu", True, TEXT_COLOR)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 90))

    # zobrazení přihlášeného uživatele nahoře vpravo
    user_txt = font_small.render(f"Uživatel: {username if username else 'Nepřihlášen'}", True, TEXT_COLOR)
    screen.blit(user_txt, (WIDTH - user_txt.get_width() - 20, 20))

    # vykreslí tlačítka
    for b in buttons:
        b.draw(screen)

    # nápověda dole
    hint = font_small.render("Použij myš k interakci. Hra: šipky/WSAD, ESC = návrat.", True, (180,180,180))
    screen.blit(hint, (20, HEIGHT - 30))


def draw_settings():
    pygame.draw.rect(screen, PANEL_COLOR, (60, 60, WIDTH-120, HEIGHT-120), border_radius=12)
    title = font_big.render("Nastavení", True, TEXT_COLOR)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 90))

    # label a slider (hlasitos)
    lbl = font_med.render("Hlasitost", True, TEXT_COLOR)
    screen.blit(lbl, (WIDTH//2 - 220, HEIGHT//2 - 60))
    slider.draw(screen)

    # zobrazí číselnou hodnotu
    val_txt = font_small.render(f"{int(slider.value*100)}%", True, TEXT_COLOR)
    screen.blit(val_txt, (WIDTH//2 + 200, HEIGHT//2 - 10))

    back_button.draw(screen)


def draw_login():
    pygame.draw.rect(screen, PANEL_COLOR, (60, 60, WIDTH-120, HEIGHT-120), border_radius=12)
    title = font_big.render("Přihlášení", True, TEXT_COLOR)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 90))

    sub = font_small.render("Zadej své uživatelské jméno a stiskni Potvrdit:", True, TEXT_COLOR)
    screen.blit(sub, (WIDTH//2 - sub.get_width()//2, HEIGHT//2 - 80))

    input_box.draw(screen)
    login_confirm.draw(screen)
    login_back.draw(screen)


def update_game(dt):
    # jednoduchá fyzika pohybu hráče: čtverec ovladatelný klávesami
    keys = pygame.key.get_pressed()
    dx = dy = 0
    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
        dx -= 1
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
        dx += 1
    if keys[pygame.K_UP] or keys[pygame.K_w]:
        dy -= 1
    if keys[pygame.K_DOWN] or keys[pygame.K_s]:
        dy += 1

    # normování diagonály
    if dx != 0 and dy != 0:
        dx *= 0.7071
        dy *= 0.7071

    player_rect.x += int(dx * player_speed * dt)
    player_rect.y += int(dy * player_speed * dt)

    # udržení v obrazovce
    player_rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))


def draw_game():
    # jednoduché vykreslení herního světa --- pozadí a hráč
    screen.fill((20, 30, 50))
    # hud: jméno hráče a instrukce
    name_txt = font_small.render(f"Hráč: {username if username else 'Host'}", True, TEXT_COLOR)
    screen.blit(name_txt, (10, 10))
    hint = font_small.render("ESC = návrat do menu", True, (180,180,180))
    screen.blit(hint, (10, 30))
    # hráč
    pygame.draw.rect(screen, (200,80,80), player_rect, border_radius=6)


# Hlavní běh programu

def main():
    global volume, state
    # hlavní smyčka
    while True:
        dt = clock.tick(FPS) / 1000.0  # delta-time v sekundách
        handle_events()

        # logika podle stavu
        if state == STATE_MENU:
            # vykreslíme pozadí i panel
            screen.fill(BG_COLOR)
            draw_menu()
        elif state == STATE_SETTINGS:
            screen.fill(BG_COLOR)
            draw_settings()
        elif state == STATE_LOGIN:
            screen.fill(BG_COLOR)
            draw_login()
        elif state == STATE_GAME:
            update_game(dt)
            draw_game()

        # update obrazovky
        pygame.display.flip()


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        pass
    except Exception as e:
        # Pokud se něco pokazí, vypíšeme chybu a ukončíme
        print('Chyba:', e)
        pygame.quit()
        sys.exit()
