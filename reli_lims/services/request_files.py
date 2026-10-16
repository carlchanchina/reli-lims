"""Private photo provenance for a customer testing request."""
from pathlib import PurePosixPath

import frappe
from frappe import _


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff'}


def photo_file(request, url):
    name = frappe.db.get_value('File', dict(file_url=url, is_private=1,
        attached_to_doctype='Test Request', attached_to_name=request.name), 'name')
    if not name or PurePosixPath(url).suffix.lower() not in IMAGE_EXTENSIONS:
        frappe.throw(_('Attach sample photos privately to this testing request.'))
    file = frappe.get_doc('File', name)
    file.check_permission('read')
    return file


def validate_photos(request):
    for row in request.photos:
        photo_file(request, row.photo)


def copy_sample_photos(request, sample_code, sample):
    for row in request.photos:
        if row.sample_code != sample_code:
            continue
        source = photo_file(request, row.photo)
        frappe.get_doc(dict(doctype='File', file_name=source.file_name, is_private=1,
            content=source.get_content(), attached_to_doctype='Sample',
            attached_to_name=sample.name)).insert()
