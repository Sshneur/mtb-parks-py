import os

# Yandex OAuth
YA_CLIENT_ID = os.getenv("YA_CLIENT_ID", "")
YA_CLIENT_SECRET = os.getenv("YA_CLIENT_SECRET", "")
YA_REDIRECT_URI = os.getenv("YA_REDIRECT_URI", "https://gripcheck.ru/auth/yandex/callback")

# VK OAuth
VK_APP_ID = os.getenv("VK_APP_ID", "")
VK_SECRET_KEY = os.getenv("VK_SECRET_KEY", "")
VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI", "https://gripcheck.ru/auth/vk/callback")
VK_API_VERSION = "5.199"
