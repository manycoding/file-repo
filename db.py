import sqlite3

from tornado.options import define, options
from tornado.gen import coroutine
from tornado.log import logging


define("database", default="file-repo.sqlite3", help="database name")
conn = sqlite3.connect(options.database)
# db.row_factory = lambda _cursor, row: {col[0]: row[i] for i, col in enumerate(_cursor.description)}
cursor = conn.cursor()


def query(sql):
    data = None
    try:
        logging.info(f'query: {sql}')
        with conn:
            cursor.execute(sql)
        if sql.startswith('INSERT '):
            # conn.commit()
            data = cursor.lastrowid
        else:
            data = cursor.fetchall()
        logging.info(f'query: {data}')
    except Exception as e:
        logging.error(f'{e}')
        logging.info(f'query: {sql}')
    return data


@coroutine
def get_file_list(user=None):
    logging.info('db.get_file_list')
    files = yield query("""
        SELECT files.name, files.published, files.id, u.name as user_name, u.id as user_id, files.pages
        FROM files
        JOIN users u on (u.id=files.user_id)
        ORDER BY files.published;
        """)
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
def get_user_id(name):
    user_id = yield query("""
        SELECT * FROM users WHERE name=?
        """, (name,))
    return user_id


@coroutine
def insert_pdf(pdf_name, hashed_name, user_name, total_pages=-1):
    user_id = yield get_user_id(user_name)
    logging.info(f'insert_pdf: user_name={user_name} user_id={user_id} selected')
    user_id = user_id[0]['id'] if user_id is not None else 0
    logging.info(f'insert_pdf: user_name={user_name} user_id={user_id} selected')
    pdf_id = yield query("""
        INSERT into files (name, hashed_name, user_id, pages) values (?, ?, ?, ?);
        """, (name, hashed_name, user_id, pages))
    logging.debug(f'insert_pdf: {pdf_id} {pdf_name} {user_id} inserted')
    return pdf_id, pdf_name, user_id, hashed_name  # , pages


def init():
    try:
        cursor.execute("SELECT COUNT(*) from users;")
    except Error as e:
        logging.debug("Creating tables")
        query("""
            CREATE TABLE IF NOT EXISTS users (
              id integer PRIMARY KEY,
              name text NOT NULL,
              hashed_password text NOT NULL
            );""")
        query("""
            CREATE TABLE IF NOT EXISTS files (
              id integer PRIMARY KEY,
              file blob NOT NULL,
              user_id integer NOT NULL,
              pages integer,
              published datetime,
              name text NOT NULL,
              hashed_name text UNIQUE ON CONFLICT ROLLBACK
              FOREIGN KEY (user_id) REFERENCES users (id)
            );""")
