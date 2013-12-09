# coding=utf-8
__author__ = "Gareth Coles"

import ctypes
import logging
import logging.handlers
import sys
import os


logging.basicConfig(
    level=(logging.DEBUG if "--debug" in sys.argv else logging.INFO),
    format="%(asctime)s | %(name)10s | %(levelname)8s | %(message)s",
    datefmt="%d %b %Y - %H:%M:%S")

loggers = {}


class ColorizingStreamHandler(logging.StreamHandler):
    # Modified version from http://bit.ly/18vOxNU
    color_map = {
        'black': 0,
        'red': 1,
        'green': 2,
        'yellow': 3,
        'blue': 4,
        'magenta': 5,
        'cyan': 6,
        'white': 7,
    }

    # levels to (background, foreground, bold/intense)
    if os.name == 'nt':
        level_map = {
            logging.DEBUG: (None, 'blue', True),
            logging.INFO: (None, 'white', False),
            logging.WARNING: (None, 'yellow', True),
            logging.ERROR: (None, 'red', True),
            logging.CRITICAL: ('red', 'white', True),
        }
    else:
        level_map = {
            logging.DEBUG: (None, 'blue', False),
            logging.INFO: (None, 'black', False),
            logging.WARNING: (None, 'yellow', False),
            logging.ERROR: (None, 'red', False),
            logging.CRITICAL: ('red', 'white', True),
        }
    csi = '\x1b['
    reset = '\x1b[0m'

    @property
    def is_tty(self):
        isatty = getattr(self.stream, 'isatty', None)
        return isatty and isatty()

    def emit(self, record):
        try:
            message = self.format(record)
            stream = self.stream
            if not self.is_tty:
                stream.write(message)
            else:
                self.output_colorized(message)
            stream.write(getattr(self, 'terminator', '\n'))
            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    if os.name != 'nt':
        def output_colorized(self, message):
            self.stream.write(message)
    else:
        import re
        ansi_esc = re.compile(r'\x1b\[((?:\d+)(?:;(?:\d+))*)m')

        nt_color_map = {
            0: 0x00,    # black
            1: 0x04,    # red
            2: 0x02,    # green
            3: 0x06,    # yellow
            4: 0x01,    # blue
            5: 0x05,    # magenta
            6: 0x03,    # cyan
            7: 0x07,    # white
        }

        def output_colorized(self, message):
            parts = self.ansi_esc.split(message)
            write = self.stream.write
            h = None
            fd = getattr(self.stream, 'fileno', None)
            if fd is not None:
                fd = fd()
                if fd in (1, 2):  # stdout or stderr
                    h = ctypes.windll.kernel32.GetStdHandle(-10 - fd)
            while parts:
                text = parts.pop(0)
                if text:
                    write(text)
                if parts:
                    params = parts.pop(0)
                    if h is not None:
                        params = [int(p) for p in params.split(';')]
                        color = 0
                        for p in params:
                            if 40 <= p <= 47:
                                color |= self.nt_color_map[p - 40] << 4
                            elif 30 <= p <= 37:
                                color |= self.nt_color_map[p - 30]
                            elif p == 1:
                                color |= 0x08  # foreground intensity on
                            elif p == 0:  # reset to default color
                                color = 0x07
                            else:
                                pass  # error condition ignored
                        ctypes.windll.kernel32.SetConsoleTextAttribute(h,
                                                                       color)

    def colorize(self, message, record):
        if record.levelno in self.level_map:
            bg, fg, bold = self.level_map[record.levelno]
            params = []
            if bg in self.color_map:
                params.append(str(self.color_map[bg] + 40))
            if fg in self.color_map:
                params.append(str(self.color_map[fg] + 30))
            if bold:
                params.append('1')
            if params:
                message = ''.join((self.csi, ';'.join(params),
                                   'm', message, self.reset))
        return message

    def format(self, record):
        message = logging.StreamHandler.format(self, record)
        if self.is_tty:
            message = self.colorize(message, record)
        return message


def getLogger(name, path=None,
              fmt="%(asctime)s | %(name)10s | %(levelname)8s | %(message)s",
              datefmt="%d %b %Y - %H:%M:%S", displayname=None):

    if displayname is None:
        displayname = name

    if name in loggers:
        return loggers[name]
    logger = logging.getLogger(displayname)
    logger.propagate = False

    chandler = ColorizingStreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s | %(name)10s | %(levelname)8s | %(message)s")
    formatter.datefmt = datefmt
    chandler.setFormatter(formatter)
    chandler.setLevel(logging.DEBUG if "--debug" in sys.argv else logging.INFO)

    logger.addHandler(chandler)
    del formatter

    if path:
        path = path.replace("..", "")
        path = "logs/" + path
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        handler = logging.FileHandler(path)
        formatter = logging.Formatter(fmt)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        del handler

    handler = logging.FileHandler("logs/output.log")
    formatter = logging.Formatter(
        "%(asctime)s | %(name)10s | %(levelname)8s | %(message)s")
    formatter.datefmt = datefmt
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG if "--debug" in sys.argv else logging.INFO)

    logger.addHandler(handler)

    del handler

    logger.debug("Created logger.")

    loggers[name] = logger

    return logger


def open_log(path):
    path = path.replace("..", "")
    path = "logs/" + path
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))

    logger = logging.getLogger("Logging")

    logger.propagate = False

    handler = logging.FileHandler(path)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)10s | %(levelname)8s | %(message)s")
    formatter.datefmt = "%d %b %Y - %H:%M:%S"
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG if "--debug" in sys.argv else logging.INFO)
    logger.addHandler(handler)

    logger.info("*** LOGFILE OPENED: %s ***" % path)

    logger.removeHandler(handler)

    del handler
    del logger


def close_log(path):
    path = path.replace("..", "")
    path = "logs/" + path
    if not os.path.exists(os.path.dirname(path)):
        return

    logger = logging.getLogger("Logging")

    logger.propagate = False

    handler = logging.FileHandler(path)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)10s | %(levelname)8s | %(message)s")
    formatter.datefmt = "%d %b %Y - %H:%M:%S"
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG if "--debug" in sys.argv else logging.INFO)
    logger.addHandler(handler)

    logger.info("*** LOGFILE CLOSED: %s ***\n\n" % path)
    logger.removeHandler(handler)

    del handler
    del logger
