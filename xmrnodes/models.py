from urllib.parse import urlparse
from datetime import datetime

from peewee import *

from xmrnodes import config


db = SqliteDatabase(f"{config.DATA_DIR}/sqlite.db")

class Node(Model):
    id = AutoField()
    url = CharField(unique=True)
    is_tor = BooleanField(default=False)
    available = BooleanField(default=False)
    validated = BooleanField(default=False)
    nettype = CharField(null=True)
    last_height = IntegerField(null=True)
    crypto = CharField(null=True)
    datetime_entered = DateTimeField(default=datetime.utcnow)
    datetime_checked = DateTimeField(default=None, null=True)
    datetime_failed = DateTimeField(default=None, null=True)
    fail_reason = CharField(null=True)

    class Meta:
        database = db

class Peer(Model):
    id = AutoField()
    url = CharField(unique=True)
    country = CharField(null=True)
    city = CharField(null=True)
    postal = IntegerField(null=True)
    lat = FloatField(null=True)
    lon = FloatField(null=True)
    datetime = DateTimeField(default=datetime.utcnow)

    def get_ip(self):
        return urlparse(self.url).hostname

    class Meta:
        database = db

class HealthCheck(Model):
    id = AutoField()
    node = ForeignKeyField(Node, backref='healthchecks')
    datetime = DateTimeField(default=datetime.utcnow)
    health = BooleanField()

    class Meta:
        database = db

db.create_tables([Node, HealthCheck, Peer])
