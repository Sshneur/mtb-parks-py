from PIL import Image, ImageDraw, ImageFont
import math

W, H = 1200, 630
img = Image.new('RGB', (W, H), '#0b0d14')
draw = ImageDraw.Draw(img)

for y in range(H):
    ratio = y / H
    draw.line([(0, y), (W, y)], fill=(int(11+4*ratio), int(13+7*ratio), int(20+10*ratio)))

cx, cy = W // 2, H // 2 - 30
for r in range(350, 0, -1):
    alpha = int(6 * (1 - r / 350))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 50, 80, alpha))

font_title = ImageFont.truetype('C:/Windows/Fonts/impact.ttf', 88)
font_sub = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 24)
font_small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)

title = 'ЧТО С ГРУНТОМ?'
bbox = draw.textbbox((0, 0), title, font=font_title)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx, ty = (W - tw) // 2, H // 2 - 70

draw.text((tx + 4, ty + 4), title, font=font_title, fill=(0, 0, 0, 100))
draw.text((tx, ty), title, font=font_title, fill='#4a90e2')

line_y = ty + th + 12
draw.rectangle([(W // 2 - 60, line_y), (W // 2 + 60, line_y + 3)], fill='#ffd966')

sub = 'Погода на трассах • Прогноз грунта'
bbox2 = draw.textbbox((0, 0), sub, font=font_sub)
sw = bbox2[2] - bbox2[0]
draw.text(((W - sw) // 2, line_y + 22), sub, font=font_sub, fill='#a0b4cc')

url = 'gripchek.ru'
bbox3 = draw.textbbox((0, 0), url, font=font_small)
uw = bbox3[2] - bbox3[0]
draw.text(((W - uw) // 2, H - 50), url, font=font_small, fill='#556677')

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

draw_mountain(draw, -20, 400, 200, '#1e2a3a')
draw_mountain(draw, 200, 350, 150, '#253448', offset_y=10)
draw_mountain(draw, 400, 450, 250, '#1a2434', offset_y=20)
draw_mountain(draw, 700, 350, 180, '#1e2a3a', offset_y=5)
draw_mountain(draw, 850, 400, 220, '#253448', offset_y=15)

img = img.convert('RGB')
img.save('static/og-image.jpg', 'JPEG', quality=95)
print('SAVED')
import os; print(os.path.getsize('static/og-image.jpg'), 'bytes')
