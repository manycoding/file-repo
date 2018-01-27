import hashlib
import time
import os
from tornado.log import logging
from tornado.gen import coroutine
from wand.image import Image
from wand import exceptions
import db
import config


@coroutine
def get_pdf_filename(hashed_name):
    pdf_name = None
    pdf_file = db.get_pdf_by_hashed_name(hashed_name)
    pdf_file = pdf_file[0] if pdf_file else None
    if pdf_file:
        pdf_name = pdf_file['name']
    return pdf_name


@coroutine
def save_pdf_to_pngs(hashed_name):
    pdf_name = yield get_pdf_filename(hashed_name)
    page_urls = []
    pdf_file = '{}/{}.pdf'.format(config.MEDIA_PDF, hashed_name)
    try:
        with Image(filename=pdf_file) as images:
            for i, page in enumerate(images.sequence):
                png_file = '{}{}.png'.format(hashed_name, i)
                png_filepath = '{}/{}'.format(config.MEDIA_PAGES, png_file)
                with Image(page) as page_image:
                    page_image.alpha_channel = False
                    if not os.path.exists(png_filepath):
                        page_image.save(filename=png_filepath)
                    page_urls.append(png_filepath)

    except exceptions.CacheError as e:
        logging.error(e)
    logging.debug('save_pdf_to_pngs: saved images to {}'.format(page_urls))
    return page_urls


@coroutine
def save_pdf_file(body, pdf_name, user_name):
    hashed_name = hashlib.md5(str(time.time()).encode()).hexdigest()
    file_path = '{}/{}.pdf'.format(config.MEDIA_PDF, hashed_name)
    with open(file_path, 'wb') as pdf:
        pdf.write(body)
    page_urls = yield save_pdf_to_pngs(hashed_name)
    total_pages = len(page_urls)
    pdf_data = db.insert_pdf(pdf_name, hashed_name, user_name, total_pages)
    logging.debug('save_pdf_file: {} ({} pages) saved ({} bytes) in {}.pdf'.format(pdf_name, total_pages, len(body), hashed_name)) # noqa

    return pdf_data
