import datetime

from aiogram.types import CallbackQuery, User, Message
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput

from database.action_data_class import DataInteraction
from config_data.config import load_config, Config
from states.state_groups import startSG, PaymentSG, VpnSG


config: Config = load_config()


async def start_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    user = await session.get_user(event_from_user.id)
    admin = False
    admins = [*config.bot.admin_ids]
    admins.extend([admin.user_id for admin in await session.get_admins()])
    if event_from_user.id in admins:
        admin = True
    text = (f'<b>👤 Профиль: {event_from_user.full_name}</b>\n\n<blockquote> - ID: '
            f'<code>{event_from_user.id}</code>\n - Подписок: {len(user.vpns) if user.vpns else 0}</blockquote>\n\n')
    retry = '🌐'
    if user.vpns:
        retry = '🔄Продлить'
    return {
        'text': text,
        'retry': retry,
        'vpn': user.vpns,
        'admin': admin
    }


async def buy_vpn_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    vpns = await session.get_user_vpns(event_from_user.id)
    buttons = []
    for vpn in vpns:
        remained = (vpn.expires_at - datetime.datetime.now()).days
        buttons.append(
            (f'🌐{vpn.name} ({remained}⌛️)', vpn.id)
        )
    return {
        'items': buttons
    }


async def buy_vpn_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    dialog_manager.dialog_data.clear()
    dialog_manager.dialog_data['vpn_id'] = int(item_id)
    await dialog_manager.switch_to(startSG.choose_rate)


async def choose_rate_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    if vpn_id:
        vpn = await session.get_vpn_by_id(vpn_id)
        text = (f'<b>📋 Выберите план продления:</b>\n\n⌛️ Текущая дата истечения подписки: '
                f'{vpn.expires_at.strftime("%d-%m-%Y %H:%M")}🌐')
    else:
        text = '🕘Выберите тарифный план для создания нового ключа:'
    return {
        'text': text
    }


async def rate_choose(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    months = int(clb.data.split('_')[0])
    if months == 1:
        price = 299
    elif months == 3:
        price = 699
    else:
        price = 1999
    data = {
        'price': price,
        'months': months
    }
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    if vpn_id:
        data['vpn_id'] = vpn_id
    await dialog_manager.start(PaymentSG.payment_type, data=data)


async def my_vpns_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    vpns = await session.get_user_vpns(event_from_user.id)
    buttons = []
    vpns_text = ''
    for vpn in vpns:
        vpns_text += f'<b>• {vpn.name}</b> (до {vpn.expires_at.strftime("%d.%m.%Y, %H:%M")})\n'
        buttons.append(
            (f'🔑{vpn.name}', f'{vpn.id}_switch')
        )
        buttons.append(
            (' - ✏️', f'{vpn.id}_rename')
        )
    return {
        'vpns': vpns_text,
        'items': buttons
    }


async def my_vpn_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    items = item_id.split('_')
    action = items[1]
    vpn_id = int(items[0])
    if action == 'rename':
        dialog_manager.dialog_data['vpn_id'] = vpn_id
        await dialog_manager.switch_to(startSG.get_vpn_name)
        return
    data = {
        'vpn_id': vpn_id
    }
    await dialog_manager.start(VpnSG.menu, data=data)


async def get_vpn_name(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    if len(text) > 10:
        await msg.answer('❗️Новое название для VPN должно быть не длинее 10 символов, пожалуйста попробуйте еще раз')
        return
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    await session.update_vpn_name(vpn_id, text)
    await msg.answer('✅VPN был успешно переименован')
    await dialog_manager.switch_to(startSG.my_vpns)


async def ref_menu_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    user = await session.get_user(event_from_user.id)
    text = (f'<b>👥 Ваша реферальная ссылка:</b>\n\n<code>https://t.me/VezdeLovit_bot?start={event_from_user.id}'
            f'</code>\n\n🤝 Приглашайте друзей и получайте 50%😳 с их каждого пополнения каждый месяц! \n\n'
            f'<b>📊 Статистика приглашений:</b>\n👥 Всего приглашено: <b>{user.refs}</b> человек\n'
            f'💰Всего заработано: <b>{user.earn}₽</b>')
    url = f'http://t.me/share/url?url=https://t.me/VezdeLovit_bot?start={event_from_user.id}'
    return {
        'text': text,
        'url': url,
        'earn': bool(user.earn)
    }


async def get_derive_amount(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    try:
        amount = int(text)
    except Exception:
        await msg.delete()
        await msg.answer('❗️Сумма для вывода должна быть числом, пожалуйста попробуйте снова')
        return
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    user = await session.get_user(msg.from_user.id)
    if amount > user.earn:
        await msg.answer('❗️Сумма для вывода должна быть не больше той что сейчас у вас')
        return
    username = msg.from_user.username
    if not username:
        await msg.answer(text='❗️Чтобы пользоваться выводом средств, пожалуйста поставьте на свой аккаунт юзернейм')
        return
    text = (f'<b>Заявка на вывод средств</b>\n\nДанные о пользователе:\n'
            f'- Никнейм: {user.name}\n - Username: @{user.username}'
            f'\n - Telegram Id: {msg.from_user.id}\n - Рефералы: {user.refs}'
            f'\n - Общий баланс: {user.earn}️₽\n - <b>Сумма для вывода</b>: {amount}₽')
    admin_id = config.bot.admin_ids[1]
    await msg.bot.send_message(
        chat_id=admin_id,
        text=text
    )
    await session.update_user_earn(msg.from_user.id, -amount)
    await msg.answer('✅Заявка на вывод средств была успешно отправлена')
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.ref_menu)

