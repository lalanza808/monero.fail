from peewee import *
from datetime import datetime
from xmrnodes import config


data_dir = getattr(config, 'DATA_FOLDER', './data')
db = SqliteDatabase(f"{data_dir}/sqlite.db")

class Node(Model):
    id = AutoField()
    url = CharField()
    is_tor = BooleanField(default=False)
    available = BooleanField(default=False)
    validated = BooleanField(default=False)
    nettype = CharField(null=True)
    is_monero = BooleanField(default=False)
    datetime_entered = DateTimeField(default=datetime.now)
    datetime_checked = DateTimeField(default=None, null=True)
    datetime_failed = DateTimeField(default=None, null=True)

    class Meta:
        database = db

db.create_tables([Node])
