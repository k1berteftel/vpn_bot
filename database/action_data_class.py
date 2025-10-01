import datetime

from dateutil.relativedelta import relativedelta
from sqlalchemy import select, insert, update, column, text, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from database.model import (UsersTable, DeeplinksTable, OneTimeLinksIdsTable, AdminsTable, UserVpnTable)


class DataInteraction():
    def __init__(self, session: async_sessionmaker):
        self._sessions = session

    async def check_user(self, user_id: int) -> bool:
        async with self._sessions() as session:
            result = await session.scalar(select(UsersTable).where(UsersTable.user_id == user_id))
        return True if result else False

    async def add_user(self, user_id: int, username: str, name: str, referral: int | None = None):
        if await self.check_user(user_id):
            return
        async with self._sessions() as session:
            await session.execute(insert(UsersTable).values(
                user_id=user_id,
                username=username,
                name=name,
                referral=referral,
            ))
            await session.commit()

    async def add_refs(self, user_id: int):
        async with self._sessions() as session:
            await session.execute(update(UsersTable).where(UsersTable.user_id == user_id).values(
                refs=UsersTable.refs + 1
            ))
            await session.commit()

    async def add_vpn(self, user_id: int, client_id: str, name: str, link: str, expires_at: datetime.datetime):
        async with self._sessions() as session:
            await session.execute(insert(UserVpnTable).values(
                user_id=user_id,
                client_id=client_id,
                name=name,
                link=link,
                expires_at=expires_at
            ))
            await session.commit()

    async def add_entry(self, link: str):
        async with self._sessions() as session:
            await session.execute(update(DeeplinksTable).where(DeeplinksTable.link == link).values(
                entry=DeeplinksTable.entry+1
            ))
            await session.commit()

    async def add_deeplink(self, link: str):
        async with self._sessions() as session:
            await session.execute(insert(DeeplinksTable).values(
                link=link
            ))
            await session.commit()

    async def add_link(self, link: str):
        async with self._sessions() as session:
            await session.execute(insert(OneTimeLinksIdsTable).values(
                link=link
            ))
            await session.commit()

    async def add_admin(self, user_id: int, name: str):
        async with self._sessions() as session:
            await session.execute(insert(AdminsTable).values(
                user_id=user_id,
                name=name
            ))
            await session.commit()

    async def get_users(self):
        async with self._sessions() as session:
            result = await session.scalars(select(UsersTable))
        return result.fetchall()

    async def get_user(self, user_id: int):
        async with self._sessions() as session:
            result = await session.scalar(select(UsersTable).where(UsersTable.user_id == user_id))
        return result

    async def get_user_by_username(self, username: str):
        async with self._sessions() as session:
            result = await session.scalar(select(UsersTable).where(UsersTable.username == username))
        return result

    async def get_user_vpns(self, user_id: int):
        async with self._sessions() as session:
            result = await session.scalars(select(UserVpnTable).where(UserVpnTable.user_id == user_id))
        return result.fetchall()

    async def get_vpn_by_id(self, id: int):
        async with self._sessions() as session:
            result = await session.scalar(select(UserVpnTable).where(UserVpnTable.id == id))
        return result

    async def get_vpn_by_client_id(self, client_id: str):
        async with self._sessions() as session:
            result = await session.scalar(select(UserVpnTable).where(UserVpnTable.client_id == client_id))
        return result

    async def get_links(self):
        async with self._sessions() as session:
            result = await session.scalars(select(OneTimeLinksIdsTable))
        return result.fetchall()

    async def get_admins(self):
        async with self._sessions() as session:
            result = await session.scalars(select(AdminsTable))
        return result.fetchall()

    async def get_deeplinks(self):
        async with self._sessions() as session:
            result = await session.scalars(select(DeeplinksTable))
        return result.fetchall()

    async def update_vpn_sub(self, vpn_id: int, months: int):
        async with self._sessions() as session:
            await session.execute(update(UserVpnTable).where(UserVpnTable.id == vpn_id).values(
                expires_at=UserVpnTable.expires_at + relativedelta(months=months)
            ))
            await session.commit()

    async def update_vpn_name(self, vpn_id: int, name: str):
        async with self._sessions() as session:
            await session.execute(update(UserVpnTable).where(UserVpnTable.id == vpn_id).values(
                name=name
            ))
            await session.commit()

    async def update_user_earn(self, user_id: int, earn: int):
        async with self._sessions() as session:
            await session.execute(update(UsersTable).where(UsersTable.user_id == user_id).values(
                earn=UsersTable.earn + earn
            ))
            await session.commit()

    async def set_activity(self, user_id: int):
        async with self._sessions() as session:
            await session.execute(update(UsersTable).where(UsersTable.user_id == user_id).values(
                activity=datetime.datetime.today()
            ))
            await session.commit()

    async def set_active(self, user_id: int, active: int):
        async with self._sessions() as session:
            await session.execute(update(UsersTable).where(UsersTable.user_id == user_id).values(
                active=active
            ))
            await session.commit()

    async def del_user_vpn(self, vpn_id: int):
        async with self._sessions() as session:
            await session.execute(delete(UserVpnTable).where(UserVpnTable.id == vpn_id))
            await session.commit()

    async def del_deeplink(self, link: str):
        async with self._sessions() as session:
            await session.execute(delete(DeeplinksTable).where(DeeplinksTable.link == link))
            await session.commit()

    async def del_link(self, link_id: str):
        async with self._sessions() as session:
            await session.execute(delete(OneTimeLinksIdsTable).where(OneTimeLinksIdsTable.link == link_id))
            await session.commit()

    async def del_admin(self, user_id: int):
        async with self._sessions() as session:
            await session.execute(delete(AdminsTable).where(AdminsTable.user_id == user_id))
            await session.commit()