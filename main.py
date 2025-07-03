from telebot import *
import sqlite3
import datetime
import logging
import threading
import time

bot = telebot.TeleBot('7927852329:AAE3Rf58_anW_ofrf7bKLgc_sKZU4XcZ03s')
SUPER_ADMIN_ID = 934063906
DATABASE_NAME = 'glaucoma_bot.db'


def init_db():
    conn = sqlite3.connect(DATABASE_NAME)
    cur = conn.cursor()

    cur.execute('''
    CREATE TABLE IF NOT EXISTS medications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        days TEXT NOT NULL,
        times TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS notifications_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        medication_id INTEGER NOT NULL,
        notification_time DATETIME NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        added_by INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (SUPER_ADMIN_ID,))
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (user_id, added_by) VALUES (?, ?)",
                    (SUPER_ADMIN_ID, SUPER_ADMIN_ID))

    conn.commit()
    conn.close()


init_db()


@bot.message_handler(
    content_types=['animation', 'audio', 'document', 'photo', 'sticker', 'story', 'video', 'video_note', 'voice',
                   'contact', 'dice', 'game', 'poll', 'venue', 'location', 'invoice', 'successful_payment',
                   'connected_website', 'passport_data', 'web_app_data'])
def invalidData(message):
    bot.reply_to(message,
                 f'{message.from_user.first_name}, такой тип сообщения не принимается. Используйте текстовые команды для взаимодействия с ботом.')


@bot.message_handler(commands=['start'])
def startMessage(message):
    bot.send_message(message.chat.id,
                     f'Емае, {message.from_user.first_name}... Короче надо придумать стартовое сообщение, Креативные директоры давайте.')


user_states = {}
user_temp_data = {}


def clear_user_state(user_id):
    """Очищает состояние пользователя"""
    if user_id in user_states:
        del user_states[user_id]
    if user_id in user_temp_data:
        del user_temp_data[user_id]


def is_admin(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    result = cur.fetchone() is not None
    conn.close()
    return result


def get_admins():
    conn = sqlite3.connect(DATABASE_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM admins")
    admins = [row[0] for row in cur.fetchall()]
    conn.close()
    return admins


def add_admin(user_id, added_by, username=None):
    conn = sqlite3.connect(DATABASE_NAME)
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO admins (user_id, username, added_by) VALUES (?, ?, ?)",
                    (user_id, username, added_by))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_admin(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cur = conn.cursor()
    try:
        if user_id == SUPER_ADMIN_ID:
            return False, "Нельзя удалить суперадминистратора"

        cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
        if not cur.fetchone():
            return False, "Этот пользователь не является администратором"

        cur.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM admins")
        count = cur.fetchone()[0]
        if count == 0:
            cur.execute("INSERT INTO admins (user_id, added_by) VALUES (?, ?)",
                        (SUPER_ADMIN_ID, SUPER_ADMIN_ID))
            conn.commit()
            return False, "Нельзя удалить последнего администратора. Суперадминистратор восстановлен"

        return True, "Администратор успешно удален"
    except Exception as e:
        return False, f"Ошибка удаления: {str(e)}"
    finally:
        conn.close()


def notify_admins(message):
    for admin_id in get_admins():
        try:
            bot.send_message(admin_id, message)
            logging.info(f"Уведомление отправлено администратору {admin_id}")
        except Exception as e:
            logging.error(f"Ошибка отправки администратору {admin_id}: {e}")


@bot.message_handler(commands=['addadmin'])
def handle_add_admin(message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды")
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "Использование: /addadmin <user_id>")
            return

        target_id = int(command_parts[1])
        if add_admin(target_id, user_id, message.from_user.username):
            bot.reply_to(message, f"Пользователь {target_id} добавлен в администраторы")
            notify_admins(f"Новый администратор: {target_id}\nДобавил: {user_id}")
        else:
            bot.reply_to(message, "Этот пользователь уже является администратором")
    except ValueError:
        bot.reply_to(message, "Некорректный ID пользователя. ID должен быть числом")


@bot.message_handler(commands=['myid'])
def handle_my_id(message):
    bot.reply_to(message, f"Ваш идентификатор пользователя: {message.from_user.id}")


@bot.message_handler(commands=['admins'])
def handle_list_admins(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды")
        return

    admins = get_admins()
    response = "Список администраторов:\n" + "\n".join(f"• {admin_id}" for admin_id in admins)
    bot.reply_to(message, response)


@bot.message_handler(commands=['removeadmin'])
def handle_remove_admin(message):
    user_id = message.from_user.id

    if not is_admin(user_id):
        bot.reply_to(message, "У вас нет прав для выполнения этой команды")
        return

    try:
        command_parts = message.text.split()
        if len(command_parts) < 2:
            bot.reply_to(message, "Использование: /removeadmin <user_id>")
            return

        target_id = int(command_parts[1])

        if target_id == user_id:
            bot.reply_to(message, "Вы не можете удалить сами себя")
            return

        success, result_msg = remove_admin(target_id)
        if success:
            bot.reply_to(message, f"Администратор {target_id} успешно удален")
            notify_admins(f"Администратор {target_id} удален пользователем {user_id}")
        else:
            bot.reply_to(message, result_msg)
    except ValueError:
        bot.reply_to(message, "Некорректный ID пользователя. ID должен быть числом")


def add_medication_start(user_id, chat_id):
    user_states[user_id] = "START_MEDICATION"
    user_temp_data[user_id] = {}

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_cancel = types.KeyboardButton('Отмена')
    markup.add(btn_cancel)

    bot.send_message(
        chat_id,
        "Добавление нового лекарственного препарата. Введите название препарата:",
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "START_MEDICATION")
def process_medication_name(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if message.text == 'Отмена':
        clear_user_state(user_id)
        bot.send_message(chat_id, "Добавление препарата отменено", reply_markup=types.ReplyKeyboardRemove())
        return

    user_temp_data[user_id]['name'] = message.text
    user_states[user_id] = "SELECT_DAYS"

    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    buttons = [
        types.KeyboardButton('Понедельник'),
        types.KeyboardButton('Вторник'),
        types.KeyboardButton('Среда'),
        types.KeyboardButton('Четверг'),
        types.KeyboardButton('Пятница'),
        types.KeyboardButton('Суббота'),
        types.KeyboardButton('Воскресенье'),
        types.KeyboardButton('Ежедневно'),
        types.KeyboardButton('Только будни'),
        types.KeyboardButton('Только выходные'),
        types.KeyboardButton('Завершить выбор дней')
    ]
    markup.add(*buttons)

    bot.send_message(
        chat_id,
        "Выберите дни недели для приема препарата:",
        reply_markup=markup
    )


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "SELECT_DAYS")
def process_days_selection(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    days_mapping = {
        'Понедельник': 'mon',
        'Вторник': 'tue',
        'Среда': 'wed',
        'Четверг': 'thu',
        'Пятница': 'fri',
        'Суббота': 'sat',
        'Воскресенье': 'sun',
        'Ежедневно': 'mon,tue,wed,thu,fri,sat,sun',
        'Только будни': 'mon,tue,wed,thu,fri',
        'Только выходные': 'sat,sun'
    }

    if message.text == 'Завершить выбор дней':
        selected_days = user_temp_data[user_id].get('days', [])
        if not selected_days:
            bot.send_message(chat_id, "Необходимо выбрать как минимум один день")
            return

        user_states[user_id] = "ENTER_TIMES"
        bot.send_message(
            chat_id,
            "Введите время приема через запятую в формате ЧЧ:ММ. Пример: 08:00, 13:30, 20:15\n"
            "Для каждого указанного времени будет создано отдельное напоминание",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return

    day_code = days_mapping.get(message.text)
    if not day_code:
        bot.send_message(chat_id, "Пожалуйста, используйте кнопки для выбора дней")
        return

    current_days = user_temp_data[user_id].get('days', [])

    if message.text in ['Ежедневно', 'Только будни', 'Только выходные']:
        current_days = day_code.split(',')
    else:
        if day_code in current_days:
            current_days.remove(day_code)
        else:
            current_days.append(day_code)

    user_temp_data[user_id]['days'] = current_days

    ru_days = {
        'mon': 'Понедельник',
        'tue': 'Вторник',
        'wed': 'Среда',
        'thu': 'Четверг',
        'fri': 'Пятница',
        'sat': 'Суббота',
        'sun': 'Воскресенье'
    }
    selected = [ru_days[d] for d in current_days]
    bot.send_message(
        chat_id,
        f"Текущий выбор дней: {', '.join(selected) or 'дни не выбраны'}\n"
        'Продолжайте выбор или нажмите "Завершить выбор дней"'
    )


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "ENTER_TIMES")
def process_times(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    times = [t.strip() for t in message.text.split(',')]

    valid_times = []
    for time_str in times:
        try:
            time_obj = datetime.datetime.strptime(time_str, '%H:%M')
            valid_time = time_obj.strftime('%H:%M')
            valid_times.append(valid_time)
        except ValueError:
            bot.send_message(
                chat_id,
                f"Некорректный формат времени: {time_str}. Используйте формат ЧЧ:ММ (например: 08:30)"
            )
            return

    user_temp_data[user_id]['times'] = valid_times
    user_states[user_id] = "ENTER_DESCRIPTION"

    bot.send_message(
        chat_id,
        "Введите дополнительные указания по приему препарата:\n"
        "(дозировка, способ применения, особые условия приема)"
    )


@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "ENTER_DESCRIPTION")
def process_description(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    temp_data = user_temp_data.get(user_id, {})

    if not temp_data:
        bot.send_message(chat_id, "Ошибка: данные сессии утеряны. Пожалуйста, начните процесс заново.")
        clear_user_state(user_id)
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO medications (user_id, name, days, times, description)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            temp_data['name'],
            ','.join(temp_data['days']),
            ','.join(temp_data['times']),
            message.text
        ))
        conn.commit()
    except Exception as e:
        logging.error(f"Ошибка сохранения препарата: {e}")
        bot.send_message(chat_id, "Произошла ошибка при сохранении препарата")
        return
    finally:
        conn.close()

    notify_admins(f"Пользователь {user_id} добавил новый препарат:\n"
                  f'Название: "{temp_data['name']}"\n'
                  f"Дни приема: {', '.join(temp_data['days'])}\n"
                  f"Время приема: {', '.join(temp_data['times'])}")

    clear_user_state(user_id)

    bot.send_message(
        chat_id,
        f'Препарат "{temp_data['name']}" успешно добавлен в план лечения.\n'
        f"Напоминания будут приходить в указанное время: {', '.join(temp_data['times'])}"
    )


def send_medication_reminders():
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        current_weekday = now.strftime("%a").lower()

        cursor.execute('''
        SELECT id, user_id, name, days, times, description 
        FROM medications
        ''')

        for med in cursor.fetchall():
            med_id, user_id, name, days_str, times_str, description = med
            times = times_str.split(',')
            days = days_str.split(',')

            if current_time in times and current_weekday in days:
                message = f"Время приема препарата: {name}"
                if description:
                    message += f"\nДополнительные указания: {description}"

                try:
                    bot.send_message(user_id, message)
                    logging.info(f"Отправлено напоминание пользователю {user_id} о препарате {name}")

                    cursor.execute('''
                    INSERT INTO notifications_log (user_id, medication_id, notification_time)
                    VALUES (?, ?, ?)
                    ''', (user_id, med_id, now))
                    conn.commit()

                    notify_admins(f'Отправлено напоминание пользователю {user_id} о препарате "{name}"')
                except Exception as e:
                    logging.error(f"Ошибка отправки пользователю {user_id}: {str(e)}")
                    notify_admins(f"Ошибка отправки напоминания пользователю {user_id}: {str(e)}")
    except Exception as e:
        logging.error(f"Ошибка в системе напоминаний: {str(e)}")
        notify_admins(f"Ошибка в системе напоминаний: {str(e)}")
    finally:
        conn.close()


def reminder_thread():
    while True:
        try:
            send_medication_reminders()
        except Exception as e:
            logging.error(f"Ошибка в потоке напоминаний: {str(e)}")

        time.sleep(60)


thread = threading.Thread(target=reminder_thread, daemon=True)
thread.start()

for admin_id in get_admins():
    try:
        bot.send_message(admin_id, "Система управления лечением глаукомы запущена")
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")


@bot.message_handler(commands=['medicationsplan'])
def handle_medications_plan(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, name, days, times, description 
    FROM medications 
    WHERE user_id = ?
    ''', (user_id,))
    medications = cursor.fetchall()
    conn.close()

    if not medications:
        response = "У вас нет добавленных препаратов в плане лечения."
    else:
        now = datetime.datetime.now()
        current_weekday = now.strftime("%a").lower()
        current_time = now.time()

        response = "Ваш текущий план лечения:\n\n"

        for med in medications:
            med_id, name, days_str, times_str, description = med
            days = days_str.split(',')
            times = times_str.split(',')

            next_times = []
            for time_str in times:
                try:
                    med_time = datetime.datetime.strptime(time_str, '%H:%M').time()

                    if current_weekday in days:
                        if med_time > current_time:
                            time_left = datetime.datetime.combine(datetime.date.today(), med_time) - now
                            next_times.append((time_left, f"сегодня в {time_str}"))
                            continue

                    days_abbr = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                    current_idx = days_abbr.index(current_weekday)

                    for i in range(1, 8):
                        next_day_idx = (current_idx + i) % 7
                        next_day = days_abbr[next_day_idx]

                        if next_day in days:
                            days_ahead = i if i < 7 else 7
                            next_date = datetime.date.today() + datetime.timedelta(days=days_ahead)
                            next_datetime = datetime.datetime.combine(next_date, med_time)

                            time_left = next_datetime - now
                            day_name = {
                                'mon': 'понедельник',
                                'tue': 'вторник',
                                'wed': 'среду',
                                'thu': 'четверг',
                                'fri': 'пятницу',
                                'sat': 'субботу',
                                'sun': 'воскресенье'
                            }.get(next_day, next_day)

                            next_times.append((time_left, f"{day_name} в {time_str}"))
                            break

                except ValueError:
                    continue

            response += f"<b>{name}</b>\n"
            if description:
                response += f"Описание: {description}\n"

            if next_times:
                next_times.sort(key=lambda x: x[0])
                closest_time = next_times[0]

                total_seconds = int(closest_time[0].total_seconds())
                days_left = total_seconds // (24 * 3600)
                hours_left = (total_seconds % (24 * 3600)) // 3600
                minutes_left = (total_seconds % 3600) // 60

                time_left_str = ""
                if days_left > 0:
                    time_left_str += f"{days_left} дн. "
                if hours_left > 0:
                    time_left_str += f"{hours_left} ч. "
                time_left_str += f"{minutes_left} мин."

                response += f"Следующий прием: {closest_time[1]} (через {time_left_str})\n\n"
            else:
                response += "Нет запланированных приемов\n\n"

    markup = types.InlineKeyboardMarkup(row_width=3)

    if medications:
        markup.add(
            types.InlineKeyboardButton('Добавить препарат', callback_data='add_med'),
            types.InlineKeyboardButton('Изменить препарат', callback_data='edit_med'),
            types.InlineKeyboardButton('Удалить препарат', callback_data='delete_med')
        )
    else:
        markup.add(types.InlineKeyboardButton('Добавить препарат', callback_data='add_med'))

    markup.add(types.InlineKeyboardButton('Отмена', callback_data='cancel_plan'))

    bot.send_message(
        chat_id,
        response,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.callback_query_handler(func=lambda call: call.data in ['add_med', 'edit_med', 'delete_med', 'cancel_plan'])
def handle_medication_actions(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    action = call.data

    if action == 'cancel_plan':
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        return

    if action == 'add_med':
        add_medication_start(user_id, chat_id)
        return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM medications WHERE user_id = ?', (user_id,))
    medications = cursor.fetchall()
    conn.close()

    if not medications:
        bot.send_message(chat_id, "У вас нет добавленных препаратов")
        return

    user_temp_data[user_id] = {'medications': medications}

    if action == 'edit_med':
        user_states[user_id] = "SELECT_MED_TO_EDIT"

        markup = types.InlineKeyboardMarkup(row_width=2)
        for med_id, name in medications:
            markup.add(types.InlineKeyboardButton(name, callback_data=f'select_med_{med_id}'))
        markup.add(types.InlineKeyboardButton('Отмена', callback_data='cancel_edit'))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="Выберите препарат для изменения:",
            reply_markup=markup
        )

    elif action == 'delete_med':
        user_states[user_id] = "SELECT_MED_TO_DELETE"

        markup = types.InlineKeyboardMarkup(row_width=2)
        for med_id, name in medications:
            markup.add(types.InlineKeyboardButton(name, callback_data=f'select_del_{med_id}'))
        markup.add(types.InlineKeyboardButton('Отмена', callback_data='cancel_delete'))

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text="Выберите препарат для удаления:",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('select_med_', 'select_del_')))
def select_med_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    action, med_id = call.data.split('_')[1:3]
    med_id = int(med_id)

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM medications WHERE id = ?", (med_id,))
    med_name = cursor.fetchone()[0]
    conn.close()

    user_temp_data[user_id] = {'selected_med': (med_id, med_name)}

    if action == 'med':
        user_states[user_id] = "SELECT_EDIT_ACTION"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('Изменить время приема', callback_data='edit_time'),
            types.InlineKeyboardButton('Изменить описание', callback_data='edit_desc'),
            types.InlineKeyboardButton('Отмена', callback_data='cancel_edit_action')
        )

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f'Выберите действие для препарата "{med_name}":',
            reply_markup=markup
        )

    elif action == 'del':
        user_states[user_id] = "CONFIRM_DELETE"

        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton('Да, удалить', callback_data='confirm_delete'),
            types.InlineKeyboardButton('Нет, отменить', callback_data='cancel_delete')
        )

        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f"Вы уверены, что хотите удалить препарат '{med_name}'?",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data in ['edit_time', 'edit_desc', 'cancel_edit_action'])
