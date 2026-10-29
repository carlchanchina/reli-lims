"""Escaped file HTML through Frappe's native wkhtmltopdf pipeline."""
from html import escape


def table(columns, rows):
    head = ''.join(f'<th>{escape(str(c))}</th>' for c in columns)
    body = ''.join('<tr>' + ''.join(f'<td>{escape(str(c if c is not None else ""))}</td>' for c in row) + '</tr>' for row in rows)
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def render(spec, context):
    from frappe.utils.pdf import get_pdf
    values = {key: escape(str(context.get(key) or '')) for key in ('title', 'name', 'notice')}
    values['fields'] = table(['项目', '内容'], context['fields'])
    values['items'] = table(context['columns'], context['rows'])
    values['sections'] = ''.join(f'<h2>{escape(section["title"])}</h2>' + table(section['columns'], section['rows'])
                                 for section in context.get('sections', []))
    if context.get('terms'):
        values['sections'] += '<h2>报价条款</h2><p>' + escape(context['terms']) + '</p>'
    html = (spec.directory / f'{spec.key}.html').read_text()
    for key, value in values.items():
        html = html.replace('{{' + key + '}}', value)
    return get_pdf(html, options={'page-size': 'A4', 'encoding': 'UTF-8',
                                 'margin-top': '15mm', 'margin-bottom': '15mm'})
