"""Translate presentation errors without changing pure validation contracts."""
from frappe import _


def scope_error_message(error):
    message = str(error)
    prefix = "Receive these samples first: "
    if message.startswith(prefix):
        return _('请先接收以下样品：{0}').format(message.removeprefix(prefix))
    return _(message, lang='zh')
