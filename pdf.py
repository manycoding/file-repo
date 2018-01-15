import hashlib
import time
import os
from PyPDF2 import PdfFileReader
from tornado.log import logging
from tornado.gen import coroutine
from wand.image import Image
import db
import config


@coroutine
def get_pdf_filename(hashed_name):
    pdf_name = None
    pdf_file = yield db.get_pdf_by_hashed_name(hashed_name)
    pdf_file = pdf_file[0] if pdf_file else None
    if pdf_file:
        pdf_name = pdf_file['name']
    return pdf_name


@coroutine
def save_pdf_to_pngs(hashed_name):
    pdf_name = yield get_pdf_filename(hashed_name)
    page_urls = []
    pdf_file = f'{config.MEDIA_PDF}/{hashed_name}.pdf'
    images = Image(filename=pdf_file)
    for i, page in enumerate(images.sequence):
        png_file = f'{hashed_name}{i}.png'
        png_filepath = f'{config.MEDIA_PAGES}/{png_file}'
        with Image(page) as page_image:
            page_image.alpha_channel = False
            if not os.path.exists(png_filepath):
                page_image.save(filename=png_filepath)
            page_urls.append(png_filepath)

    logging.debug(f'save_pdf_file: saved images to {page_urls}')
    return page_urls


@coroutine
def save_pdf_file(body, pdf_name, user_name):
    hashed_name = hashlib.md5(f'{time.time()}'.encode()).hexdigest()
    with open(f'{config.MEDIA_PDF}/{hashed_name}.pdf', 'wb') as pdf:
        pdf.write(body)
    total_pages = PdfFileReader(f'{config.MEDIA_PDF}/{hashed_name}.pdf').getNumPages()
    pdf_data = yield db.insert_pdf(pdf_name, hashed_name, user_name, total_pages)
    logging.debug(f'save_pdf_file: {pdf_name} ({total_pages} pages) saved ({len(body)} bytes) in {hashed_name}.pdf')
    page_urls = yield save_pdf_to_pngs(hashed_name)

    return pdf_data
