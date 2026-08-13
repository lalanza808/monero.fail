from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


class SubmitNode(FlaskForm):
    node_url = StringField(
        "",
        validators=[DataRequired()],
        render_kw={"placeholder": "Node URL (http://host:18081 or http://[ipv6]:18081)"},
    )
