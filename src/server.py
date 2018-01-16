import db
import tornado.ioloop
import tornado.web
import os
import pdf
import config

from tornado.options import define, options
from tornado import gen
from tornado.log import logging

define("port", default=config.PORT, help="run on the given port", type=int)


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", HomeHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/auth/create", AuthCreateHandler),
            (r'/post', PostFileHandler),
            (r'/storage/pdf/(?P<hashed_name>[^\/]+)',
             PdfDownloadHandler, {'file_path': config.MEDIA_PDF}),
            (r'/storage/pdf/pages/(?P<hashed_name>[^\/]+)/?(?P<page>[^\/]+)',
             PngDownloadHandler, {'file_path': config.MEDIA_PAGES}),
        ]

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


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        logging.debug(self.get_secure_cookie("user"))
        return self.get_secure_cookie("user")

    def set_current_user(self, user_name):
        if user_name:
            self.set_secure_cookie("user", user_name)
        else:
            self.clear_cookie("user")

    async def data_received(self):
        logging.debug(self.request)


class HomeHandler(BaseHandler):
    def get(self):
        files = db.get_file_list()
        logging.info(files)
        return self.render("home.html",
                           files_list=files,
                           error=''
                           )


class PostFileHandler(BaseHandler):
    @gen.coroutine
    def post(self, *args, **kwargs):
        file_list = db.get_file_list()
        logging.debug(dir(self))
        for field, files in self.request.files.items():
            logging.info('POST {} {}'.format(field, files))
            for info in files:
                filename = info['filename']
                content_type = info['content_type']
                body = info['body']
                logging.info(
                    'POST {}: {} {} {} bytes'.
                    format(field, filename, content_type, len(body)))
                if content_type.lower() == 'application/pdf':
                    file = yield pdf.save_pdf_file(
                        body,
                        filename,
                        self.current_user.decode()
                    )
                    self.redirect('/')
                else:
                    self.render(
                        "home.html",
                        files_list=file_list,
                        error='expected pdf but received {}'.
                        format(content_type))


class PdfDownloadHandler(BaseHandler):
    def initialize(self, file_path):
        self.file_path = file_path

    @tornado.web.asynchronous
    @gen.engine
    def get(self, hashed_name):
        file_size = os.path.getsize(
            '{}/{}.pdf'.format(self.file_path, hashed_name))
        file_path = '{}/{}.pdf'.format(self.file_path, hashed_name)
        logging.info(
            'download handler: {} {} bytes'.format(file_path, str(file_size)))
        self.set_header('Content-Type', 'application/pdf')
        self.set_header('Content-length', file_size)
        self.flush()
        fd = open(file_path, 'rb')
        complete_download = False
        while not complete_download:
            data = fd.read(config.CHUNK_SIZE)
            logging.info('download chunk: {} bytes'.format(len(data)))
            if len(data) > 0:
                self.write(data)
                yield gen.Task(self.flush)
            complete_download = (len(data) == 0)
        fd.close()
        self.finish()


class PngDownloadHandler(BaseHandler):
    def initialize(self, file_path):
        self.file_path = file_path

    @tornado.web.asynchronous
    @gen.engine
    def get(self, hashed_name, **params):
        page = int(params['page']) if params['page'] else 1
        logging.info('page: {}'.format(page))

        file_path = '{}/{}{}.png'.format(self.file_path, hashed_name, page)
        file_size = os.path.getsize(file_path)
        self.set_header('Content-Type', 'application/png')
        self.set_header('Content-length', file_size)
        self.flush()
        fd = open(file_path, 'rb')
        complete_download = False
        while not complete_download:
            data = fd.read(config.CHUNK_SIZE)
            logging.info('download chunk: {} bytes'.format(len(data)))
            if len(data) > 0:
                self.write(data)
                yield gen.Task(self.flush)
            complete_download = (len(data) == 0)
        fd.close()
        self.finish()


class AuthCreateHandler(BaseHandler):
    def get(self):
        self.render("create_user.html", error=None)

    @gen.coroutine
    def post(self):
        name = self.get_argument("name")
        user_id = yield db.create_user(name, self.get_argument("password"))
        logging.debug('user_id: {}'.format(user_id))
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
        user = yield db.auth_user(user_name,
                                  self.get_argument("password"))
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
