from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import SwitchTo, Column, Row, Button, Group, Select, Start, Url, Cancel
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.media import DynamicMedia

from dialogs.vpn_dialog import getters

from states.state_groups import startSG, VpnSG


vpn_dialog = Dialog(
    Window(
        Format('{text}'),
        Column(
            SwitchTo(Const('📲Подключить устройство'), id='connect_menu_switcher', state=VpnSG.connect_menu),
            SwitchTo(Const('❌Удалить'), id='del_confirm_switcher', state=VpnSG.del_confirm),
        ),
        Cancel(Const('⬅️Назад'), id='close_dialog'),
        Button(Const('🏠На главное меню'), id='back_main', on_click=getters.close_dialog),
        getter=getters.menu_getter,
        state=VpnSG.menu
    ),
    Window(
        Format('{text}'),
        Column(
            Url(Const('📡Подключить'), id='connect_url', url=Format('{url}'))
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=VpnSG.menu),
        getter=getters.connect_menu_getter,
        state=VpnSG.connect_menu
    ),
    Window(
        Const('<b>Вы действительно хотите удалить данный VPN??</b>'),
        Const('<em>❗️После удаления средства не будут возвращены на баланс</em>'),
        Row(
            Button(Const('✅Подтвердить'), id='del_vpn', on_click=getters.del_vpn),
            SwitchTo(Const('❌Отмена'), id='back', state=VpnSG.menu)
        ),
        state=VpnSG.del_confirm
    ),
)