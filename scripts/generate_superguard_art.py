# HOT
from PIL import Image, ImageDraw, ImageFilter
import math
import random

# Create 1920x1080 image
width, height = 1920, 1080
img = Image.new('RGB', (width, height), (10, 10, 25))  # Deep midnight blue
draw = ImageDraw.Draw(img)

# --- Background gradient from deep blue to slightly lighter
for y in range(height):
    ratio = y / height
    r = int(10 + 5 * ratio)
    g = int(10 + 3 * ratio)
    b = int(25 + 5 * ratio)
    for x in range(width):
        img.putpixel((x, y), (r, g, b))

# --- Concentric elliptical sectors (monitoring zones)
for i in range(0, 8):
    scale = 1 - (i * 0.12)
    outer_w = int(width * scale)
    outer_h = int(height * scale)
    inner_w = int(width * (scale - 0.08))
    inner_h = int(height * (scale - 0.08))
    
    # Gunmetal gray: dark steel blue-gray
    gray_val = int(80 + i * 15)
    color = (gray_val, gray_val + 10, gray_val + 20)
    
    # Draw elliptical annulus
    for dx in range(outer_w):
        for dy in range(outer_h):
            x = width // 2 - outer_w // 2 + dx
            y = height // 2 - outer_h // 2 + dy
            if 0 <= x < width and 0 <= y < height:
                outer_dist = ((x - width//2) / (outer_w/2))**2 + ((y - height//2) / (outer_h/2))**2
                inner_dist = ((x - width//2) / (inner_w/2))**2 + ((y - height//2) / (inner_h/2))**2
                if outer_dist <= 1 and inner_dist > 1:
                    current = img.getpixel((x, y))
                    new_r = int(0.7 * current[0] + 0.3 * color[0])
                    new_g = int(0.7 * current[1] + 0.3 * color[1])
                    new_b = int(0.7 * current[2] + 0.3 * color[2])
                    img.putpixel((x, y), (new_r, new_g, new_b))

# --- Active cyan accent (emissive detection spot)
accent_x = width // 2 + 200
accent_y = height // 2 - 100
accent_w = 300
accent_h = 200

# Glowing radial gradient
for r in range(accent_h, 0, -1):
    ratio = r / accent_h
    g_color = min(255, int(0 + 255 * (1 - ratio)))
    for c in range(accent_w):
        cx = accent_x - accent_w // 2 + c
        cy = accent_y - accent_h // 2 + r
        if 0 <= cx < width and 0 <= cy < height:
            dist = ((c - accent_w // 2) / (accent_w // 2))**2 + (r / (accent_h // 2))**2
            if dist <= 1:
                current = img.getpixel((cx, cy))
                new_r = min(255, current[0] + 100)
                new_g = min(255, current[1] + g_color)
                new_b = min(255, current[2] + 200)
                img.putpixel((cx, cy), (new_r, new_g, new_b))

# --- Subtle grid pattern (circuit board texture)
grid_spacing = 80
for x in range(0, width, grid_spacing):
    for y in range(0, height, grid_spacing):
        if 0 <= x < width and 0 <= y < height:
            draw.rectangle([x, y, x + 2, y + 2], fill=(50, 55, 70))

# --- Faint scan lines
for y in range(0, height, 4):
    if 0 <= y < height:
        draw.line([(0, y), (width, y)], fill=(30, 35, 50), width=1)

# --- Node indicators (mesoscopic)
node_positions = []
for i in range(20):
    angle = (2 * 3.14159 * i) / 20
    r = 300 + random.randint(-50, 50)
    nx = int(width // 2 + r * 0.8 * math.cos(angle) + random.randint(-30, 30))
    ny = int(height // 2 + r * 0.6 * math.sin(angle) + random.randint(-30, 30))
    if 0 <= nx < width and 0 <= ny < height:
        node_positions.append((nx, ny))

for nx, ny in node_positions[:15]:
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            if 0 <= nx+dx < width and 0 <= ny+dy < height:
                current = img.getpixel((nx+dx, ny+dy))
                new_r = int(0.8 * current[0] + 0.2 * 0)
                new_g = int(0.8 * current[1] + 0.2 * 255)
                new_b = int(0.8 * current[2] + 0.2 * 255)
                img.putpixel((nx+dx, ny+dy), (new_r, new_g, new_b))

# --- Microscopic status glyphs
for i in range(5):
    sx = width // 4 + i * 200 + random.randint(-20, 20)
    sy = height // 2 + random.randint(-20, 20)
    if 20 <= sx < width - 20 and 20 <= sy < height - 20:
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if 0 <= sx+dx < width and 0 <= sy+dy < height:
                    current = img.getpixel((sx+dx, sy+dy))
                    new_r = int(0.9 * current[0] + 0.1 * 80)
                    new_g = int(0.9 * current[1] + 0.1 * 85)
                    new_b = int(0.9 * current[2] + 0.1 * 90)
                    img.putpixel((sx+dx, sy+dy), (new_r, new_g, new_b))

# Apply slight blur
img = img.filter(ImageFilter.GaussianBlur(radius=1.5))

# Save
img.save('/home/thomas/LivingCode/Projects/superguard/assets/SuperGuard-OmniWatch.png', quality=95)
print(f"Image saved: {img.size}")