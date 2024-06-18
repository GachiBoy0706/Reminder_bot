import telebot
from telebot import types 
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from datetime import datetime, timedelta
import time
import threading
import os
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re


class Task:
    def __init__(self, theme, date, period=0, attachments=None, chat_id=None, file_names=None):
        if isinstance(date, str):
            date = parse_datetime(date)
        self.theme = theme
        self.date = date
        self.period = period
        self.attachments = attachments if attachments is not None else []
        self.chat_id = chat_id  
        self.file_names=file_names

global tasks, user_files, file_urls, file_names
user_files = {}
tasks = []
file_urls = []
file_names = []
global theme, date, state, period

gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)
state = 'wait'

global cur_tasks, comp_tasks, task_index
cur_tasks = []
comp_tasks = []

bot = telebot.TeleBot('7094401548:AAG-2dJTLvXK3cFVUFw79D37yyGIwBFmRaI')

# def create_and_upload_file(file_name):
#     global file_urls
#     try:
#         my_file = drive.CreateFile({'title': file_name, 'parents': [{'id': '1EDY5PBu1eotATCJm57cZo-zM_LhPM2D9'}]})
#         with open(file_name, 'r') as file:
#             content = file.read()
#             print(content)
#         #my_file.SetContentFile(file_name)
#         # my_file.Upload()
#         # print(f"https://drive.google.com/file/d/{my_file['id']}/view?usp=sharing")
#         # file_urls.append(f"https://drive.google.com/file/d/{my_file['id']}/view?usp=sharing")
#         return f'File {file_name} was uploaded! Have a good day!'
#     except Exception as _ex:
#         return 'Got some trouble, check your code please!'



def parse_datetime(date_string):
    try:
        parsed_date = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
        return parsed_date
    except ValueError:
        return None

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup()
    btn1 = types.KeyboardButton('Посмотреть список текущих дел')
    btn2 = types.KeyboardButton('Посмотреть список выполненных дел')
    markup.add(btn1, btn2)
    bot.send_message(message.chat.id, 'Привет! Я бот для создания напоминаний, чтобы добавить новое событие отправь тему, дату и прикрепи файлы (если необходимо) разными сообщениями', reply_markup=markup)

@bot.message_handler(commands=['done'])
def done(message):
    global user_files, state, cur_tasks, task_index, file_urls
    user_id = message.chat.id

    if user_id in user_files and user_files[user_id]:
        for file_name in user_files[user_id]:
            upload_to_drive(file_name)
            os.remove(file_name)  # Удаляем файл после загрузки
        user_files[user_id] = []
        bot.send_message(user_id, "Все файлы загружены на Google Drive.")
    else:
        bot.send_message(user_id, "Вы не отправили ни одного файла.")
    if state == 'new_task':
        bot.send_message(user_id, "Введите периодичность задачи (0 для одноразовой задачи)")
        bot.register_next_step_handler(message, add_period)
        #data_check(message)
    else: 
        cur_tasks[task_index].attachments = file_urls
        #file_urls = []
        bot.send_message(user_id, "Файлы успешно перезаписаны")


    
def upload_to_drive(file_name):
    global file_urls, file_names
    try:
        my_file = drive.CreateFile({'title': file_name, 'parents': [{'id': '1EDY5PBu1eotATCJm57cZo-zM_LhPM2D9'}]})
        my_file.SetContentFile(file_name)
        my_file.Upload()
        print(f"Файл {file_name} загружен: https://drive.google.com/file/d/{my_file['id']}/view?usp=sharing")
        file_names.append(file_name)
        file_urls.append(f"https://drive.google.com/file/d/{my_file['id']}/view?usp=sharing")
    except Exception as _ex:
        print(f"Произошла ошибка при загрузке файла {file_name}: {_ex}")

def add_period(message):
    global period
    period = int(message.text)
    bot.send_message(message.chat.id, f'Задача будет повторяться каждый/-ые "{period}" день/дней')
    data_check(message)

@bot.message_handler(commands=['check'])
def checkereee(message):
    bot.send_message(message.chat.id, 'Все задачки на сегодня выполнены! Самое время отдохнуть')
    check_today_tasks()

@bot.message_handler(commands=['new_task'])
def new_task(message):
    global state
    state = 'new_task'
    bot.send_message(message.chat.id, f'Введи тему')
    bot.register_next_step_handler(message, read_theme)

def read_theme(message):
    global theme
    theme = message.text
    bot.send_message(message.chat.id, f'Тема "{theme}"')
    bot.send_message(message.chat.id, f'Теперь введи дату (пример 2024-05-16 15:30:00)')
    bot.register_next_step_handler(message, read_date)

def read_date(message):
    global date
    date = parse_datetime(message.text)
    if date:
        bot.send_message(message.chat.id, f'Дата {date}')
        bot.send_message(message.chat.id, 'Нужно ли прикреплять файлы? (Да/Нет)')
        bot.register_next_step_handler(message, is_file_needed)
    else:
        bot.send_message(message.chat.id, f'Неправильный формат даты')
        bot.register_next_step_handler(message, read_date)

