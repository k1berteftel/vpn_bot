from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import SwitchTo, Column, Row, Button, Group, Select, Start, Url
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.media import DynamicMedia

from dialogs.user_dialog import getters

from states.state_groups import startSG, adminSG

user_dialog = Dialog(
    Window(
        Format('{text}'),
        Column(
            SwitchTo(Format('Купить VPN{retry}'), id='buy_vpn_switcher', state=startSG.buy_vpn),
            SwitchTo(Const('🪐Мои VPN'), id='my_vpn_switcher', state=startSG.my_vpns, when='vpn'),
            SwitchTo(Const('💰Реферальная программа'), id='ref_program', state=startSG.ref_menu),
            Start(Const('Админ панель'), id='admin', state=adminSG.start, when='admin')
        ),
        getter=getters.start_getter,
        state=startSG.start
    ),
    Window(
        Const('Выберите подписку для продления или купите новую'),
        Group(
            Select(
                Format('{item[0]}'),
                id='buy_vpn_builder',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=getters.buy_vpn_selector
            ),
            Start(Const('➕Добавить новый VPN'), id='choose_rate_switcher', state=startSG.choose_rate),
            width=1
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.buy_vpn_getter,
        state=startSG.buy_vpn
    ),
    Window(
        Format('{text}'),
        Column(
            Button(Const('📅1 месяц - 299₽'), id='1_month_choose', on_click=getters.rate_choose),
            Button(Const('📅3 месяца - 699₽'), id='3_month_choose', on_click=getters.rate_choose),
            Button(Const('📅12 месяцев - 1999₽'), id='12_month_choose', on_click=getters.rate_choose),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_buy_vpn', state=startSG.buy_vpn),
        getter=getters.choose_rate_getter,
        state=startSG.choose_rate
    ),
    Window(
        Const('<b>🌐Список ваших VPN серверов</b>:\n\n'),
        Format('<blockquote>{vpns}</blockquote>\n'),
        Const('<em>Нажмите на ✏️, чтобы переименовать подписку.</em>'),
        Group(
            Select(
                Format('{item[0]}'),
                id='my_vpns_builder',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=getters.my_vpn_selector
            ),
            width=2
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.my_vpns_getter,
        state=startSG.my_vpns
    ),
    Window(
        Const('✏️ Введите новое имя вашего VPN (до 10 символов):'),
        TextInput(
            id='get_vpn_name',
            on_success=getters.get_vpn_name
        ),
        SwitchTo(Const('⬅️Назад'), id='back_my_vpns', state=startSG.my_vpns),
        state=startSG.get_vpn_name
    ),
    Window(
        Format('{text}'),
        Column(
            Url(Const('👥Пригласить'), id='share_url', url=Format('{url}')),
        ),
        SwitchTo(Const('Вывод'), id='get_derive_amount', state=startSG.get_derive_amount, when='earn'),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.ref_menu_getter,
        state=startSG.ref_menu
    ),
    Window(
        Const('Введите сумму для вывода <em>(в рублях)</em>'),
        TextInput(
            id='get_derive_amount',
            on_success=getters.get_derive_amount
        ),
        SwitchTo(Const('⬅️Назад'), id='back_ref_menu', state=startSG.ref_menu),
        state=startSG.get_derive_amount
    ),
)