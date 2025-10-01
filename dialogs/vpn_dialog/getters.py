import datetime

from aiogram.types import CallbackQuery, User, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput

from services.vpn.manager import AsyncVPNManager
from database.action_data_class import DataInteraction
from config_data.config import load_config, Config
from states.state_groups import startSG, PaymentSG, VpnSG


config: Config = load_config()


async def menu_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    if dialog_manager.start_data:
        dialog_manager.dialog_data.update(dialog_manager.start_data)
        dialog_manager.start_data.clear()
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    vpn = await session.get_vpn_by_id(vpn_id)
    text = (f'<b>{vpn.name}:</b>\n\n<code>{vpn.link}</code>\n\n<b>📅 Статус подписки:</b>\n<blockquote>'
            f'⏳ Осталось: <b>{(vpn.expires_at - datetime.datetime.now()).days}</b></blockquote>\n'
            f'🛑 Истекает: {vpn.expires_at.strftime("%d-%m-%Y %H:%M")}')
    return {'text': text}


async def close_dialog(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    await clb.message.delete()
    if dialog_manager.has_context():
        await dialog_manager.done()
        try:
            await clb.bot.delete_message(chat_id=clb.from_user.id, message_id=clb.message.message_id - 1)
        except Exception:
            ...
        counter = 1
        while dialog_manager.has_context():
            await dialog_manager.done()
            try:
                await clb.bot.delete_message(chat_id=clb.from_user.id, message_id=clb.message.message_id + counter)
            except Exception:
                ...
            counter += 1
    await dialog_manager.start(startSG.start)


async def connect_menu_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    manager: AsyncVPNManager = dialog_manager.middleware_data.get('vpn_manager')
    vpn = await session.get_vpn_by_id(vpn_id)
    url = manager.generate_deep_link(vpn.link)
    text = (f'<b>📋Ваша ссылка:</b>\n\n<code>{vpn.link}</code>\n\n<b>1️⃣Установите приложение для вашего устройства:</b>\n<blockquote>'
            f'Ссылка: https://v2raytun.art/?yclid=13922034514585714687</blockquote>\n\n'
            f'<b>2️⃣Авто-импорт</b>\n<blockquote>\nНажмите на кнопку "📡Подключить" ниже'
            f'</blockquote>\n\n'
            f'<b>3️⃣Включите VPN</b>\n\n✅ Готово! Приложение само всё настроит.')
    return {
        'text': text,
        'url': f'https://{config.site.domain}//connect?url={url}'
    }


async def del_vpn(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    manager: AsyncVPNManager = dialog_manager.middleware_data.get('vpn_manager')
    vpn = await session.get_vpn_by_id(vpn_id)
    status = await manager.delete_vpn(clb.from_user.id, vpn.client_id)
    if not status:
        await clb.answer('Во время удаления что-то пошло не так, пожалуйста обратитесь в поддержку')
        return
    await session.del_user_vpn(vpn_id)
    await clb.answer(f'{vpn.name} был успешно удален, возвращаюсь в главное меню...')
    await clb.message.delete()
    if dialog_manager.has_context():
        await dialog_manager.done()
        try:
            await clb.bot.delete_message(chat_id=clb.from_user.id, message_id=clb.message.message_id - 1)
        except Exception:
            ...
        counter = 1
        while dialog_manager.has_context():
            await dialog_manager.done()
            try:
                await clb.bot.delete_message(chat_id=clb.from_user.id, message_id=clb.message.message_id + counter)
            except Exception:
                ...
            counter += 1
    await dialog_manager.start(startSG.start)