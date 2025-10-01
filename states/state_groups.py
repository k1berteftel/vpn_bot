from aiogram.fsm.state import State, StatesGroup

# Обычная группа состояний


class startSG(StatesGroup):
    start = State()

    buy_vpn = State()
    choose_rate = State()

    my_vpns = State()
    get_vpn_name = State()

    ref_menu = State()
    get_derive_amount = State()


class VpnSG(StatesGroup):
    menu = State()

    connect_menu = State()

    del_confirm = State()


class PaymentSG(StatesGroup):
    payment_type = State()
    process_payment = State()


class adminSG(StatesGroup):
    start = State()
    get_mail = State()
    get_time = State()
    get_keyboard = State()
    confirm_mail = State()
    deeplink_menu = State()
    deeplink_del = State()
    admin_menu = State()
    admin_del = State()
    admin_add = State()
