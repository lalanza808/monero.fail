from datetime import datetime

import arrow
from flask import Blueprint
from urllib.parse import urlencode

bp = Blueprint("filters", "filters")


@bp.app_template_filter("humanize")
def humanize(d):
    t = arrow.get(d, "UTC")
    return t.humanize()


@bp.app_template_filter("hours_elapsed")
def hours_elapsed(d):
    now = datetime.utcnow()
    diff = now - d
    return diff.total_seconds() / 60 / 60


@bp.app_template_filter("pop_arg")
def trim_arg(all_args, arg_to_trim):
    d = all_args.to_dict()
    d.pop(arg_to_trim)
    return urlencode(d)


@bp.app_template_filter("seems_legit")
def seems_legit(addy):
    if type(addy) is str:
        return len(addy) == 97
    return False