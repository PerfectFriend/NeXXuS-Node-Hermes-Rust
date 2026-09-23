# HOT
#!/usr/bin/env python3
"""
Generate banner and icon for Elemental Life project.
"""
import math
from PIL import Image, ImageDraw

# Colors from the philosophy
BACKGROUND_COLOR = (10, 10, 20)  # deep midnight blue
FIRE_COLOR = (180, 30, 30)      # deep crimson
WATER_COLOR = (30, 120, 180)    # serene teal
AIR_COLOR = (30, 180, 200)      # airy cyan
EARTH_COLOR = (120, 80, 50)     # rich umber

def draw_hexagon(center_x, center_y, size, fill_color, draw_obj):
    points = []
    for i in range(6):
        angle_deg = 60 * i - 30  # start from top
        angle_rad = math.radians(angle_deg)
        point_x = center_x + size * math.cos(angle_rad)
        point_y = center_y + size * math.sin(angle_rad)
        points.append((point_x, point_y))
    draw_obj.polygon(points, fill=fill_color)

def generate_art(width, height, hex_size=20, seed=42):
    img = Image.new('RGB', (width, height), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)
    
    # Hexagon size
    HEX_SIZE = hex_size
    HEX_HEIGHT = HEX_SIZE * 2
    HEX_WIDTH = int(math.sqrt(3) * HEX_SIZE)
    HEX_HALF_HEIGHT = HEX_SIZE
    HEX_HALF_WIDTH = int(math.sqrt(3) * HEX_SIZE / 2)
    
    # Generate a grid of hexagons
    rows = int(height / (HEX_SIZE * 1.5)) + 2
    cols = int(width / (HEX_WIDTH)) + 2
    
    import random
    random.seed(seed)
    
    for row in range(rows):
        for col in range(cols):
            x = col * HEX_WIDTH + (HEX_WIDTH // 2 if row % 2 == 1 else 0)
            y = row * HEX_SIZE * 1.5 + HEX_SIZE
            
            if -HEX_WIDTH < x < width + HEX_WIDTH and -HEX_HEIGHT < y < height + HEX_HEIGHT:
                noise = random.Random()
                noise.seed(row * 1000 + col * 7 + 42)
                val = noise.random()
                
                if val < 0.25:
                    fill = FIRE_COLOR
                elif val < 0.5:
                    fill = WATER_COLOR
                elif val < 0.75:
                    fill = AIR_COLOR
                else:
                    fill = EARTH_COLOR
                
                intensity = noise.random() * 0.3 + 0.7
                fill = tuple(int(c * intensity) for c in fill)
                
                draw_hexagon(x, y, HEX_SIZE, fill, draw)
    
    # Subtle grid pattern
    for i in range(0, width, 40):
        draw.line([(i, 0), (i, height)], fill=(20, 20, 30), width=1)
    for i in range(0, height, 40):
        draw.line([(0, i), (width, i)], fill=(20, 20, 30), width=1)
    
    return img

if __name__ == "__main__":
    # Banner: wide image, e.g., 1920x400
    banner = generate_art(1920, 400, hex_size=15, seed=123)
    banner.save("/home/thomas/LivingCode/Projects/elemental-life/assets/banner.png", "PNG")
    print("Banner saved")
    
    # Icon: square, e.g., 512x512
    icon = generate_art(512, 512, hex_size=30, seed=456)
    icon.save("/home/thomas/LivingCode/Projects/elemental-life/assets/icon.png", "PNG")
    print("Icon saved")