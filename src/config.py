import os


APP_PATH = os.path.dirname(__file__)
MEDIA = os.path.join(APP_PATH, 'storage')
MEDIA_PDF = os.path.join(MEDIA, 'pdf')
MEDIA_PAGES = os. path.join(MEDIA_PDF, 'pages')
CHUNK_SIZE = 524288
PORT = 8888
