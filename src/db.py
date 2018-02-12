import bcrypt
import datetime
import sqlite3
import tornado
import concurrent.futures

from tornado.options import define, options
from tornado.gen import coroutine
from tornado.log import logging


define("database", default="file-repo.sqlite3", help="database name")
conn = sqlite3.connect(options.database, check_same_thread=False)
conn.row_factory = lambda _cursor, row: {
    col[0]: row[i] for i, col in enumerate(_cursor.description)}
cursor = conn.cursor()
# A thread pool
executor = concurrent.futures.ThreadPoolExecutor(2)


def query(sql, args):
    data = None
    try:
        logging.info('query: {} {}'.format(sql, args))
        with conn:
            cursor.execute(sql, args)
        if sql.strip().startswith('INSERT '):
            data = cursor.lastrowid
        else:
            data = cursor.fetchall()
        logging.info('query: {}'.format(data))
    except Exception as e:
        logging.error(e)
    return data


def get_file_list(user=None):
    files = query("""
        SELECT files.name, files.hashed_name, files.published, files.id, u.name as user_name, u.id as user_id, files.pages
        FROM files
        JOIN users u on (u.id=files.user_id)
        ORDER BY files.published;
        """, ()) # noqa
    logging.debug('db.get_file_list {}'.format(files))
    return files


def get_pdf_by_hashed_name(hashed_name):
    pdf_file = query("""
        SELECT id as pdf_id, name, hashed_name, published, user_id, pages
        FROM files
        WHERE (hashed_name=?);
        """, (hashed_name,))
    return pdf_file


@coroutine
def auth_user(name, password):
    hashed_password = query("""
        SELECT hashed_password FROM users WHERE name=?
        """, (name,))
    hashed_password = hashed_password[0]['hashed_password'] if hashed_password else None # noqa
    logging.debug("hashed_password {}".format(hashed_password))

    if not hashed_password:
        return None

    p = yield executor.submit(
        bcrypt.hashpw, tornado.escape.utf8(password),
        tornado.escape.utf8(hashed_password))
    if hashed_password == p:
        logging.info('db.get_user: {}'.format(name))
        return name
    return None


def get_user_id(name):
    user_id = query("""
        SELECT id FROM users WHERE name=?
        """, (name,))
    return user_id


@coroutine
def create_user(name, password):
    if not password:
        return None
    hashed_password = yield executor.submit(
        bcrypt.hashpw, tornado.escape.utf8(password),
        bcrypt.gensalt())
    user_id = query("""
        INSERT INTO users(name, hashed_password)
        VALUES(?, ?)""", (name, hashed_password,))
    return user_id


def insert_pdf(pdf_name, hashed_name, user_name, total_pages=-1):
    user_id = get_user_id(user_name)
    user_id = user_id[0]['id'] if user_id is not None else 0
    query("""
        INSERT into files (name, hashed_name, user_id, pages, published) values (?, ?, ?, ?, ?);
        """, (pdf_name, hashed_name, user_id, total_pages, datetime.datetime.now())) # noqa
    logging.debug(
        'insert_pdf: {} {} {} inserted'.format(pdf_id, pdf_name, user_id)) # noqa


def insert_file(name, hashed_name, user_name):
    user_id = get_user_id(user_name)
    user_id = user_id[0]['id'] if user_id is not None else 0
    query("""
        INSERT into files (name, hashed_name, user_id, published)
            values (?, ?, ?, ?);
        """, (name, hashed_name, user_id, datetime.datetime.now()))


def init():
    query("""
        CREATE TABLE IF NOT EXISTS users (
          id integer PRIMARY KEY,
          name text NOT NULL UNIQUE,
          hashed_password text NOT NULL
        );""", ())
    query("""
        CREATE TABLE IF NOT EXISTS files (
          id integer PRIMARY KEY,
          user_id integer NOT NULL,
          pages integer,
          published datetime,
          name text NOT NULL,
          hashed_name text UNIQUE ON CONFLICT ROLLBACK,
          FOREIGN KEY (user_id) REFERENCES users (id)
        );""", ())
