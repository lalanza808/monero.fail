from peewee import *
from datetime import datetime
from xmrnodes import config


data_dir = getattr(config, 'DATA_FOLDER', './data')
db = SqliteDatabase(f"{data_dir}/db/sqlite.db")

class Node(Model):
    id = AutoField()
    scheme = CharField()
    address = CharField()
    port = IntegerField()
    version = CharField(null=True)
    tor = BooleanField(default=False)
    available = BooleanField(default=False)
    mainnet = BooleanField(default=False)
    datetime_entered = DateTimeField(default=datetime.now)
    datetime_checked = DateTimeField(default=datetime.now)
    datetime_failed = DateTimeField(default=None, null=True)

    class Meta:
        database = db

db.create_tables([Node])