def is_file_needed(message):
    if message.text.lower() == 'да':
        bot.send_message(message.chat.id, 'Пришли мне файлы')
        bot.register_next_step_handler(message, file_needed)
    else:
        bot.send_message(message.chat.id, "Введите периодичность задачи (0 для одноразовой задачи)")
        bot.register_next_step_handler(message, add_period) 
        #data_check(message)

@bot.message_handler(content_types=['document', 'photo'])
def file_needed(message):
    global user_files, state
    if state == 'wait':
        bot.send_message(user_id, "Сейчас файл не ожидается")
        return
    user_id = message.chat.id
    if user_id not in user_files:
        user_files[user_id] = []

    if message.document:
        file_info = bot.get_file(message.document.file_id)
        
        file_name = message.document.file_name

    elif message.photo:
        file_id = message.photo[-1].file_id  # Использование самого большого по размеру фото
        file_info = bot.get_file(file_id)
        file_name = f'photo_{file_id}.jpg'

    downloaded_file = bot.download_file(file_info.file_path)

    with open(file_name, 'wb') as new_file:
        new_file.write(downloaded_file)
    
    user_files[user_id].append(file_name)
    bot.send_message(user_id, f"Файл {file_name} получен и сохранен. Отправьте следующий файл или команду /done для завершения.")


    # user_files[user_id].append((message.document.file_id, message.document.file_name))
    # bot.send_message(user_id, f"Файл {message.document.file_name} получен. Отправьте следующий файл или команду /done для завершения.")

def data_check(message):
    global theme, date, tasks, file_urls, cur_tasks, period, state, file_names
    if isinstance(date, str):
        date = parse_datetime(date)
    cur_tasks.append(Task(theme=theme, date=date, period=period, attachments=file_urls, chat_id=message.chat.id, file_names=file_names))
    file_urls = []
    file_names = []
    bot.send_message(message.chat.id, f'Тема: {theme}, дата: {date}')
    state = 'wait'
    

@bot.message_handler(func=lambda message: True)
def on_click(message):
    if message.text == 'Посмотреть список текущих дел':
        send_cur_tasks_list(message)
    elif message.text == 'Посмотреть список выполненных дел':
        send_comp_tasks_list(message)