def handle_edit_action(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == 'cancel_edit_action':
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        clear_user_state(user_id)
        return

    selected_med = user_temp_data.get(user_id, {}).get('selected_med')
    if not selected_med:
        bot.send_message(chat_id, "Ошибка: данные не найдены")
        return

    med_id, med_name = selected_med

    if call.data == 'edit_time':
        user_states[user_id] = "EDIT_MED_TIMES"
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f'Введите новое время приема для "{med_name}" через запятую в формате ЧЧ:ММ\nПример: 08:00, 13:30, 20:15'
        )

    elif call.data == 'edit_desc':
        user_states[user_id] = "EDIT_MED_DESC"
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=call.message.message_id,
            text=f'Введите новое описание для препарата "{med_name}":\n(дозировка, способ применения и т.д.)'
        )


@bot.callback_query_handler(func=lambda call: call.data in ['confirm_delete', 'cancel_delete'])
def handle_delete_confirmation(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == 'cancel_delete':
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        clear_user_state(user_id)
        return

    selected_med = user_temp_data.get(user_id, {}).get('selected_med')
    if not selected_med:
        bot.send_message(chat_id, "Ошибка: препарат не найден")
        return

    med_id, med_name = selected_med

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medications WHERE id = ?", (med_id,))
    conn.commit()
    conn.close()

    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f'Препарат "{med_name}" успешно удален!'
    )

    notify_admins(f'Пользователь {user_id} удалил препарат: "{med_name}"')
    clear_user_state(user_id)

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "EDIT_MED_TIMES")
def edit_med_times(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    selected_med = user_temp_data.get(user_id, {}).get('selected_med')
    if not selected_med:
        bot.send_message(chat_id, "Ошибка: данные сессии утеряны")
        clear_user_state(user_id)
        return

    med_id, med_name = selected_med

    times = [t.strip() for t in message.text.split(',')]
    valid_times = []

    for time_str in times:
        try:
            datetime.datetime.strptime(time_str, '%H:%M')
            valid_times.append(time_str)
        except ValueError:
            bot.send_message(chat_id, f"Неверный формат времени: {time_str}. Используйте ЧЧ:ММ")
            return

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE medications SET times = ? WHERE id = ?",
        (','.join(valid_times), med_id))
    conn.commit()
    conn.close()

    bot.send_message(
        chat_id,
        f'Время приема для "{med_name}" успешно обновлено!'
    )
    clear_user_state(user_id)
    handle_medications_plan(message)

@ bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == "EDIT_MED_DESC")


def edit_med_desc(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    selected_med = user_temp_data.get(user_id, {}).get('selected_med')
    if not selected_med:
        bot.send_message(chat_id, "Ошибка: данные сессии утеряны")
        clear_user_state(user_id)
        return

    med_id, med_name = selected_med
    new_desc = message.text

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE medications SET description = ? WHERE id = ?",
        (new_desc, med_id))
    conn.commit()
    conn.close()

    bot.send_message(
        chat_id,
        f'Описание для "{med_name}" успешно обновлено!'
    )
    clear_user_state(user_id)
    handle_medications_plan(message)

@bot.callback_query_handler(func=lambda call: call.data in ['cancel_edit', 'cancel_delete', 'cancel_plan'])
def handle_cancel_actions(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    clear_user_state(call.from_user.id)

questions = [
    "ВЕРОЯТНО ОТРЕДАКТИРУЕТСЯ НУЖНО ИСКАТЬ ТОЧНУЮ ЛИТЕРАТУРУ\n1/5 \nИспытываете ли вы боль в глазах?",
    "2/5 \nБывают ли у вас головные боли в области лба?",
    "3/5 \nЗамечали ли вы ухудшение зрения?",
    "4/5 \nПоявляются ли радужные круги при взгляде на свет?",
    "5/5 \nБыла ли глаукома у ваших близких родственников?"
]


@bot.message_handler(commands=['selfdiagnosis'])
def selfDiagnosisMessage(message):
    user_id = message.from_user.id
    user_states[user_id] = {'current_question': 0, 'answers': [None] * len(questions), 'message_id': None,
                            'max_reached': 0}
    send_question(user_id, message.chat.id)


def send_question(user_id, chat_id):
    state = user_states[user_id]
    q_index = state['current_question']
    question_text = questions[q_index]

    state['max_reached'] = max(state['max_reached'], q_index)

    markup = types.InlineKeyboardMarkup()

    yes_text = 'Да ✓' if state['answers'][q_index] is True else 'Да'
    no_text = 'Нет ✓' if state['answers'][q_index] is False else 'Нет'

    buttons = []

    if q_index > 0:
        buttons.append(types.InlineKeyboardButton('←', callback_data='prevQuestion'))

    buttons.append(types.InlineKeyboardButton(yes_text, callback_data='positiveAnswer'))
    buttons.append(types.InlineKeyboardButton(no_text, callback_data='negativeAnswer'))

    if q_index < len(questions) - 1 and q_index < state['max_reached']:
        buttons.append(types.InlineKeyboardButton('→', callback_data='nextQuestion'))

    markup.row(*buttons)

    if state['message_id']:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=state['message_id'], text=question_text,
                                  reply_markup=markup)
        except:
            msg = bot.send_message(chat_id, question_text, reply_markup=markup)
            state['message_id'] = msg.message_id
    else:
        msg = bot.send_message(chat_id, question_text, reply_markup=markup)
        state['message_id'] = msg.message_id


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    if user_id not in user_states:
        return

    state = user_states[user_id]
    q_index = state['current_question']

    if data == 'positiveAnswer':
        state['answers'][q_index] = True
        if q_index < len(questions) - 1:
            state['current_question'] += 1
            send_question(user_id, chat_id)
        else:
            finish_diagnostic(chat_id, user_id)

    elif data == 'negativeAnswer':
        state['answers'][q_index] = False
        if q_index < len(questions) - 1:
            state['current_question'] += 1
            send_question(user_id, chat_id)
        else:
            finish_diagnostic(chat_id, user_id)

    elif data == 'nextQuestion':
        if q_index < state['max_reached']:
            state['current_question'] += 1
            send_question(user_id, chat_id)

    elif data == 'prevQuestion':
        if q_index > 0:
            state['current_question'] -= 1
            send_question(user_id, chat_id)


def finish_diagnostic(chat_id, user_id):
    state = user_states[user_id]
    positive_count = sum(1 for ans in state['answers'] if ans is True)

    if positive_count >= 3:
        result = "высокий риск глаукомы. Рекомендуем срочно обратиться к офтальмологу."
    elif positive_count >= 1:
        result = "средний риск глаукомы. Рекомендуем пройти обследование у специалиста."
    else:
        result = "низкий риск глаукомы."

    bot.edit_message_text(chat_id=chat_id, message_id=state['message_id'], text=f"Результаты самодиагностики: {result}")

    del user_states[user_id]


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id in user_states:
        current_state = user_states[user_id]
        return

    if message.text == 'Отмена':
        clear_user_state(user_id)
        bot.send_message(chat_id, "Текущая операция отменена", reply_markup=types.ReplyKeyboardRemove())


bot.polling(none_stop=True)