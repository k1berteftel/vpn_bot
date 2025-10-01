import asyncio
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, Message
from aiogram_dialog import DialogManager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from services.vpn.manager import AsyncVPNManager
from database.action_data_class import DataInteraction


async def send_messages(bot: Bot, session: DataInteraction, keyboard: InlineKeyboardMarkup|None, message: Message, **kwargs):
    users = await session.get_users()
    text = kwargs.get('text')
    caption = kwargs.get('caption')
    photo = kwargs.get('photo')
    video = kwargs.get('video')
    if text:
        for user in users:
            try:
                await bot.send_message(
                    chat_id=user.user_id,
                    text=text.format(name=user.name),
                    reply_markup=keyboard
                )
                if user.active == 0:
                    await session.set_active(user.user_id, 1)
            except Exception as err:
                print(err)
                await session.set_active(user.user_id, 0)
    elif caption:
        if photo:
            for user in users:
                try:
                    await bot.send_photo(
                        chat_id=user.user_id,
                        photo=photo,
                        caption=caption.format(name=user.name),
                        reply_markup=keyboard
                    )
                    if user.active == 0:
                        await session.set_active(user.user_id, 1)
                except Exception as err:
                    print(err)
                    await session.set_active(user.user_id, 0)
        else:
            for user in users:
                try:
                    await bot.send_video(
                        chat_id=user.user_id,
                        video=video,
                        caption=caption.format(name=user.name),
                        reply_markup=keyboard
                    )
                    if user.active == 0:
                        await session.set_active(user.user_id, 1)
                except Exception as err:
                    print(err)
                    await session.set_active(user.user_id, 0)


async def check_vpns_sub(bot: Bot, user_id: int, session: DataInteraction, manager: AsyncVPNManager,
                        scheduler: AsyncIOScheduler, job_id: str):
    """
    Доработать функцию в плане интерфейса и напоминалок, клавиатура для помощи в продлении подписки обработка ошибок и т.д
    """
    vpns = await session.get_user_vpns(user_id)
    if not vpns:
        job = scheduler.get_job(job_id)
        if job:
            job.remove()
        return
    for vpn in vpns:
        if not vpn.active:
            continue
        differ = (vpn.expires_at - datetime.now()).days
        if differ <= 0:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f'😔К сожалению срок вашей подписки на VPN <em>`{vpn.name}`</em> подошел к концу'
                )
            except Exception:
                await session.set_active(user_id, 0)
            await manager.login()
            status = await manager.delete_user_vpn(vpn.inbound_id)
            if not status:
                print('delete vpn error')
            await session.del_user_vpn(vpn.id)
            if not await session.get_user_vpns(user_id):
                job = scheduler.get_job(job_id)
                if job:
                    job.remove()
                return

