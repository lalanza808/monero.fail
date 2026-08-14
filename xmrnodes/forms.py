from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired


class SubmitNode(FlaskForm):
    node_url = StringField(
        "",
        validators=[DataRequired()],
        render_kw={"placeholder": "Node URL - proto://hostname:port (http://hostname:18081, http://ipv4:18081, http://[ipv6]:18081)"},
    )
