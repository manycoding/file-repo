import bcrypt
import sqlite3
import tornado
import concurrent.futures

from tornado.options import define, options
from tornado.gen import coroutine
from tornado.log import logging


define("database", default="file-repo.sqlite3", help="database name")
conn = sqlite3.connect(options.database)
# db.row_factory = lambda _cursor, row: {col[0]: row[i] for i, col in enumerate(_cursor.description)}
cursor = conn.cursor()
# A thread pool
executor = concurrent.futures.ThreadPoolExecutor(2)


@coroutine
def query(sql, args):
    data = None
    try:
        logging.info(f'query: {sql} {args}')
        with conn:
            cursor.execute(sql, args)
        if sql.startswith('INSERT '):
            # conn.commit()
            data = cursor.lastrowid
        else:
            data = cursor.fetchall()
        logging.info(f'query: {data}')
    except Exception as e:
        logging.error(f'{e}')
        logging.info(f'query: {sql} {args}')
    return data


@coroutine
def get_file_list(user=None):
    logging.info('db.get_file_list')
    files = yield query("""
        SELECT files.name, files.published, files.id, u.name as user_name, u.id as user_id, files.pages
        FROM files
        JOIN users u on (u.id=files.user_id)
        ORDER BY files.published;
        """, ())
    logging.debug(f'db.get_file_list {files}')
    return files


@coroutine
def get_pdf_by_hashed_name(hashed_name):
    pdf_file = yield query("""
        SELECT id as pdf_id, name, hashed_name, published, user_id, pages
        FROM files
        WHERE (hashed_name=?);
        """, (hashed_name,))
    return pdf_file


@coroutine
def get_user(name, password):
    logging.debug(name)
    logging.debug(password)
    hashed_password = yield query("""
        SELECT hashed_password FROM users WHERE name=?
        """, (name,))
    hashed_password = hashed_password[0][0] if hashed_password else None
    logging.info(f'hashed_password: {hashed_password}')

    if not hashed_password:
        return None

    hashed_password = yield executor.submit(
        bcrypt.hashpw, tornado.escape.utf8(password),
        tornado.escape.utf8(hashed_password))
    logging.info(f'new hashed_password: {hashed_password}')
    hashed_password = hashed_password[0] if hashed_password else None

    if hashed_password:
        logging.info(f'db.get_user: {name}')
        return name
    return None


@coroutine
def get_user_id(name):
    user_id = yield query("""
        SELECT id FROM users WHERE name=?
        """, (name,))
    return user_id


@coroutine
def create_user(name, password):
    hashed_password = yield executor.submit(
        bcrypt.hashpw, tornado.escape.utf8(password),
        bcrypt.gensalt())
    yield query("""
        INSERT INTO users(name, hashed_password)
        VALUES(?, ?)""", (name, hashed_password,))


@coroutine
def insert_pdf(pdf_name, hashed_name, user_name, total_pages=-1):
    user_id = yield get_user_id(user_name)
    logging.info(
        f'insert_pdf: user_name={user_name} user_id={user_id} selected')
    user_id = user_id[0] if user_id is not None else 0
    logging.info(
        f'insert_pdf: user_name={user_name} user_id={user_id} selected')
    pdf_id = yield query("""
        INSERT into files (name, hashed_name, user_id, pages) values (?, ?, ?, ?);
        """, (pdf_name, hashed_name, user_id, total_pages))
    logging.debug(f'insert_pdf: {pdf_id} {pdf_name} {user_id} inserted')
    return pdf_id, pdf_name, user_id, hashed_name


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
          file blob NOT NULL,
          user_id integer NOT NULL,
          pages integer,
          published datetime,
          name text NOT NULL,
          hashed_name text UNIQUE ON CONFLICT ROLLBACK,
          FOREIGN KEY (user_id) REFERENCES users (id)
        );""", ())
