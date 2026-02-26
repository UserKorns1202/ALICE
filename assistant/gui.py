import pygame
import sys
import random
import os

# Initialize Pygame
pygame.init()

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Colors
WHITE = (255, 255, 255)

# Function to read character directory path from config file
def get_char_dir():
    try:
        with open("config.txt", "r") as file:
            charDir = file.read().strip()
            if charDir == "virgil":
                charDir = "VRGL"
            return charDir
    except FileNotFoundError:
        return "VRGL"  # Fallback to default character directory

# Initial load of character directory
charDir = get_char_dir()

# Load character images
def load_images(charDir, folder):
    return [pygame.image.load(os.path.join("assets", charDir, folder, f)) for f in os.listdir(os.path.join("assets", charDir, folder))]

idle_frames = load_images(charDir, "idle")
listening_frames = load_images(charDir, "listening")
angry_frames = load_images(charDir, "angry")
working_frames = load_images(charDir, "working")
math_frames = load_images(charDir, "math")
speaking_frames = load_images(charDir, "speaking")

class Character(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.idle_frames = idle_frames
        self.listening_frames = listening_frames
        self.angry_frames = angry_frames
        self.working_frames = working_frames
        self.math_frames = math_frames
        self.speaking_frames = speaking_frames
        self.frames = self.idle_frames  # Initialize frames to idle frames
        self.image_index = 0
        self.image = self.frames[self.image_index]
        self.rect = self.image.get_rect()
        self.rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    
    def update(self):
        self.image_index = (self.image_index + 1) % len(self.frames)
        self.image = self.frames[self.image_index]

    def set_idle(self):
        self.frames = self.idle_frames

    def set_listening(self):
        self.frames = self.listening_frames

    def set_angry(self):
        self.frames = self.angry_frames

    def set_working(self):
        self.frames = self.working_frames

    def set_math(self):
        self.frames = self.math_frames

    def set_speaking(self):
        self.frames = self.speaking_frames

# Function to read commands from file
def read_command():
    try:
        with open("gui_command.txt", "r") as f:
            command = f.read().strip()
        return command
    except FileNotFoundError:
        return ""

# Function to handle events
def handle_events():
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

def main():
    global charDir, idle_frames, listening_frames, angry_frames, working_frames, math_frames, speaking_frames

    # Set up the screen
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption(charDir)

    # Create character
    character = Character()
    all_sprites = pygame.sprite.Group()
    all_sprites.add(character)

    clock = pygame.time.Clock()
    running = True  # Flag to control the main loop

    while running:
        handle_events()

        # Reload character directory if changed
        new_charDir = get_char_dir()
        if new_charDir != charDir:
            charDir = new_charDir
            idle_frames = load_images(charDir, "idle")
            listening_frames = load_images(charDir, "listening")
            angry_frames = load_images(charDir, "angry")
            working_frames = load_images(charDir, "working")
            math_frames = load_images(charDir, "math")
            speaking_frames = load_images(charDir, "speaking")
            character.idle_frames = idle_frames
            character.listening_frames = listening_frames
            character.angry_frames = angry_frames
            character.working_frames = working_frames
            character.math_frames = math_frames
            character.speaking_frames = speaking_frames
            character.set_idle()  # Reset to idle frames

        # Check for commands
        command = read_command()
        if command == "listening":
            character.set_listening()
        elif command == "idle":
            character.set_idle()
        elif command == "angry":
            character.set_angry()
        elif command == "working":
            character.set_working()
        elif command == "math":
            character.set_math()
        elif command == "speaking":
            character.set_speaking()
        elif command == "exit":  # Check for exit command
            running = False      # Set running flag to False

        # Update the character
        character.update()

        # Clear the screen
        screen.fill(WHITE)

        # Draw all sprites
        all_sprites.draw(screen)

        # Update the display
        pygame.display.flip()

        # Cap the frame rate
        clock.tick(1)  # Adjust frame rate for smoother animation (higher = faster)

    # Close Pygame and exit the program
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
