import asyncio
import aiohttp
import json
import logging
import uuid
import base64
from typing import List, Dict, Optional

from config_data.config import Config, load_config

logger = logging.getLogger(__name__)

config: Config = load_config()


class AsyncVPNManager:
    def __init__(self):
        self.panel_url = f"https://{config.site.domain}:2053/panel/api".rstrip('/')
        self.username = config.site.username
        self.password = config.site.password
        self.domain = config.site.domain
        self.cookies = None

    async def login(self) -> bool:
        """Асинхронная аутентификация в 3x-ui"""
        try:
            async with aiohttp.ClientSession() as session:
                login_data = {
                    "username": self.username,
                    "password": self.password
                }

                async with session.post(
                        f"https://{self.domain}:2053/login",
                        data=login_data,
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                ) as response:
                    if response.status == 200:
                        self.cookies = response.cookies
                        logger.info("✅ Успешный вход в 3x-ui")
                        return True
                    else:
                        logger.error(f"❌ Ошибка входа: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            return False

    async def get_or_create_main_inbound(self) -> int:
        """
        Находит или создает основной inbound на порту 443
        Возвращает ID inbound
        """
        if not self.cookies:
            if not await self.login():
                raise Exception("Не удалось авторизоваться в 3x-ui")

        try:
            async with aiohttp.ClientSession(cookies=self.cookies) as session:
                async with session.get(
                        f"{self.panel_url}/inbounds/list",
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                ) as response:

                    if response.status == 200:
                        result = await response.json()
                        inbounds = result.get('obj', [])

                        # Ищем inbound на порту 443
                        for inbound in inbounds:
                            if inbound.get('port') == 443 and "MAIN_VPN" in inbound.get('remark', ''):
                                logger.info(f"✅ Найден основной inbound: {inbound.get('id')}")
                                return inbound.get('id')

                        # Если не нашли - создаем новый
                        return await self._create_main_inbound()
                    else:
                        raise Exception("Не удалось получить список inbounds")

        except Exception as e:
            logger.error(f"❌ Ошибка поиска основного inbound: {e}")
            raise

    async def _create_main_inbound(self) -> int:
        """Создает основной inbound на порту 443"""
        inbound_data = {
            "up": 0,
            "down": 0,
            "total": 0,
            "remark": "MAIN_VPN_INBOUND",
            "enable": True,
            "expiryTime": 0,
            "listen": "",
            "port": 62789,
            "protocol": "vless",
            "settings": json.dumps({
                "clients": [],
                "decryption": "none",
                "fallbacks": []
            }),
            "streamSettings": json.dumps({
                "network": "ws",
                "security": "tls",
                "tlsSettings": {
                    "serverName": self.domain,
                    "certificates": [{
                        "certificateFile": "/root/cert/cert.crt",
                        "keyFile": "/root/cert/private.key"
                    }],
                    "alpn": ["h2", "http/1.1"]
                },
                "wsSettings": {
                    "path": "/vpn",
                    "headers": {
                        "Host": self.domain
                    }
                }
            }),
            "sniffing": json.dumps({
                "enabled": True,
                "destOverride": ["http", "tls", "quic"]
            })
        }

        async with aiohttp.ClientSession(cookies=self.cookies) as session:
            async with session.post(
                    f"{self.panel_url}/inbounds/add",
                    data=inbound_data,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=False
            ) as response:

                result = await response.json()
                if result.get('success'):
                    inbound_id = result.get('obj', {}).get('id')
                    logger.info(f"✅ Создан основной inbound: {inbound_id}")
                    return inbound_id
                else:
                    error_msg = result.get('msg', 'Unknown error')
                    raise Exception(f"Ошибка создания основного inbound: {error_msg}")

    async def create_vpn_for_user(self, user_id: int, vpn_name: str = None) -> dict:
        """
        Создает VPN для пользователя добавляя его в основной inbound

        Args:
            user_id: ID пользователя
            vpn_name: Название VPN (для идентификации)
        """
        if not self.cookies:
            if not await self.login():
                raise Exception("Не удалось авторизоваться в 3x-ui")

        # Получаем ID основного inbound
        inbound_id = await self.get_or_create_main_inbound()

        # Генерируем уникальные параметры
        client_id = str(uuid.uuid4())
        vpn_name = vpn_name or f"VPN_{user_id}"
        user_email = f"user{user_id}_{client_id[:8]}@{self.domain}"

        # Получаем текущие настройки inbound
        inbound_config = await self._get_inbound_config(inbound_id)

        # Добавляем нового клиента
        clients = inbound_config.get('clients', [])
        clients.append({
            "id": client_id,
            "flow": "xtls-rprx-vision",
            "email": user_email,
            "limitIp": 3,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "tgId": str(user_id),  # Сохраняем user_id для идентификации
            "vpnName": vpn_name  # Сохраняем название VPN
        })

        # Обновляем inbound
        update_data = {
            "up": 0,
            "down": 0,
            "total": 0,
            "remark": "MAIN_VPN_INBOUND",
            "enable": True,
            "expiryTime": 0,
            "listen": "",
            "port": 62789,
            "protocol": "vless",
            "settings": json.dumps({
                "clients": clients,
                "decryption": "none",
                "fallbacks": []
            }),
            "streamSettings": json.dumps(inbound_config.get('streamSettings', {})),
            "sniffing": json.dumps(inbound_config.get('sniffing', {}))
        }

        try:
            async with aiohttp.ClientSession(cookies=self.cookies) as session:
                async with session.post(
                        f"{self.panel_url}/inbounds/update/{inbound_id}",
                        data=update_data,
                        timeout=aiohttp.ClientTimeout(total=30),
                        ssl=False
                ) as response:

                    result_text = await response.text()

                    if response.status == 200:
                        # Генерируем ссылки
                        subscription_url = self._generate_subscription_url(user_id, client_id)
                        deep_link = self.generate_deep_link(subscription_url)

                        logger.info(f"✅ VPN '{vpn_name}' для пользователя {user_id} создан")

                        return {
                            "success": True,
                            "subscription_url": subscription_url,
                            "deep_link": deep_link,
                            "user_id": user_id,
                            "client_id": client_id,
                            "vpn_name": vpn_name,
                            "inbound_id": inbound_id
                        }
                    else:
                        raise Exception(f"Ошибка обновления inbound: {result_text}")

        except Exception as e:
            logger.error(f"❌ Ошибка при создании VPN: {e}")
            raise

    def _generate_subscription_url(self, user_id: int, client_id: str) -> str:
        """
        Генерирует URL подписки используя и user_id и client_id
        """
        unique_data = f"{user_id}:{client_id}"
        unique_hash = base64.urlsafe_b64encode(unique_data.encode()).decode().rstrip('=')

        return f"https://{self.domain}/sub/{unique_hash}/{user_id}"

    def generate_deep_link(self, subscription_url: str) -> str:
        """Генерирует deep link для автоматического подключения"""
        return f"v2raytun://import-sub?url={subscription_url}"

    async def delete_vpn(self, user_id: int, client_id: str) -> bool:
        """
        УДАЛЯЕТ конкретный VPN сервер пользователя по client_id
        """
        if not self.cookies:
            if not await self.login():
                raise Exception("Не удалось авторизоваться в 3x-ui")

        try:
            # Получаем ID основного inbound
            inbound_id = await self.get_or_create_main_inbound()

            # Получаем текущую конфигурацию
            inbound_config = await self._get_inbound_config(inbound_id)
            clients = inbound_config.get('clients', [])

            # Находим VPN для удаления
            vpn_to_delete = None
            for client in clients:
                if client.get('id') == client_id and client.get('tgId') == str(user_id):
                    vpn_to_delete = client
                    break

            if not vpn_to_delete:
                logger.warning(f"⚠️ VPN с client_id {client_id} для пользователя {user_id} не найден")
                return False

            # Удаляем клиента из списка
            clients = [client for client in clients if client.get('id') != client_id]

            # Обновляем inbound
            update_data = {
                "up": 0,
                "down": 0,
                "total": 0,
                "remark": "MAIN_VPN_INBOUND",
                "enable": True,
                "expiryTime": 0,
                "listen": "",
                "port": 62789,
                "protocol": "vless",
                "settings": json.dumps({
                    "clients": clients,
                    "decryption": "none",
                    "fallbacks": []
                }),
                "streamSettings": json.dumps(inbound_config.get('streamSettings', {})),
                "sniffing": json.dumps(inbound_config.get('sniffing', {}))
            }

            async with aiohttp.ClientSession(cookies=self.cookies) as session:
                async with session.post(
                        f"{self.panel_url}/inbounds/update/{inbound_id}",
                        data=update_data,
                        timeout=aiohttp.ClientTimeout(total=30),
                        ssl=False
                ) as response:

                    if response.status == 200:
                        vpn_name = vpn_to_delete.get('vpnName', 'Unknown')
                        logger.info(f"✅ VPN '{vpn_name}' (client_id: {client_id}) пользователя {user_id} удален")
                        return True
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ошибка удаления: {error_text}")

        except Exception as e:
            logger.error(f"❌ Ошибка при удалении VPN: {e}")
            return False

    async def disable_vpn(self, user_id: int, client_id: str) -> bool:
        """
        ВРЕМЕННО ОТКЛЮЧАЕТ конкретный VPN сервер
        """
        return await self._toggle_vpn(user_id, client_id, enable=False)

    async def enable_vpn(self, user_id: int, client_id: str) -> bool:
        """
        ВКЛЮЧАЕТ отключенный VPN сервер
        """
        return await self._toggle_vpn(user_id, client_id, enable=True)

    async def _toggle_vpn(self, user_id: int, client_id: str, enable: bool = True) -> bool:
        """Включает/выключает конкретный VPN"""
        if not self.cookies:
            if not await self.login():
                raise Exception("Не удалось авторизоваться в 3x-ui")

        try:
            # Получаем ID основного inbound
            inbound_id = await self.get_or_create_main_inbound()

            # Получаем текущую конфигурацию
            inbound_config = await self._get_inbound_config(inbound_id)
            clients = inbound_config.get('clients', [])

            # Находим и обновляем конкретный VPN
            vpn_name = 'Unknown'
            vpn_found = False
            for client in clients:
                if client.get('id') == client_id and client.get('tgId') == str(user_id):
                    client['enable'] = enable
                    vpn_found = True
                    vpn_name = client.get('vpnName', 'Unknown')
                    break

            if not vpn_found:
                logger.warning(f"⚠️ VPN с client_id {client_id} для пользователя {user_id} не найден")
                return False

            # Обновляем inbound
            update_data = {
                "up": 0,
                "down": 0,
                "total": 0,
                "remark": "MAIN_VPN_INBOUND",
                "enable": True,
                "expiryTime": 0,
                "listen": "",
                "port": 62789,
                "protocol": "vless",
                "settings": json.dumps({
                    "clients": clients,
                    "decryption": "none",
                    "fallbacks": []
                }),
                "streamSettings": json.dumps(inbound_config.get('streamSettings', {})),
                "sniffing": json.dumps(inbound_config.get('sniffing', {}))
            }

            async with aiohttp.ClientSession(cookies=self.cookies) as session:
                async with session.post(
                        f"{self.panel_url}/inbounds/update/{inbound_id}",
                        data=update_data,
                        timeout=aiohttp.ClientTimeout(total=30),
                        ssl=False
                ) as response:

                    if response.status == 200:
                        action = "включен" if enable else "отключен"
                        logger.info(f"✅ VPN '{vpn_name}' пользователя {user_id} {action}")
                        return True
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ошибка переключения: {error_text}")

        except Exception as e:
            logger.error(f"❌ Ошибка при переключении VPN: {e}")
            return False

    async def get_user_vpns(self, user_id: int) -> List[Dict]:
        """
        Возвращает ВСЕ VPN серверы пользователя
        Ищет по полю tgId в настройках клиента
        """
        if not self.cookies:
            if not await self.login():
                raise Exception("Не удалось авторизоваться в 3x-ui")

        try:
            # Получаем ID основного inbound
            inbound_id = await self.get_or_create_main_inbound()

            # Получаем текущую конфигурацию
            inbound_config = await self._get_inbound_config(inbound_id)
            clients = inbound_config.get('clients', [])

            # Фильтруем клиентов по user_id (из поля tgId)
            user_vpns = []

            for client in clients:
                if client.get('tgId') == str(user_id):
                    user_vpns.append({
                        'client_id': client.get('id'),
                        'vpn_name': client.get('vpnName', 'Unnamed'),
                        'email': client.get('email', ''),
                        'enable': client.get('enable', True),
                        'totalGB': client.get('totalGB', 0),
                        'expiryTime': client.get('expiryTime', 0),
                        'inbound_id': inbound_id
                    })

            return user_vpns

        except Exception as e:
            logger.error(f"❌ Ошибка при получении VPN пользователя: {e}")
            return []

    async def get_vpn_info(self, user_id: int, client_id: str) -> Dict:
        """
        Возвращает информацию о конкретном VPN сервере
        """
        user_vpns = await self.get_user_vpns(user_id)

        for vpn in user_vpns:
            if vpn['client_id'] == client_id:
                return {
                    'found': True,
                    'vpn_name': vpn['vpn_name'],
                    'enabled': vpn['enable'],
                    'client_id': vpn['client_id'],
                    'totalGB': vpn['totalGB'],
                    'expiryTime': vpn['expiryTime']
                }

        return {'found': False}

    async def _get_inbound_config(self, inbound_id: int) -> dict:
        """Получает конфигурацию inbound"""
        async with aiohttp.ClientSession(cookies=self.cookies) as session:
            async with session.get(
                    f"{self.panel_url}/inbounds/get/{inbound_id}",
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=False
            ) as response:

                result = await response.json()
                if result.get('success'):
                    inbound_data = result.get('obj', {})
                    settings_str = inbound_data.get('settings', '{}')
                    stream_settings_str = inbound_data.get('streamSettings', '{}')
                    sniffing_str = inbound_data.get('sniffing', '{}')

                    return {
                        'clients': json.loads(settings_str).get('clients', []),
                        'streamSettings': json.loads(stream_settings_str),
                        'sniffing': json.loads(sniffing_str)
                    }
                else:
                    raise Exception("Не удалось получить конфиг inbound")


# Пример использования в Telegram боте
async def example_usage():
    vpn_manager = AsyncVPNManager()
    user_id = 8005178596

    # Создаем несколько VPN для пользователя
    vpn1 = await vpn_manager.create_vpn_for_user(user_id, "Основной VPN")
    vpn2 = await vpn_manager.create_vpn_for_user(user_id, "Для работы")
    vpn3 = await vpn_manager.create_vpn_for_user(user_id, "Резервный")

    print("✅ Создано 3 VPN сервера")

    # Получаем все VPN пользователя
    user_vpns = await vpn_manager.get_user_vpns(user_id)
    print(f"📊 У пользователя {len(user_vpns)} VPN:")

    for vpn in user_vpns:
        print(f"  - {vpn['vpn_name']} ({vpn['client_id'][:8]}...) - {'✅ Вкл' if vpn['enable'] else '❌ Выкл'}")

    # Отключаем второй VPN
    await vpn_manager.disable_vpn(user_id, vpn2['client_id'])

    # Удаляем третий VPN
    await vpn_manager.delete_vpn(user_id, vpn3['client_id'])

    # Проверяем оставшиеся VPN
    final_vpns = await vpn_manager.get_user_vpns(user_id)
    print(f"📊 Осталось {len(final_vpns)} VPN:")

    for vpn in final_vpns:
        print(f"  - {vpn['vpn_name']} - {'✅ Вкл' if vpn['enable'] else '❌ Выкл'}")


if __name__ == "__main__":
    asyncio.run(example_usage())