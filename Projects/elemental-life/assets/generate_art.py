# HOT
#!/usr/bin/env python3
"""
Generate a visual representation of the Elemental Life philosophy.
Creates a hexagonal grid with cells colored by element (fire, water, air, earth).
"""
import math
from PIL import Image, ImageDraw

# Image dimensions
WIDTH, HEIGHT = 1920, 1080
BACKGROUND_COLOR = (10, 10, 20)  # deep midnight blue

# Element colors (approximate)
FIRE_COLOR = (180, 30, 30)      # deep crimson
WATER_COLOR = (30, 120, 180)    # serene teal
AIR_COLOR = (30, 180, 200)      # airy cyan
EARTH_COLOR = (120, 80, 50)     # rich umber

# Hexagon size
HEX_SIZE = 20  # radius of hexagon (distance from center to vertex)
HEX_HEIGHT = HEX_SIZE * 2
HEX_WIDTH = int(math.sqrt(3) * HEX_SIZE)
HEX_HALF_HEIGHT = HEX_SIZE
HEX_HALF_WIDTH = int(math.sqrt(3) * HEX_SIZE / 2)

# Create image
img = Image.new('RGB', (WIDTH, HEIGHT), BACKGROUND_COLOR)
draw = ImageDraw.Draw(img)

# Function to draw a hexagon at (x, y) center
def draw_hexagon(center_x, center_y, size, fill_color):
    points = []
    for i in range(6):
        angle_deg = 60 * i - 30  # start from top
        angle_rad = math.radians(angle_deg)
        point_x = center_x + size * math.cos(angle_rad)
        point_y = center_y + size * math.sin(angle_rad)
        points.append((point_x, point_y))
    draw.polygon(points, fill=fill_color)

# Generate a grid of hexagons
# We'll offset rows to create a honeycomb pattern
rows = int(HEIGHT / (HEX_SIZE * 1.5)) + 2
cols = int(WIDTH / (HEX_WIDTH)) + 2

# Use a seeded random pattern to simulate natural distribution
import random
random.seed(42)  # for reproducibility

for row in range(rows):
    for col in range(cols):
        # Calculate center x, y for hexagon
        x = col * HEX_WIDTH + (HEX_WIDTH // 2 if row % 2 == 1 else 0)
        y = row * HEX_SIZE * 1.5 + HEX_SIZE
        
        # Only draw if within image bounds (with some margin)
        if -HEX_WIDTH < x < WIDTH + HEX_WIDTH and -HEX_HEIGHT < y < HEIGHT + HEX_HEIGHT:
            # Choose element based on some noise to create clusters
            # Use Perlin-like noise via random seeded by position
            noise = random.Random()
            noise.seed(row * 1000 + col * 7 + 42)
            val = noise.random()
            
            # Assign element with some weighting
            if val < 0.25:
                fill = FIRE_COLOR
            elif val < 0.5:
                fill = WATER_COLOR
            elif val < 0.75:
                fill = AIR_COLOR
            else:
                fill = EARTH_COLOR
            
            # Add subtle variation to color based on intensity
            # Simulate activity level
            intensity = noise.random() * 0.3 + 0.7  # 0.7 to 1.0
            fill = tuple(int(c * intensity) for c in fill)
            
            draw_hexagon(x, y, HEX_SIZE, fill)

# Add a subtle grid pattern to suggest circuit board texture (optional)
# Draw faint lines
for i in range(0, WIDTH, 40):
    draw.line([(i, 0), (i, HEIGHT)], fill=(20, 20, 30), width=1)
for i in range(0, HEIGHT, 40):
    draw.line([(0, i), (WIDTH, i)], fill=(20, 20, 30), width=1)

# Save the image
output_path = "/home/thomas/LivingCode/Projects/elemental-life/assets/ElementalLife-Visual.png"
img.save(output_path, "PNG")
print(f"Saved artwork to {output_path}")