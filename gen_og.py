from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

W, H = 1200, 630
img = Image.new('RGB', (W, H), '#0b0d14')
draw = ImageDraw.Draw(img)

# Gradient overlay: dark blue to darker
for y in range(H):
    ratio = y / H
    r = int(11 + 4 * ratio)
    g = int(13 + 7 * ratio)
    b = int(20 + 10 * ratio)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Subtle radial glow in center
cx, cy = W // 2, H // 2
for r in range(300, 0, -1):
    alpha = int(8 * (1 - r / 300))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(20, 28, 48, alpha))

# Load fonts
font_title = ImageFont.truetype('C:/Windows/Fonts/impact.ttf', 72)
font_sub = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 26)
font_small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)

# Title text
title = 'MTB ПАРКИ 2.0'
bbox = draw.textbbox((0, 0), title, font=font_title)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
tx = (W - tw) // 2
ty = H // 2 - 60

# Shadow
draw.text((tx + 3, ty + 3), title, font=font_title, fill=(0, 0, 0, 128))
draw.text((tx, ty), title, font=font_title, fill='#4a90e2')

# Accent line under title
line_y = ty + th + 10
draw.rectangle([(W // 2 - 80, line_y), (W // 2 + 80, line_y + 3)], fill='#ffd966')

# Subtitle
sub = 'Погода • Трассы • Сообщество'
bbox2 = draw.textbbox((0, 0), sub, font=font_sub)
sw = bbox2[2] - bbox2[0]
draw.text(((W - sw) // 2, line_y + 20), sub, font=font_sub, fill='#a0b4cc')

# URL at bottom
url = 'gripchek.ru'
bbox3 = draw.textbbox((0, 0), url, font=font_small)
uw = bbox3[2] - bbox3[0]
draw.text(((W - uw) // 2, H - 50), url, font=font_small, fill='#556677')

# Mountain silhouette at bottom
def draw_mountain(draw, x, w, h, color, offset_y=0):
    points = [(x, H - offset_y)]
    steps = max(10, w // 10)
    for i in range(steps + 1):
        px = x + (w * i / steps)
        py = H - offset_y
        if 0 < i < steps:
            py -= h * (0.3 + 0.7 * math.sin(math.pi * i / steps))
        points.append((px, py))
    points.append((x + w, H - offset_y))
    draw.polygon(points, fill=color)

draw_mountain(draw, -20, 400, 200, '#1e2a3a', offset_y=0)
draw_mountain(draw, 200, 350, 150, '#253448', offset_y=10)
draw_mountain(draw, 400, 450, 250, '#1a2434', offset_y=20)
draw_mountain(draw, 700, 350, 180, '#1e2a3a', offset_y=5)
draw_mountain(draw, 850, 400, 220, '#253448', offset_y=15)

# Bottom gradient fade
for y in range(H - 80, H):
    alpha = int(255 * (y - (H - 80)) / 80)
    draw.line([(0, y), (W, y)], fill=(int(11*(1-alpha/255) + 0*alpha/255), int(13*(1-alpha/255) + 0*alpha/255), int(20*(1-alpha/255) + 0*alpha/255)))

# Save
img.save('static/og-image.png', 'PNG')
print('OG image saved')
