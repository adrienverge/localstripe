import random
import hashlib
import string


def random_id(n):
    return ''.join(random.choice(string.ascii_letters + string.digits)
                   for i in range(n))


def fingerprint(s: str):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:16]


def try_convert_to_bool(arg):
    if type(arg) is str:
        if arg.lower() == 'false':
            return False
        elif arg.lower() == 'true':
            return True
    return arg


def try_convert_to_int(arg):
    if type(arg) == int:
        return arg
    elif type(arg) in (str, float):
        try:
            return int(arg)
        except ValueError:
            pass
    return arg


def try_convert_to_float(arg):
    if type(arg) == float:
        return arg
    elif type(arg) in (str, int):
        try:
            return float(arg)
        except ValueError:
            pass
    return arg
