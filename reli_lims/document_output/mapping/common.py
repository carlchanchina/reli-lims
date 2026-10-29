"""Plain values only: no HTML, raw file links, or internal notes in deliverables."""
from html.parser import HTMLParser


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ('br', 'p', 'div', 'li'):
            self.parts.append('\n')


def text(value) -> str:
    return '' if value is None else str(value)


def plain(value) -> str:
    parser = PlainText()
    parser.feed(text(value))
    return ''.join(parser.parts).strip()


def context(title, doc, fields, columns, rows, notice='', sections=None):
    return dict(title=title, name=text(doc.get('name')), notice=notice,
                fields=[[label, text(value)] for label, value in fields],
                columns=columns, rows=[[text(v) for v in row] for row in rows],
                sections=sections or [])
