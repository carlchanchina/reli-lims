"""Native File copy regression for receiving; no business records are saved."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe

from reli_lims.request_confirmation import validate_file_visibility
from reli_lims.services.request_files import copy_sample_photos


class TestFileVisibilityCopy(unittest.TestCase):
    def test_shared_request_attachment_copy_does_not_inherit_customer_grant(self):
        source = frappe.get_doc({
            'doctype': 'File',
            'file_name': 'TEST-receiving-copy.png',
            'file_url': '/private/files/TEST-receiving-copy.png',
            'is_private': 1,
            'attached_to_doctype': 'Test Request',
            'attached_to_name': 'TEST-SOURCE-REQUEST',
            'reli_customer_visible': 1,
        })
        request = SimpleNamespace(photos=[SimpleNamespace(
            sample_code='TEST-S1', photo=source.file_url)])
        sample = SimpleNamespace(name='TEST-RECEIVED-SAMPLE')
        copies = []

        def inspect_insert(document, **kwargs):
            validate_file_visibility(document)
            copies.append(document)
            return document

        with patch('reli_lims.services.request_files.photo_file', return_value=source):
            with patch.object(type(source), 'insert', new=inspect_insert):
                copy_sample_photos(request, 'TEST-S1', sample)

        self.assertEqual(len(copies), 1)
        copied = copies[0]
        self.assertFalse(copied.get('reli_customer_visible'))
        self.assertEqual(source.get('reli_customer_visible'), 1)
        self.assertEqual(copied.is_private, 1)
        self.assertEqual(copied.file_url, source.file_url)
        self.assertEqual(copied.attached_to_doctype, 'Sample')
        self.assertEqual(copied.attached_to_name, sample.name)
