from dataclasses import dataclass

from environs import Env

'''
    При необходимости конфиг базы данных или других сторонних сервисов
'''


@dataclass
class tg_bot:
    token: str
    admin_ids: list[int]


@dataclass
class DB:
    dns: str


@dataclass
class NatsConfig:
    servers: list[str]


@dataclass
class Site:
    domain: str
    username: str
    password: str


@dataclass
class Yookassa:
    account_id: int
    secret_key: str


@dataclass
class OxaPay:
    api_key: str


@dataclass
class Config:
    bot: tg_bot
    db: DB
    nats: NatsConfig
    yookassa: Yookassa
    oxapay: OxaPay
    site: Site


def load_config(path: str | None = None) -> Config:
    env: Env = Env()
    env.read_env(path)

    return Config(
        bot=tg_bot(
            token=env('token'),
            admin_ids=list(map(int, env.list('admins')))
            ),
        db=DB(
            dns=env('dns')
        ),
        nats=NatsConfig(
            servers=env.list('nats')
        ),
        yookassa=Yookassa(
            account_id=int(env('account_id')),
            secret_key=env('secret_key')
        ),
        oxapay=OxaPay(
            api_key=env('oxa_api_key')
        ),
        site=Site(
            domain=env('domain'),
            username=env('username'),
            password=env('password')
        )
    )
