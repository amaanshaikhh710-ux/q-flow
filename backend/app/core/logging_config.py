import logging
import re

class SanitizingFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        msg = re.sub(r'(?i)(bearer\s+)[A-Za-z0-9-_=.]+', r'\g<1>[REDACTED]', msg)
        msg = re.sub(r'(?i)(token=)[^&\s]+', r'\g<1>[REDACTED]', msg)
        msg = re.sub(r'(?i)(password\s*[:=]\s*)[^\s,]+', r'\g<1>[REDACTED]', msg)
        msg = re.sub(r'AIza[0-9A-Za-z-_]{35}', r'[REDACTED_KEY]', msg)
        return msg

def setup_logging(is_production=False):
    level = logging.INFO if is_production else logging.DEBUG
    handler = logging.StreamHandler()
    fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    handler.setFormatter(SanitizingFormatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(level)
    root.addHandler(handler)
