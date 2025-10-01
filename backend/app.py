import json
import base64
import asyncio
import urllib.parse

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from services.vpn.manager import AsyncVPNManager
from config_data.config import Config, load_config

config: Config = load_config()

router = APIRouter()

CONNECT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Подключение VPN...</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script>
        function redirectToApp() {
            const appUrl = "{{ app_url }}";

            // Пробуем открыть приложение
            window.location.href = appUrl;

            // Если через 2 секунды не открылось, показываем fallback
            setTimeout(function() {
                document.getElementById('autoRedirect').style.display = 'none';
                document.getElementById('manualRedirect').style.display = 'block';
                document.getElementById('fallbackMessage').style.display = 'block';
            }, 2000);
        }

        window.onload = function() {
            redirectToApp();
        };
    </script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 30px;
            border-radius: 20px;
            text-align: center;
        }
        .button {
            display: block;
            padding: 15px 30px;
            background: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: bold;
            margin: 15px 0;
            transition: transform 0.2s;
        }
        .button:hover {
            transform: scale(1.05);
            background: #45a049;
        }
        .loading {
            font-size: 20px;
            margin: 30px 0;
        }
        .spinner {
            border: 4px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top: 4px solid white;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .hidden {
            display: none;
        }
        .url-info {
            background: rgba(0,0,0,0.2);
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
            word-break: break-all;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔒 Подключение VPN</h1>

        <div id="autoRedirect">
            <div class="loading">
                <div class="spinner"></div>
                <p>Открываем приложение...</p>
            </div>
        </div>

        <div id="manualRedirect" class="hidden">
            <p>Не удалось открыть приложение автоматически</p>
            <a href="{{ app_url }}" class="button">
                📱 Нажмите чтобы открыть вручную
            </a>
        </div>

        <div id="fallbackMessage" class="hidden">
            <p><strong>Если приложение не установлено:</strong></p>
            <a href="https://play.google.com/store/apps/details?id=com.v2raytun" 
               class="button" style="background: #2196F3;">
                📥 Скачать V2rayTUN
            </a>
        </div>

        <div style="margin-top: 30px; font-size: 14px; opacity: 0.8;">
            <p>VPN: {{ vpn_name }}</p>
            <p>Сервер: {{ server_address }}</p>
        </div>

        <div class="url-info">
            <strong>URL для открытия:</strong><br>
            {{ app_url }}
        </div>
    </div>
</body>
</html>
"""


@router.get("/")
async def root():
    """
    Корневой эндпоинт
    """
    return {
        "service": "VPN Subscription Service",
        "version": "1.0.0",
        "endpoints": {
            "subscription": "GET /sub/{user_hash}/{user_id} - JSON для V2rayTUN",
            "connect": "GET /connect?url=... - Редирект на приложение"
        }
    }


@router.get("/sub/{user_hash}/{user_id}")
async def get_subscription(
        user_hash: str,
        user_id: int,
        request: Request
):
    """
    Эндпоинт для V2rayTUN - возвращает чистый JSON конфиг
    """
    try:
        manager: AsyncVPNManager = request.app.state.manager
        decoded_hash = base64.urlsafe_b64decode(user_hash + '==').decode()
        user_id_from_hash, client_id = decoded_hash.split(':')

        if int(user_id_from_hash) != int(user_id):
            raise HTTPException(status_code=404, detail="Invalid subscription")

        # Получаем информацию о VPN
        vpn_info = await manager.get_vpn_info(int(user_id), client_id)

        if not vpn_info['found']:
            raise HTTPException(status_code=404, detail="VPN not found")

        # Генерируем конфиг V2ray
        v2ray_config = generate_v2ray_config(client_id, vpn_info, user_id)

        # Всегда возвращаем JSON для этого эндпоинта
        return JSONResponse(content={
            "version": 2,
            "servers": [v2ray_config],
            "remark": vpn_info['vpn_name'],
            "status": "active"
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


@router.get("/connect")
async def connect_redirect(
        request: Request,
        url: str = Query(..., description="URL для редиректа в приложение")
):
    """
    Эндпоинт для редиректа в приложение
    Пример: /connect?url=v2raytun://import-sub?uri=https://domain.com/sub/abc123/8005178596
    """
    try:
        manager: AsyncVPNManager = request.app.state.manager
        if not is_safe_url(url):
            raise HTTPException(status_code=400, detail="Invalid URL")

        # Если это v2raytun ссылка - делаем редирект
        if url.startswith('v2raytun://'):
            return RedirectResponse(url=url)

        # Если это обы HTTP ссылка на подписку
        elif url.startswith('https://') and '/sub/' in url:
            # Извлекаем user_hash и user_id из URL
            parts = url.split('/sub/')
            if len(parts) == 2:
                sub_path = parts[1]
                sub_parts = sub_path.split('/')
                if len(sub_parts) >= 2:
                    user_hash = sub_parts[0]
                    user_id = sub_parts[1]

                    # Получаем информацию о VPN для отображения
                    try:
                        decoded_hash = base64.urlsafe_b64decode(user_hash + '==').decode()
                        user_id_from_hash, client_id = decoded_hash.split(':')

                        vpn_info = await manager.get_vpn_info(int(user_id_from_hash), client_id)
                        vpn_name = vpn_info['vpn_name'] if vpn_info['found'] else "Unknown VPN"
                    except:
                        vpn_name = "VPN Service"

                    # Показываем страницу с авто-редиректом
                    deep_link = f"v2raytun://import-sub?uri={urllib.parse.quote(url)}"
                    html_content = CONNECT_HTML.replace("{{ app_url }}", deep_link)
                    html_content = html_content.replace("{{ vpn_name }}", vpn_name)
                    html_content = html_content.replace("{{ server_address }}", manager.domain)

                    return HTMLResponse(content=html_content)

        # Если URL не распознан, делаем простой редирект
        return RedirectResponse(url=url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redirect error: {str(e)}")


@router.get("/web/{user_hash}/{user_id}")
async def web_subscription_page(
        user_hash: str,
        user_id: int,
        request: Request
):
    """
    Веб-страница для подписки (альтернатива /connect)
    """
    try:
        manager: AsyncVPNManager = request.app.state.manager
        decoded_hash = base64.urlsafe_b64decode(user_hash + '==').decode()
        user_id_from_hash, client_id = decoded_hash.split(':')

        if int(user_id_from_hash) != int(user_id):
            raise HTTPException(status_code=404, detail="Invalid subscription")

        vpn_info = await manager.get_vpn_info(int(user_id), client_id)

        if not vpn_info['found']:
            raise HTTPException(status_code=404, detail="VPN not found")

        # Генерируем ссылки
        subscription_url = f"https://{manager.domain}/sub/{user_hash}/{user_id}"
        deep_link = f"v2raytun://import-sub?uri={urllib.parse.quote(subscription_url)}"
        connect_url = f"https://{manager.domain}/connect?url={urllib.parse.quote(deep_link)}"

        # Показываем страницу с авто-редиректом
        html_content = CONNECT_HTML.replace("{{ app_url }}", deep_link)
        html_content = html_content.replace("{{ vpn_name }}", vpn_info['vpn_name'])
        html_content = html_content.replace("{{ server_address }}", manager.domain)

        return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")


def generate_v2ray_config(client_id: str, vpn_info: dict, user_id: int) -> dict:
    """Генерирует конфиг в формате V2ray"""
    return {
        "v": "2",
        "ps": f"{vpn_info['vpn_name']} - {user_id}",
        "add": config.site.domain,
        "port": "443",
        "id": client_id,
        "aid": "0",
        "scy": "auto",
        "net": "ws",
        "type": "none",
        "host": config.site.domain,
        "path": "/vpn",
        "tls": "tls",
        "sni": config.site.domain,
        "alpn": "h2,http/1.1",
        "fp": "chrome"
    }


def is_safe_url(url: str) -> bool:
    """Проверяет что URL безопасен для редиректа"""
    allowed_schemes = ['v2raytun://', 'https://', 'http://']
    return any(url.startswith(scheme) for scheme in allowed_schemes)