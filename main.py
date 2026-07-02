import asyncio
import logging
import sys
import os
import psutil
import time
import subprocess
import json
from aiogram.exceptions import TelegramNetworkError


import pyautogui

from pycaw.pycaw import AudioUtilities
from pycaw.pycaw import AudioUtilities

from aiogram.fsm.state import State, StatesGroup
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext

from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    FSInputFile

)


CONFIG_FILE = "kiryha_pc_control_config.json"
if not os.path.exists(CONFIG_FILE):
    user_token = input("Введи токен своего бота: ")
    user_id = int(input("Введи свой тг ID: "))
    data = {"token": user_token, "id": user_id}
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)
    if getattr(sys, 'frozen', False):
        subprocess.Popen([sys.executable],
                         creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        subprocess.Popen([sys.executable, __file__],
                         creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit()
with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

ADMIN_ID = int(config["id"])


def volume_chunks(target_volume):
    filled_chunks = round(target_volume * 15)
    not_filled_chunks = 15 - filled_chunks
    all_chunks = "▇" * filled_chunks + "░" * not_filled_chunks
    return all_chunks


def get_top_cpu_processes(limit=10):
    bad_processes = ['svchost'.lower(), 'System'.lower(),
                     'dwm'.lower(), 'explorer'.lower()]
    for proc in psutil.process_iter(['cpu_percent']):
        try:
            proc.info['cpu_percent']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(2)

    processes = []

    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            proc.info['cpu_percent']

            if not proc.info['name'] or proc.info['name'] == "System Idle Process" or proc.info['pid'] == 0 or any(bad in proc.info['name'].lower() for bad in bad_processes):
                continue

            processes.append({
                'pid': proc.info['pid'],
                'name': proc.info['name'],
                'cpu': proc.info['cpu_percent']
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda x: x['cpu'], reverse=True)
    return processes[:limit]


class VolumeCallback(CallbackData, prefix="volume"):
    action: str


class Form(StatesGroup):
    waiting_for_app = State()
    waiting_for_shutdown = State()
    waiting_for_process = State()


dp = Dispatcher()

start_button = [
    [types.KeyboardButton(text='🖥️ Меню')],
    [types.KeyboardButton(text='🆘 Помощь')]
]
start_kb = types.ReplyKeyboardMarkup(
    keyboard=start_button,
    resize_keyboard=True
)


volume_list = [
    [
        InlineKeyboardButton(text="🔊 Volume ⬅️",
                             callback_data=VolumeCallback(action="down").pack()),
        InlineKeyboardButton(text="🔊 Volume ➡️",
                             callback_data=VolumeCallback(action="up").pack())
    ],
    [InlineKeyboardButton(text="↩️ Назад", callback_data="menu")]
]

volume_kb = InlineKeyboardMarkup(inline_keyboard=volume_list)

inline_menu_list = [
    [
        InlineKeyboardButton(text="💤 Shutdown PC",
                             callback_data="pc_shutdown"),
        InlineKeyboardButton(text="🔄 Restart PC", callback_data="pc_restart")
    ],

    [
        InlineKeyboardButton(text="📸 PC screenshot",
                             callback_data="pc_screenshot"),
        InlineKeyboardButton(text="📂 Open app", callback_data="pc_open")
    ],

    [
        InlineKeyboardButton(text="🔊 Volume ⬅️",
                             callback_data=VolumeCallback(action="down").pack()),
        InlineKeyboardButton(text="🔊 Volume ➡️",
                             callback_data=VolumeCallback(action="up").pack())
    ],

    [
        InlineKeyboardButton(text="📊 PC info", callback_data="pc_info")
    ],
    [
        InlineKeyboardButton(text="⚙️ Процессы", callback_data="process")
    ]

]

menu_kb = InlineKeyboardMarkup(inline_keyboard=inline_menu_list)

menu_processes_kbord = [
    [
        InlineKeyboardButton(text="🛑 Убить процесс",
                             callback_data="kill_process"),
        InlineKeyboardButton(text="🔁 Перезапустить процессы",
                             callback_data="remake_process")
    ],
    [InlineKeyboardButton(text="↩️ Назад", callback_data="menu")]
]
menu_processes_kb = InlineKeyboardMarkup(
    inline_keyboard=menu_processes_kbord)


back_kbord = [[InlineKeyboardButton(text="↩️ Назад", callback_data="menu")]]
back_kb = InlineKeyboardMarkup(inline_keyboard=back_kbord)

back_kbord_screen = [[InlineKeyboardButton(
    text="↩️ Назад", callback_data="menu_for_screen")]]
back_kb_screen = InlineKeyboardMarkup(inline_keyboard=back_kbord_screen)

yes_of_kbord = [[InlineKeyboardButton(
    text="💤 ДА, выключить ПК", callback_data="yes_of")]]
yes_off_kb = InlineKeyboardMarkup(inline_keyboard=yes_of_kbord)

yes_restart_kbord = [[InlineKeyboardButton(
    text="🔄 ДА, перезагрузить ПК", callback_data="yes_restart")]]
yes_restart_kb = InlineKeyboardMarkup(inline_keyboard=yes_restart_kbord)


def find_and_run_app(name_app):
    name_app = name_app.lower()

    search_dir = [
        os.path.expanduser(r"~\AppData\Local"),
        os.path.expanduser(r"~\AppData\Roaming"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        os.path.expanduser(
            r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
        r"C:\Program Files",
        r"C:\Program Files (x86)",
    ]

    for direct in search_dir:
        for root, dirs, files in os.walk(direct, onerror=lambda e: None):
            for file in files:
                if name_app in file.lower() and file.lower().endswith('.exe'):
                    full_path = os.path.join(root, file)

                    subprocess.Popen(f'"{full_path}"', shell=True)
                    return True

                elif name_app in file.lower() and file.lower().endswith(".lnk"):
                    full_path = os.path.join(root, file)
                    subprocess.Popen(f'start "" "{full_path}"', shell=True)
                    return True

    return False


@dp.message(Command("start"))
async def start_message(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    await message.answer('<b>🖥️ Компьютер под контролем!</b>\n\nВыбирай действие:\n\n• <b>🔌 Shutdown/Restart PC:</b> Выключение и перезагрузка ПК\n\n• <b>📸 PC Screenshot:</b> Текущий снимок экрана\n\n• <b>📂 Open app:</b> Дистанционное открытие программ\n\n• <b>🔊 Valume:</b> Регулировка громкости системы\n\n• <b>📊 PC info:</b> Информация о ПК и топ процессов ЦП\n\n<b>Жду команду, нажмите на кнопку ниже 👇</b>', reply_markup=start_kb, parse_mode="HTML")


@dp.message(F.text == '🖥️ Меню')
async def menu_message(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return await message.answer("🔴 Отказано в доступе!")

    await message.answer("<b>🖥️ Компьютер под контролем!</b>\n\n<b>Жду твоих команд... 👇</b>", reply_markup=menu_kb, parse_mode="HTML")
    await state.clear()


@dp.message(F.text == '🆘 Помощь')
async def help_message(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("🔴 Отказано в доступе!")

    await message.answer('<b>🖥️ Компьютер под контролем!</b>\n\nВыбирай действие:\n\n• <b>🔌 Shutdown/Restart PC:</b> Выключение и перезагрузка ПК\n\n• <b>📸 PC Screenshot:</b> Текущий снимок экрана\n\n• <b>📂 Open app:</b> Дистанционное открытие программ\n\n• <b>🔊 Valume:</b> Регулировка громкости системы\n\n• <b>📊 PC info:</b> Информация о ПК и топ процессов ЦП\n\n<b>Жду твоих команд... 👇</b>', reply_markup=start_kb, parse_mode="HTML")


@dp.callback_query(F.data == "menu_for_screen")
async def back_menu_screen(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("🔴 Отказано в доступе!")

    await callback.message.delete()
    await callback.message.answer(
        text="ну какое то описание", reply_markup=menu_kb
    )


@dp.callback_query(F.data == "menu")
async def back_menu(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("🔴 Отказано в доступе!")

    await callback.message.edit_text(
        text="ну какое то описание", reply_markup=menu_kb
    )


@dp.callback_query(F.data == "pc_screenshot")
async def make_screenshot(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("🔴 Отказано в доступе!")

    await callback.answer()
    screen = "screenshot.png"
    pyautogui.screenshot(screen)

    photo = FSInputFile(screen)

    await callback.message.delete()
    await callback.message.answer_photo(photo=photo, caption="📸 Скрин экрана", reply_markup=back_kb_screen)
    os.remove(screen)


@dp.callback_query(VolumeCallback.filter())
async def valume_ap(callback: CallbackQuery, callback_data: VolumeCallback):

    #    if callback.from_user.id != ADMIN_ID:
    #        return await callback.answer("Отказано в доступе!")

    if callback_data.action == "up":
        await callback.answer()
        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume
        current_volume = volume.GetMasterVolumeLevelScalar()

        target_volume = max(0.0, min(current_volume + 0.04, 1.0))

        volume.SetMasterVolumeLevelScalar(target_volume, None)

        await callback.message.edit_text(
            text=f"{volume_chunks(target_volume)} {round(target_volume * 100)}%",
            reply_markup=volume_kb
        )

    if callback_data.action == "down":
        await callback.answer()
        devices = AudioUtilities.GetSpeakers()
        volume = devices.EndpointVolume
        current_volume = volume.GetMasterVolumeLevelScalar()

        target_volume = max(0.0, min(current_volume - 0.04, 1.0))
        volume.SetMasterVolumeLevelScalar(target_volume, None)

        await callback.message.edit_text(
            text=f"{volume_chunks(target_volume)} {round(target_volume * 100)}%",
            reply_markup=volume_kb
        )


@dp.callback_query(F.data == "pc_info")
async def all_info(callback: CallbackQuery):

    memory = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=None)

    total = f"🧠 RAM: {memory.total / (1024**3):.1f} ГБ"
    used = f"  └ <code>Используется: {memory.used / (1024**3):.1f} ГБ ({memory.percent}%)</code>"
    free = f'  └ <code>Свободно: {memory.available / (1024**3):.1f} ГБ</code>'

    cpu_work_value = await asyncio.to_thread(psutil.cpu_percent, 1)
    cpu_work = f"<code>Нагрузка на ЦП: {cpu_work_value}%</code>"
    cpu_cores = f"  └ 📟<code>Количество ядер: {psutil.cpu_count(logical=True)}</code>"

    disk_c = psutil.disk_usage('C:')
    percent_used_c = disk_c.percent
    scalar_used_c = percent_used_c / 100

    disk_d = psutil.disk_usage('D:')
    percent_used_d = disk_d.percent
    scalar_used_d = percent_used_d / 100

    time_work = time.time() - psutil.boot_time()
    minutes, seconds = divmod(int(time_work), 60)
    hours, minutes = divmod(minutes, 60)

    text_status = (
        "🎚️ <b>Информация о RAM</b>\n\n"
        f"{total}\n"
        f"{used}\n"
        f"{free}\n\n"

        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
        "🔥 <b>Информация о CPU</b>\n\n"
        f"⚡ {cpu_work}\n"
        f"{cpu_cores}\n\n"

        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        "💾 <b>Информация о ДИСКЕ</b>\n\n"
        f"📁 Диск C:{volume_chunks(scalar_used_c)}\n                                        {percent_used_c}%\n"
        f"📁 Диск D:{volume_chunks(scalar_used_d)}\n                                        {percent_used_d}%\n\n"

        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"

        f"⏳ <b>Состояние ПК:</b>\n\n"
        f"Время работы: <code>{hours} ч. {minutes} мин.</code>"
    )

    await callback.message.edit_text(text=text_status, parse_mode="HTML", reply_markup=back_kb)


@dp.callback_query(F.data == 'pc_open')
async def open_app(callback: CallbackQuery, state: FSMContext):

    await callback.message.edit_text("📂 Напиши название приложения которе хочешь открыть.\nНапример: <code>discord</code>, <code>telegram</code>, <code>steam</code>, <code>bettersoundcloud</code>, <code>chrome</code>", parse_mode="HTML", reply_markup=back_kb)
    await state.set_state(Form.waiting_for_app)


@dp.message(Form.waiting_for_app)
async def getint_app_name(message: Message, state: FSMContext):
    name_app = message.text
    if not name_app:
        return await message.answer("🟡 Пожалуйста, отправьте текстовое название программы!")
    await state.clear()

    status_msg = await message.answer(f"🟢 Ищу и запускаю <b>{name_app}...</b>",
                                      parse_mode="HTML")

    succes = await asyncio.to_thread(find_and_run_app, name_app)

    if succes:
        await status_msg.edit_text(f"🟢 <b>{name_app}</b> успешно запущено", reply_markup=back_kb,
                                   parse_mode="HTML")
    else:
        await status_msg.edit_text(f"🔴 <b>{name_app}</b> не удалось найти  в стандартных папках.", reply_markup=back_kb,
                                   parse_mode="HTML")


@dp.callback_query(F.data == "pc_shutdown")
async def off_pc(callback: CallbackQuery):
    await callback.message.edit_text(
        text=f"⚠️ Вы уверены что хотите выключить ПК? ⚠️", reply_markup=yes_off_kb)


@dp.callback_query(F.data == "yes_of")
async def yes_off_pc(callback: CallbackQuery):

    await callback.message.edit_text(text="💤 ПК выключится через 5 сек.", reply_markup=None)
    await asyncio.sleep(1)

    for sec in range(4, 0, -1):
        await callback.message.edit_text(text=f"💤 ПК выключится через {sec} сек.")
        await asyncio.sleep(1)
    await callback.message.edit_text(text="🟡 Выключение ПК...")
    subprocess.Popen("shutdown /s /t 7", shell=True)
    await callback.answer(text="🟢 Успешно!")
    await asyncio.sleep(5)
    await callback.message.edit_text(text="🟢 ПК был успешно выключен!")


@dp.callback_query(F.data == "pc_restart")
async def restart_pc(callback: CallbackQuery):
    await callback.message.edit_text(text="⚠️ Вы уверены что хотите перезагрузить ПК? ⚠️", reply_markup=yes_restart_kb)
    await asyncio.sleep(1)


@dp.callback_query(F.data == "yes_restart")
async def yes_restart_pc(callback: CallbackQuery):

    await callback.message.edit_text(text="🔄 ПК перезазагрузится через 5 сек.", reply_markup=None)
    await asyncio.sleep(1)

    for sec in range(4, 0, -1):
        await callback.message.edit_text(text=f"🔄 ПК перезагрузится через {sec} сек.")
        await asyncio.sleep(1)
    await callback.message.edit_text(text="🟡 Перезапуск ПК...")
    subprocess.Popen("shutdown /r /f /t 0", shell=True)
    await asyncio.sleep(5)
    await callback.message.edit_text(text="🟢 ПК был успешно перезагружен!")


@dp.callback_query(F.data == "process")
async def process(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(text="Считываю нагрузку на ЦП...")

    top_procs = await asyncio.to_thread(get_top_cpu_processes(limit=10))
    text_list = []
    for i, proc in enumerate(top_procs, start=1):
        text_list.append(
            f"{i}. <code>{proc['name']}</code> -- {proc['cpu']:.1f}% ЦП\n")

    final_text = "".join(text_list)
    await callback.message.edit_text(text=f"--- ТОП-10 самых тяжелых процессов ---\n\n{final_text}", reply_markup=menu_processes_kb, parse_mode="HTML")


@dp.callback_query(F.data == 'kill_process')
async def getint_process_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📂 Напиши название процесса который хочешь остановить:", reply_markup=back_kb)
    await state.set_state(Form.waiting_for_process)


@dp.message(Form.waiting_for_process)
async def getint_app_name(message: Message, state: FSMContext):
    process_name = message.text.lower()

    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() == process_name:
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    await state.clear()
    await message.answer("🟢 Процесс успешно прибит!", reply_markup=back_kb)


@dp.callback_query(F.data == "remake_process")
async def remake_process_def(callback: CallbackQuery):
    await callback.message.edit_text(text="🟡 Считываю нагрузку на ЦП...")

    top_procs = get_top_cpu_processes(limit=10)
    text_list_remake = []
    for i, proc in enumerate(top_procs, start=1):
        text_list_remake.append(
            f"{i}. <code>{proc['name']}</code> -- {proc['cpu']:.1f}% ЦП\n")

    final_text_remake = "".join(text_list_remake)
    await callback.answer(text="🟢 Успешно!")
    await callback.message.edit_text(text=f"--- ТОП-10 самых тяжелых процессов ---\n\n{final_text_remake}", reply_markup=menu_processes_kb, parse_mode="HTML")


async def main() -> None:
    await asyncio.sleep(10)
    bot = Bot(token=config["token"])

    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Бот успешно подключился к сети!")
            break

        except TelegramNetworkError:
            print("Сеть еще не готова. Ждем 5 секунд...")
            await asyncio.sleep(5)

    try:
        await bot.send_message(chat_id=ADMIN_ID, text="🟢 <b>Компьютер успешно включен и бот готов к работе!</b>", parse_mode="HTML")

    except Exception as e:
        logging.error(f"Не удалось отправить уведомление о запуске: {e}")

    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
