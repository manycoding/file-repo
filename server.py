import db
import sqlite3
import tornado.ioloop
import tornado.web
import os
# import pdf

from sqlite3 import Error
from tornado.options import define, options
from tornado import gen
from tornado.log import logging

define("port", default=8888, help="run on the given port", type=int)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/auth/create", AuthCreateHandler),
            (r'/post', PostFile),
            # (r'/pdf/(?P<hashed_name>[^\/]+)/?(?P<page>[^\/]+)?', Preview),
            # (r'/media/pdf/(?P<hashed_name>[^\/]+)', handlers.PdfFileStreamDownload, {'file_path': settings.MEDIA_PDF}),
            # (r'/media/png/(?P<hashed_name>[^\/]+)/?(?P<page>[^\/]+)', handlers.PngFileStreamDownload, {'file_path': settings.MEDIA_PAGES}),
            # (r'/pages/(.*)', StaticFileHandler, {'path': f'{settings.MEDIA_PAGES}'}),
        ]
        self._db = None

        settings = dict(
            blog_title=u"File repo",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            cookie_secret="oLGcDzgWH^5^$M77DS8mkOHNZ@$yO3pu1W6^Sy&s7jHreFUdGsy5EvkEIbKN%Q6^0qyr6J@u0Vkz3k!sU#f3o0plKXYlB*xL^7o*",
            login_url="/auth/create",
            debug=True
        )
        super(Application, self).__init__(handlers, **settings)

    def create_session(self):
        """Create a database connection"""
        try:
            conn = sqlite3.connect(options.database)
            return conn
        except Error as e:
            logging.debug(e)
        # TODO: close connection
        return None

    @property
    def db(self):
        if self._db is None:
            self._db = self.create_session()
        return self._db


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.db

    def get_current_user(self):
        logging.debug(f'{self.get_secure_cookie("user")}')
        return self.get_secure_cookie("user")

    def set_current_user(self, user_name):
        if user_name:
            self.set_secure_cookie("user", user_name)
        else:
            self.clear_cookie("user")

    async def data_received(self):
        logging.debug(f'{self.request}')


class HomeHandler(BaseHandler):
    @gen.coroutine
    def get(self):
        files = yield db.get_file_list()
        files = None
        logging.debug(files)
        return self.render("home.html",
                           files_list=files,
                           error_message=''
                           )


class PostFile(BaseHandler):
    @gen.coroutine
    def post(self, *args, **kwargs):
        logging.debug(f'dir(self)')
        for field, files in self.request.files.items():
            logging.info(f'POST {field} {files}')
            for info in files:
                filename = info['filename']
                content_type = info['content_type']
                body = info['body']
                logging.info(
                    f'POST {field}: {filename} {content_type} {len(body)} bytes')
                if content_type.lower() == 'application/pdf':
                    file = yield pdf_utils.save_pdf_file(body,
                                                         filename,
                                                         self.current_user
                                                         )
        self.redirect('/')


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_user.html", error=None)

    @gen.coroutine
    def post(self):
        name = self.get_argument("name")
        user_id = yield db.create_user(name, self.get_argument("password"))

        if user_id:
            self.set_current_user(name)
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("create_user.html", error="""
                could not create user with such name and password
                """)


class AuthLoginHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.redirect(self.get_argument('next', '/'))
        else:
            self.render("login.html", error=None)

    @gen.coroutine
    def post(self):
        user_name = self.get_argument("name")
        user = yield db.get_user(user_name,
                                 self.get_argument("password"))
        user = user[0] if user else None

        if user:
            self.set_current_user(user_name)
            self.redirect(self.get_argument("next", "/"))
        else:
            self.render("login.html", error="""
                user with such name and password was not found
                """)


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.redirect(self.get_argument("next", "/"))


def main():
    db.init()
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
