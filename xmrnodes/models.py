from urllib.parse import urlparse
from statistics import mean
from datetime import datetime

from peewee import *
from playhouse.sqliteq import SqliteQueueDatabase

from xmrnodes import config


db = SqliteQueueDatabase(f"{config.DATA_DIR}/sqlite.db")


class Node(Model):
    id = AutoField()
    url = CharField(unique=True)
    is_tor = BooleanField(default=False)
    is_i2p = BooleanField(default=False)
    available = BooleanField(default=False)
    validated = BooleanField(default=False)
    web_compatible = BooleanField(default=False)
    nettype = CharField(null=True)
    last_height = IntegerField(null=True)
    crypto = CharField(null=True)
    donation_address = CharField(null=True)
    country_name = CharField(null=True)
    country_code = CharField(null=True)
    city = CharField(null=True)
    postal = IntegerField(null=True)
    lat = FloatField(null=True)
    lon = FloatField(null=True)
    asn = CharField(null=True)
    asn_cidr = CharField(null=True)
    asn_country_code = CharField(null=True)
    asn_description = CharField(null=True)
    datetime_entered = DateTimeField(default=datetime.utcnow)
    datetime_checked = DateTimeField(default=None, null=True)
    datetime_failed = DateTimeField(default=None, null=True)
    fail_reason = CharField(null=True)

    def get_netloc(self):
        _url = urlparse(self.url)
        return _url.netloc

    def get_failed_checks(self):
        hcs = HealthCheck.select().where(
            HealthCheck.node == self, HealthCheck.health == False
        )
        return hcs

    def get_all_checks(self):
        hcs = HealthCheck.select().where(HealthCheck.node == self)
        return hcs
    
    @property
    def uptime(self):
        hcs = self.healthchecks
        ups = [1 for i in hcs if i.health == True]
        downs = [0 for i in hcs if i.health == False]
        if (len(ups + downs)):
            m = mean(ups + downs)
            return int(m * 100)
        return 0

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

    def hours_elapsed(self):
        now = datetime.utcnow()
        diff = now - self.datetime
        return diff.total_seconds() / 60 / 60

    def get_ip(self):
        return urlparse(self.url).hostname

    class Meta:
        database = db


class HealthCheck(Model):
    id = AutoField()
    node = ForeignKeyField(Node, backref="healthchecks")
    datetime = DateTimeField(default=datetime.utcnow)
    health = BooleanField()

    @property
    def color(self):
        return 'green' if self.health else 'red'

    class Meta:
        database = db


db.create_tables([Node, HealthCheck, Peer])
