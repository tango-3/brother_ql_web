#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This is a web service to print labels on Brother QL label printers.
"""

import argparse
import json
import logging
import random
import sys
import time
from io import BytesIO
from subprocess import PIPE, Popen

from bottle import get
from bottle import jinja2_view as view
from bottle import post, redirect, request, response, route, run, static_file
from brother_ql import BrotherQLRaster, create_label
from brother_ql.backends import backend_factory, guess_backend
from brother_ql.devicedependent import (DIE_CUT_LABEL, ENDLESS_LABEL,
                                        ROUND_DIE_CUT_LABEL, label_sizes,
                                        label_type_specs, models)
from PIL import Image, ImageDraw, ImageFont

from firestore import Firestore
from font_helpers import get_fonts

logger = logging.getLogger(__name__)

LABEL_SIZES = [ (name, label_type_specs[name]['name']) for name in label_sizes]

try:
    with open('config.json', encoding='utf-8') as fh:
        CONFIG = json.load(fh)
except FileNotFoundError as e:
    with open('config.example.json', encoding='utf-8') as fh:
        CONFIG = json.load(fh)

def git_version():
    gitproc = Popen(['git', 'rev-parse', 'HEAD'],
                    stdout=PIPE)
    (stdout, _) = gitproc.communicate()
    version = stdout.strip()
    logger.debug("Git Version {}".format(version))
    return version.decode("utf-8") 

def git_branch():
    gitproc = Popen(['git', 'symbolic-ref', '--short', 'HEAD'],
                    stdout=PIPE)
    (stdout, _) = gitproc.communicate()
    branch = stdout.strip()
    logger.debug("Git Branch {}".format(branch))
    return branch.decode("utf-8") 

def get_serial():
    # Extract serial from cpuinfo file
    cpuserial = "0000000000000000"
    try:
        f = open('/proc/cpuinfo','r')
        for line in f:
            if line[0:6]=='Serial':
                cpuserial = line[10:26]
        f.close()
    except:
        cpuserial = "ERROR000000000"
    logger.debug("Cpu Serial {}".format(cpuserial))
    return cpuserial

def print_label(data):
    try:
        logger.debug("recieved data: {}".format(data))
        font_path = FONTS['DejaVu Sans Mono']['Book']
        title_font_path = FONTS['DejaVu Sans Mono']['Bold']
        title_font = ImageFont.truetype(title_font_path, 32)
        im_font = ImageFont.truetype(font_path, 30)
        
        lines = []
        for line in data['homeAddress'].split('\n'):
            if line == '': line = ' '
            lines.append(line)
        
        lines.append(data['postcode'].upper())
        if 'phone' in data:
            lines.append("TEL: {}".format(data['phone']))
        if 'dob' in data:
            lines.append("DOB: {}".format(data['dob']))
        if 'doctor' in data:
            lines.append("DOCTOR: {}".format(data['doctor']))
        else:
            lines.append("DOCTOR: NKGP")
        if 'test' in data and 'appointmentDate' in data:
            lines.append("{} TEST DATE: {}".format(data['test'], data['appointmentDate']))
        text = '\n'.join(lines)

        im = Image.new('L', (20, 20), 'white')
        draw = ImageDraw.Draw(im)

        footer = ""
        if 'contract' in data and data['contract'] == 'RCHT-Patient':
            footer = "RCHT MAXIMS PATIENT: {}\nCONSULTANT: {}".format(data['referringDepartment'], data['referrerName'])

        title_text_size = draw.multiline_textsize(data['testForName'].upper(), font=title_font)
        body_text_size = draw.multiline_textsize(text, font=im_font)
        foot_text_size = draw.multiline_textsize(footer, font=title_font)

        width = 696
        height = body_text_size[1] + title_text_size[1] + foot_text_size[1] + 20
        im = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(im)


        offset = 5, 0
        color = (0, 0, 0)
        draw.multiline_text(offset, data['testForName'].upper(), color, title_font, 'left')
        offset = 5, title_text_size[1]
        draw.multiline_text(offset, text, color, im_font, 'left')
        offset = 5, title_text_size[1] + body_text_size[1]
        draw.multiline_text(offset,footer, color, title_font, 'left')
        im.save('sample-out.png')

        qlr = BrotherQLRaster(CONFIG['PRINTER']['MODEL'])

        create_label(qlr, im, '62', red=False, threshold=70, cut=True, rotate=0)

        try:
            be = BACKEND_CLASS(CONFIG['PRINTER']['PRINTER'])
            be.write(qlr.data)
            be.write(qlr.data)
            be.dispose()
            del be
        except Exception as e:
            logger.warning('Exception happened: %s', e)

    except Exception as e:
        logger.error(e)

def main():
    try:
        global DEBUG, FONTS, BACKEND_CLASS, CONFIG
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--port', default=False)
        parser.add_argument('--loglevel', type=lambda x: getattr(logging, x.upper()), default=False)
        parser.add_argument('--font-folder', default=False, help='folder for additional .ttf/.otf fonts')
        parser.add_argument('--default-label-size', default=False, help='Label size inserted in your printer. Defaults to 62.')
        parser.add_argument('--default-orientation', default=False, choices=('standard', 'rotated'), help='Label orientation, defaults to "standard". To turn your text by 90°, state "rotated".')
        parser.add_argument('--model', default=False, choices=models, help='The model of your printer (default: QL-500)')
        parser.add_argument('printer',  nargs='?', default=False, help='String descriptor for the printer to use (like tcp://192.168.0.23:9100 or file:///dev/usb/lp0)')
        args = parser.parse_args()

        if args.printer:
            CONFIG['PRINTER']['PRINTER'] = args.printer

        if args.port:
            PORT = args.port
        else:
            PORT = CONFIG['SERVER']['PORT']

        if args.loglevel:
            LOGLEVEL = args.loglevel
        else:
            LOGLEVEL = CONFIG['SERVER']['LOGLEVEL']

        if LOGLEVEL == 'DEBUG':
            DEBUG = True
        else:
            DEBUG = False

        if args.model:
            CONFIG['PRINTER']['MODEL'] = args.model

        if args.default_label_size:
            CONFIG['LABEL']['DEFAULT_SIZE'] = args.default_label_size

        if args.default_orientation:
            CONFIG['LABEL']['DEFAULT_ORIENTATION'] = args.default_orientation

        if args.font_folder:
            ADDITIONAL_FONT_FOLDER = args.font_folder
        else:
            ADDITIONAL_FONT_FOLDER = CONFIG['SERVER']['ADDITIONAL_FONT_FOLDER']


        logging.basicConfig(level=LOGLEVEL)

        try:
            selected_backend = guess_backend(CONFIG['PRINTER']['PRINTER'])
        except ValueError:
            parser.error("Couln't guess the backend to use from the printer string descriptor")
        BACKEND_CLASS = backend_factory(selected_backend)['backend_class']

        if CONFIG['LABEL']['DEFAULT_SIZE'] not in label_sizes:
            parser.error("Invalid --default-label-size. Please choose on of the following:\n:" + " ".join(label_sizes))

        FONTS = get_fonts()
        if ADDITIONAL_FONT_FOLDER:
            FONTS.update(get_fonts(ADDITIONAL_FONT_FOLDER))

        if not FONTS:
            sys.stderr.write("Not a single font was found on your system. Please install some or use the \"--font-folder\" argument.\n")
            sys.exit(2)

        for font in CONFIG['LABEL']['DEFAULT_FONTS']:
            try:
                FONTS[font['family']][font['style']]
                CONFIG['LABEL']['DEFAULT_FONTS'] = font
                logger.debug("Selected the following default font: {}".format(font))
                break
            except: pass
        if CONFIG['LABEL']['DEFAULT_FONTS'] is None:
            sys.stderr.write('Could not find any of the default fonts. Choosing a random one.\n')
            family =  random.choice(list(FONTS.keys()))
            style =   random.choice(list(FONTS[family].keys()))
            CONFIG['LABEL']['DEFAULT_FONTS'] = {'family': family, 'style': style}
            sys.stderr.write('The default font is now set to: {family} ({style})\n'.format(**CONFIG['LABEL']['DEFAULT_FONTS']))

        serial = get_serial()
        version = git_version()
        branch = git_branch()
        firestore = Firestore()
        while firestore is None:
            try:
                firestore.connect(serial, branch, version)
                firestore.listen(print_label)
            except Exception as e:
                logger.error(e)
                time.sleep(5)

        while True:
            try:
                firestore.ping()
                time.sleep(5)
            except Exception as e:
                logger.error(e)
                try:
                    firestore.close()
                except: pass
                firestore.connect(serial, branch, version)
                firestore.listen(print_label)
        #run(host=CONFIG['SERVER']['HOST'], port=PORT, debug=DEBUG)

    except KeyboardInterrupt:
        firestore.close()


if __name__ == "__main__":
    main()
