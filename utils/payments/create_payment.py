import uuid
import asyncio
from aiohttp import ClientSession

from yookassa import Payment, Configuration, Payout
from yookassa.payment import PaymentResponse

from config_data.config import Config, load_config


config: Config = load_config()


Configuration.account_id = config.yookassa.account_id
Configuration.secret_key = config.yookassa.secret_key


async def _get_usdt_rub() -> float:
    url = 'https://open.er-api.com/v6/latest/USD'
    async with ClientSession() as session:
        async with session.get(url, ssl=False) as res:
            data = await res.json()
            rub = data['rates']['RUB']
    return float(rub)


async def get_yookassa_url(amount: int, description: str):
    payment = await Payment.create({
        "amount": {
            "value": str(amount) + '.00',
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/VezdeLovit_bot"
        },
        "receipt": {
            "customer": {
                "email": "kkulis985@gmail.com"
            },
            'items': [
                {
                    'description': description,
                    "amount": {
                        "value": str(amount) + '.00',
                        "currency": "RUB"
                    },
                    'measure': 'another',
                    'vat_code': 1,
                    'quantity': 1,
                    'payment_subject': 'payment',
                    'payment_mode': 'full_payment'
                }
            ]
        },
        "capture": True,
        "description": description
    }, uuid.uuid4())
    url = payment.confirmation.confirmation_url
    return {
        'url': url,
        'id': payment.id
    }


async def get_oxa_payment_data(amount: int | float):
    usdt_rub = await _get_usdt_rub()
    amount = round(amount / (usdt_rub), 2)
    url = 'https://api.oxapay.com/v1/payment/invoice'
    headers = {
        'merchant_api_key': config.oxapay.api_key,
        'Content-Type': 'application/json'
    }
    data = {
        'amount': float(amount),
        'mixed_payment': False
    }
    async with ClientSession() as session:
        async with session.post(url, json=data, headers=headers, ssl=False) as resp:
            if resp.status != 200:
                print(await resp.json())
                print(resp.status)
            data = await resp.json()
            print(data)
            print(type(data['status']), data['status'])
            if data['status'] == 429:
                print('status', data['status'])
                return await get_oxa_payment_data(amount)
    return {
        'url': data['data']['payment_url'],
        'id': data['data']['track_id']
    }


async def check_oxa_payment(track_id: str, counter: int = 1) -> bool:
    url = 'https://api.oxapay.com/v1/payment/' + track_id
    headers = {
        'merchant_api_key': config.oxapay.api_key,
        'Content-Type': 'application/json'
    }
    async with ClientSession() as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            if resp.status != 200:
                print('oxa check error', await resp.json())
                return False
            try:
                data = await resp.json()
            except Exception:
                if counter >= 5:
                    return False
                return await check_oxa_payment(track_id, counter+1)
    if data['data']['status'] == 'paid':
        return True
    return False


async def check_yookassa_payment(payment_id):
    payment: PaymentResponse = await Payment.find_one(payment_id)
    if payment.paid:
        return True
    return False