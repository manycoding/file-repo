import bcrypt
import concurrent.futures
import sqlite3
import tornado.ioloop
import tornado.web
import os

from sqlite3 import Error
from tornado.options import define, options
from tornado import gen

define("port", default=8888, help="run on the given port", type=int)
define("database", default="file-repo.sqlite3", help="database name")


# A thread pool to be used for password hashing with bcrypt.
executor = concurrent.futures.ThreadPoolExecutor(2)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/auth/create", AuthCreateHandler),
        ]
        self._db = None

        settings = dict(
            blog_title=u"File repo",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            # ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="oLGcDzgWH^5^$M77DS8mkOHNZ@$yO3pu1W6^Sy&s7jHreFUdGsy5EvkEIbKN%Q6^0qyr6J@u0Vkz3k!sU#f3o0plKXYlB*xL^7o*",
            login_url="/auth/create",
            debug=True
        )
        super(Application, self).__init__(handlers, **settings)

        self.maybe_create_tables()

    def create_session(self):
        """Create a database connection"""
        try:
            conn = sqlite3.connect(options.database)
            return conn
        except Error as e:
            print(e)
        # TODO: close connection
        return None

    @property
    def db(self):
        if self._db is None:
            self._db = self.create_session()
        return self._db

    def maybe_create_tables(self):
        try:
            self.db.cursor().execute("SELECT COUNT(*) from users;")
        except Error as e:
            print(e)
            print("Creating tables")
            self.db.cursor().execute("""
                CREATE TABLE IF NOT EXISTS users (
                  id integer PRIMARY KEY,
                  name text NOT NULL,
                  hashed_password text NOT NULL
                );""")
            self.db.cursor().execute("""
                CREATE TABLE IF NOT EXISTS docs (
                  id integer PRIMARY KEY,
                  file BLOB NOT NULL,
                  user_id integer NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users (id)
                );""")
            self.db.cursor().execute("""
                CREATE TABLE IF NOT EXISTS images (
                  id integer PRIMARY KEY,
                  doc_id integer NOT NULL,
                  image blob NOT NULL,
                  FOREIGN KEY (doc_id) REFERENCES docs (id)
                );""")


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    def get_current_user(self):
        user_id = self.get_secure_cookie("user")
        if not user_id:
            return None
        cursor = self.db.cursor().execute("""
            SELECT * FROM users WHERE id=?
            """, (int(user_id),))
        return cursor.fetchall()[0]


class HomeHandler(BaseHandler):
    def get(self):
        self.write("Hello, world")
        user_id = self.get_secure_cookie("user")
        if not user_id:
            return self.render("home.html")
        return self.render("home.html", user=self.get_current_user()[1])



class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_user.html")

    @gen.coroutine
    def post(self):
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt())
        cursor = self.db.cursor().execute(
            """INSERT INTO users(name, hashed_password)
            VALUES(?, ?)""", (self.get_argument("name"),
                              hashed_password),)
        self.db.commit()
        self.set_secure_cookie("user", str(cursor.lastrowid))
        self.redirect(self.get_argument("next", "/"))


class AuthLoginHandler(BaseHandler):
    def get(self):
        self.render("login.html", error=None)

    @gen.coroutine
    def post(self):
        cursor = self.db.cursor().execute("""
            SELECT * FROM users WHERE name=?
            """, (self.get_argument("name"),))
        user = cursor.fetchall()[0]
        password = user[2]
        print(user)
        print(password)

        if not user:
            self.render("login.html", error="user not found")
            return
        hashed_password = yield executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(password))
        if hashed_password == password:
            self.set_secure_cookie("user", str(user[0]))
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="incorrect password")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
