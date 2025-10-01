import datetime
import random
from typing import Literal
import asyncio
from asyncio import TimeoutError
from dateutil.relativedelta import relativedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from nats.js import JetStreamContext

from services.vpn.manager import AsyncVPNManager
from utils.payments.create_payment import check_yookassa_payment, check_oxa_payment
from utils.schedulers import check_vpns_sub
from database.action_data_class import DataInteraction
from config_data.config import Config, load_config


config: Config = load_config()


async def wait_for_payment(
        payment_id,
        months: int,
        user_id: int,
        bot: Bot,
        session: DataInteraction,
        scheduler: AsyncIOScheduler,
        manager: AsyncVPNManager,
        currency: int,
        payment_type: Literal['crypto', 'card'],
        vpn_id: int | None,
        timeout: int = 60 * 15,
        check_interval: int = 6
):
    """
    Ожидает оплаты в фоне. Завершается при оплате или по таймауту.
    """
    try:
        await asyncio.wait_for(_poll_payment(payment_id, months, user_id, currency, bot, session, scheduler,
                                             manager, payment_type, vpn_id, check_interval),
                               timeout=timeout)

    except TimeoutError:
        print(f"Платёж {payment_id} истёк (таймаут)")

    except Exception as e:
        print(f"Ошибка в фоновом ожидании платежа {payment_id}: {e}")


async def _poll_payment(payment_id, months: int, user_id: int, currency: int, bot: Bot, session: DataInteraction,
                        scheduler: AsyncIOScheduler, manager: AsyncVPNManager, payment_type: str, vpn_id: int | None, interval: int):
    """
    Цикл опроса статуса платежа.
    Завершается, когда платёж оплачен.
    """
    while True:
        """
        if payment_type == 'card':
            status = await check_yookassa_payment(payment_id)
        else:
            status = await check_oxa_payment(payment_id)
        if status:
            await bot.send_message(
                chat_id=user_id,
                text='✅Оплата прошла успешно'
            )
        """
        await execute_rate(user_id, months, vpn_id, bot, currency, session, scheduler, manager)
        break
        await asyncio.sleep(interval)


async def execute_rate(user_id: int, months: int, vpn_id: int | None, bot: Bot, currency: int,
                       session: DataInteraction, scheduler: AsyncIOScheduler, manager: AsyncVPNManager):
    user = await session.get_user(user_id)
    if vpn_id:
        await session.update_vpn_sub(vpn_id, months)
        vpn = await session.get_vpn_by_id(vpn_id)
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f'<b>✅<em>`{vpn.name}`</em> был успешно продлен</b>\nВернитесь в главное '
                     f'меню чтобы продолжить им пользоваться'
            )
        except Exception:
            await session.set_active(user_id, 0)
    else:
        await manager.login()
        new_vpn = await manager.create_vpn_for_user(user_id)
        if new_vpn and new_vpn['success']:
            client_id = new_vpn["client_id"]
            link = new_vpn['subscription_url']
            vpn_name = new_vpn['vpn_name']
            await session.add_vpn(
                user_id=user_id,
                client_id=client_id,
                link=link,
                name=vpn_name,
                expires_at=datetime.datetime.now() + relativedelta(months=months)
            )
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f'<b>✅<em>`{vpn_name}`</em> был успешно арендован</b>\nВернитесь в главное '
                         f'меню чтобы начать им пользоваться'
                )
            except Exception:
                await session.set_active(user_id, 0)
            job_id = f'check_sub_{user_id}'
            job = scheduler.get_job(job_id)
            if not job:
                scheduler.add_job(
                    check_vpns_sub,
                    'interval',
                    args=[bot, user_id, session, manager, scheduler, job_id],
                    id=job_id,
                    days=1
                )
        else:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text='<b>⚠️Во время аренды VPN сервера произошла какая-то ошибка, пожалуйста обратитесь в поддержку</b>'
                )
            except Exception:
                await session.set_active(user_id, 0)
    if user.referral and user.entry > (datetime.datetime.now() - relativedelta(months=3)):
        earn = int(round(currency * 0.5))
        await session.update_user_earn(user.referral, earn)
