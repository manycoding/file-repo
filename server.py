import bcrypt
import concurrent.futures
import sqlite3
import tornado.ioloop
import tornado.web
import os

from sqlite3 import Error
from tornado.options import define, options

define("port", default=8888, help="run on the given port", type=int)
# define("mysql_host", default="127.0.0.1:3306", help="blog database host")
define("database", default="file-repo.sqlite3", help="database name")
# define("mysql_user", default="blog", help="blog database user")
# define("mysql_password", default="blog", help="blog database password")


# A thread pool to be used for password hashing with bcrypt.
executor = concurrent.futures.ThreadPoolExecutor(2)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/login", AuthLoginHandler),
            (r"/logout", AuthLogoutHandler),
            (r"/create", AuthCreateHandler),
        ]
        self._db = None

        settings = dict(
            blog_title=u"File repo",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            # ui_modules={"Entry": EntryModule},
            xsrf_cookies=True,
            cookie_secret="oLGcDzgWH^5^$M77DS8mkOHNZ@$yO3pu1W6^Sy&s7jHreFUdGsy5EvkEIbKN%Q6^0qyr6J@u0Vkz3k!sU#f3o0plKXYlB*xL^7o*",
            login_url="/login",
            debug=True
        )
        super(Application, self).__init__(handlers, **settings)

        self.maybe_create_tables()

    def create_session(self):
        """Create a database connection"""
        try:
            conn = sqlite3.connect(options.database)
            print(sqlite3.version)
            return conn.cursor()
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
            self.db.execute("SELECT COUNT(*) from users;")
        except Error as e:
            print(e)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                  id integer PRIMARY KEY,
                  name text NOT NULL,
                  hashed_password text NOT NULL
                );""")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS docs (
                  id integer PRIMARY KEY,
                  file blob NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users (id)
                );""")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS images (
                  id integer PRIMARY KEY,
                  image blob NOT NULL,
                  FOREIGN KEY (doc_id) REFERENCES docs (id)
                );""")


# class MainHandler(tornado.web.RequestHandler):
#     @tornado.web.authenticated
#     def get(self):
#         name = tornado.escape.xhtml_escape(self.current_user)
#         self.write("Hello, " + name)


# class LoginHandler(tornado.web.RequestHandler):
#     def get(self):
#         self.write('<html><body><form action="/login" method="post">'
#                    'Name: <input type="text" name="name">'
#                    '<input type="submit" value="Sign in">'
#                    '</form></body></html>')

#     def post(self):
#         self.set_secure_cookie("user", self.get_argument("name"))
#         self.redirect("/")


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    def get_current_user(self):
        user_id = self.get_secure_cookie("demo_user")
        if not user_id:
            return None
        return self.db.execute("""
            SELECT * FROM users where id = %s
            """, int(user_id))


class HomeHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        name = tornado.escape.xhtml_escape(self.current_user)
        self.write("Hello, " + name)


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_id.html")

    async def post(self):
        hashed_password = await executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            bcrypt.gensalt())
        user_id = self.db.execute(
            """INSERT INTO users(name, hashed_password)
            VALUES(?, ?)""", (self.get_argument("name"),
                              hashed_password),)
        self.set_secure_cookie("demo_user", str(user_id))
        self.redirect(self.get_argument("next", "/"))


class AuthLoginHandler(BaseHandler):
    def get(self):
        self.render("login.html", error=None)

    async def post(self):
        user = self.db.execute("""
            SELECT * FROM users WHERE name=?
            """, (self.get_argument("name"),))

        if not user:
            self.render("login.html", error="user not found")
            return
        hashed_password = await executor.submit(
            bcrypt.hashpw, tornado.escape.utf8(self.get_argument("password")),
            tornado.escape.utf8(user.hashed_password))
        if hashed_password == user.hashed_password:
            self.set_secure_cookie("demo_user", str(user.id))
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="incorrect password")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("demo_user")
        self.redirect(self.get_argument("next", "/"))


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
