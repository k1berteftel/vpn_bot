import asyncio

from aiogram.types import CallbackQuery, User, Message, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.vpn.manager import AsyncVPNManager
from utils.payments.create_payment import get_yookassa_url, get_oxa_payment_data
from utils.payments.process_payment import wait_for_payment
from database.action_data_class import DataInteraction
from config_data.config import load_config, Config
from states.state_groups import startSG, PaymentSG


async def payment_choose(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    if dialog_manager.start_data:
        dialog_manager.dialog_data.update(dialog_manager.start_data)
        dialog_manager.start_data.clear()
    manager: AsyncVPNManager = dialog_manager.middleware_data.get('vpn_manager')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    scheduler: AsyncIOScheduler = dialog_manager.middleware_data.get('scheduler')
    price = dialog_manager.dialog_data.get('price')
    months = dialog_manager.dialog_data.get('months')
    vpn_id = dialog_manager.dialog_data.get('vpn_id')
    payment = clb.data.split('_')[0]
    if payment == 'card':
        payment = await get_yookassa_url(price, "Оплата подписки VPN")
        task = asyncio.create_task(
            wait_for_payment(
                payment_id=payment.get('id'),
                months=months,
                user_id=clb.from_user.id,
                bot=clb.bot,
                session=session,
                scheduler=scheduler,
                manager=manager,
                currency=price,
                payment_type='card',
                vpn_id=vpn_id
            )
        )
        for active_task in asyncio.all_tasks():
            if active_task.get_name() == f'process_payment_{clb.from_user.id}':
                active_task.cancel()
        task.set_name(f'process_payment_{clb.from_user.id}')
        dialog_manager.dialog_data['url'] = payment.get('url')
        await dialog_manager.switch_to(PaymentSG.process_payment)
        return
    elif payment == 'crypto':
        payment = await get_oxa_payment_data(price)
        task = asyncio.create_task(
            wait_for_payment(
                payment_id=payment.get('id'),
                months=months,
                user_id=clb.from_user.id,
                bot=clb.bot,
                session=session,
                scheduler=scheduler,
                manager=manager,
                currency=price,
                payment_type='crypto',
                vpn_id=vpn_id
            )
        )
        for active_task in asyncio.all_tasks():
            if active_task.get_name() == f'process_payment_{clb.from_user.id}':
                active_task.cancel()
        task.set_name(f'process_payment_{clb.from_user.id}')
        dialog_manager.dialog_data['url'] = payment.get('url')
        await dialog_manager.switch_to(PaymentSG.process_payment)
        return


async def process_payment_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    price = dialog_manager.dialog_data.get('price')
    url = dialog_manager.dialog_data.get('url')
    text = f'<blockquote> - Сумма к оплате: {price}₽</blockquote>'
    return {
        'text': text,
        'url': url
    }


async def close_payment(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    name = f'process_payment_{clb.from_user.id}'
    for task in asyncio.all_tasks():
        if task.get_name() == name:
            task.cancel()
    await dialog_manager.switch_to(PaymentSG.payment_type)