def send_cur_tasks_list(message):
    global cur_tasks
    if not cur_tasks:
        bot.send_message(message.chat.id, 'Список задач пуст.')
        return
    for idx, task in enumerate(cur_tasks):
        task_message = f"Тема: {task.theme}\nДата: {task.date}\nПериодичность: {task.period} дней"
        markup = types.InlineKeyboardMarkup()
        edit_button = types.InlineKeyboardButton("Редактировать", callback_data=f'edit_{idx}')
        complete_button = types.InlineKeyboardButton("Перевести в выполненное", callback_data=f'complete_{idx}')
        delete_button = types.InlineKeyboardButton("Удалить", callback_data=f'delete_{idx}')
        markup.add(edit_button, complete_button, delete_button)
        bot.send_message(message.chat.id, task_message, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def callback_delete(call):
    task_index = int(call.data.split('_')[1])
    deleted_task = cur_tasks.pop(task_index)
    bot.send_message(call.message.chat.id, f"Задача {deleted_task.theme} удалена")

@bot.callback_query_handler(func=lambda call: call.data.startswith('complete_'))
def callback_complete(call):
    task_index = int(call.data.split('_')[1])
    completed_task = cur_tasks.pop(task_index)
    comp_tasks.append(completed_task)
    bot.send_message(call.message.chat.id, f"Задача {completed_task.theme} переведена в выполненные")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_period_'))
def callback_edit_period(call):
    global task_index
    bot.send_message(call.message.chat.id, f"Введите новую периодичность для задачи {cur_tasks[task_index].theme}")
    bot.register_next_step_handler(call.message, change_period, task_index)
    
def change_period(message, task_index):
    cur_tasks[task_index].period = message.text
    bot.send_message(message.chat.id, f"Пеоиодичность задачи изменена на {cur_tasks[task_index].period}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_theme_'))
def callback_edit_theme(call):
    global task_index
    bot.send_message(call.message.chat.id, f"Введите новую тему для задачи {cur_tasks[task_index].theme}")
    bot.register_next_step_handler(call.message, change_theme, task_index)

def change_theme(message, task_index):
    cur_tasks[task_index].theme = message.text
    bot.send_message(message.chat.id, f"Тема задачи изменена на {cur_tasks[task_index].theme}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_date_'))
def callback_edit_date(call):
    global task_index
    bot.send_message(call.message.chat.id, f"Введите новую дату для задачи {cur_tasks[task_index].theme}")
    bot.register_next_step_handler(call.message, change_date, task_index)

def change_date(message, task_index):
    cur_tasks[task_index].date = parse_datetime(message.text)
    bot.send_message(message.chat.id, f"Дата задачи изменена на {cur_tasks[task_index].date}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_files_'))
def callback_edit_files(call):
    global task_index
    bot.send_message(call.message.chat.id, f"Пришлите новые файлы для задачи {cur_tasks[task_index].theme}")
    cur_tasks[task_index].attachments = []  # Очистка текущих вложений

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def callback_edit(call):
    global state, task_index
    state = 'edit'
    task_index = int(call.data.split('_')[1])
    markup = types.InlineKeyboardMarkup()
    edit_theme_button = types.InlineKeyboardButton("Тема", callback_data=f'edit_theme_')
    edit_date_button = types.InlineKeyboardButton("Дата", callback_data=f'edit_date_')
    edit_files_button = types.InlineKeyboardButton("Файлы", callback_data=f'edit_files_')
    edit_period_button = types.InlineKeyboardButton("Период", callback_data=f'edit_period_')
    markup.add(edit_theme_button, edit_date_button, edit_files_button, edit_period_button)
    bot.send_message(call.message.chat.id, 'Что изменить?', reply_markup=markup)

def send_comp_tasks_list(message):
    global comp_tasks
    if not comp_tasks:
        bot.send_message(message.chat.id, 'Список выполненных задач пуст.')
        return
    
    # Сортировка задач по дате в порядке убывания
    sorted_comp_tasks = sorted(comp_tasks, key=lambda task: task.date, reverse=True)
    
    for idx, task in enumerate(sorted_comp_tasks):
        task_message = f"Тема: {task.theme}\nДата: {task.date}"
        if task.attachments:
            for attachment in task.attachments:
                task_message += f"\nВложение: {attachment}"
        markup = types.InlineKeyboardMarkup()
        return_button = types.InlineKeyboardButton("Вернуть в текущие", callback_data=f'return_{idx}')
        markup.add(return_button)
        bot.send_message(message.chat.id, task_message, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('return_'))
def callback_return(call):
    global task_index
    task_index = int(call.data.split('_')[1])
    completed_task = comp_tasks.pop(task_index)
    bot.send_message(call.message.chat.id, f"Введите новую дату для задачи '{completed_task.theme}'")
    bot.register_next_step_handler(call.message, set_new_date, completed_task)

def set_new_date(message, task):
    global cur_tasks
    new_date = parse_datetime(message.text)
    if new_date:
        task.date = new_date
        cur_tasks.append(task)
        bot.send_message(message.chat.id, f"Задача '{task.theme}' возвращена в текущие задачи с новой датой '{task.date}'")
    else:
        bot.send_message(message.chat.id, 'Неправильный формат даты. Попробуйте снова.')
        bot.register_next_step_handler(message, set_new_date, task)


def download_file(url, name):
    # Преобразуем URL для прямой загрузки файла
    file_id = url.split('/d/')[1].split('/')[0]
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    print(f'Начинаю загрузку для уведомления из {direct_url}')
    
    # Создаем сессию, чтобы обрабатывать редиректы и скачивать файл
    session = requests.Session()
    response = session.get(direct_url, stream=True)
    
    # Проверяем наличие предупреждающего сообщения от Google
    if "confirm" in response.url:
        confirm_token = response.url.split('confirm=')[1].split('&')[0]
        direct_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
        response = session.get(direct_url, stream=True)
    
    # Сохраняем файл во временное хранилище
    with open(name, 'wb') as file:
        for chunk in response.iter_content(chunk_size=32768):
            if chunk:
                file.write(chunk)
    
    return name


def check_today_tasks():
    global cur_tasks, comp_tasks
    now = datetime.now()
    tasks_to_complete = []

    for task in cur_tasks:
        if (task.date.date() == now.date() and 
            task.date.hour == now.hour and 
            task.date.minute == now.minute and 
            task.date.second == now.second):
            # Отправка напоминания о задаче
            bot.send_message(task.chat_id, f"Напоминание: сегодня необходимо выполнить задачу '{task.theme}'")
            # Загрузка и отправка вложений как документов
            for attachment_url, attachment_names in zip(task.attachments, task.file_names):
                bot.send_message(task.chat_id, f"Файл '{attachment_names}' по ссылку {attachment_url}")
                bot.send_message(task.chat_id, "Чтобы закрыть задачу, отметьте ее как выполненную в редакторе этой задачи")
                # file_name = download_file(attachment_url, attachment_names
                # with open(file_name, 'rb') as file:
                #     bot.send_document(task.chat_id, file)
                # # Удаляем временный файл после отправки
                # os.remove(file_name)
            # Если задача периодическая, обновить её дату
            if task.period > 0:
                task.date += timedelta(days=task.period)
                bot.send_message(task.chat_id, f"Задача '{task.theme}' перенесена на {task.date}")
            else:
                tasks_to_complete.append(task)

    # Перевод одноразовых задач в выполненные
    # for task in tasks_to_complete:
    #     cur_tasks.remove(task)
    #     comp_tasks.append(task)
    #     bot.send_message(task.chat_id, f"Задача '{task.theme}' отмечена как выполненная")


def schedule_checker():
    while True:
        check_today_tasks()
        time.sleep(1)



checker_thread = threading.Thread(target=schedule_checker)
checker_thread.start()

bot.polling(non_stop=True)