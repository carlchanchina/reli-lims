"""Private CNAS intake adapter over existing Documents packages and review.

Internal functions are called by the authenticated Bridge gateway. Only an
approved structured Documents version can become an immutable Capability Source.
"""
import base64
import binascii
import hashlib
import json
import ipaddress
from urllib.parse import urlsplit
from pathlib import PurePosixPath
import re
import uuid

import frappe
from reli_lims.integration_access import require_bridge

MAX_BYTES = 20 * 1024 * 1024
TYPES = {
    "application/pdf": ({".pdf"}, b"%PDF-"),
    "image/png": ({".png"}, b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ({".jpg", ".jpeg"}, b"\xff\xd8\xff"),
}


def validate_file(payload):
    required = {"request_id", "file_name", "mime_type", "sha256", "content_base64"}
    if not isinstance(payload, dict) or set(payload) - {"previousRequestId"} != required:
        frappe.throw("INVALID_SCHEMA")
    try:
        request_id = str(uuid.UUID(payload["request_id"]))
    except (ValueError, TypeError, AttributeError):
        frappe.throw("INVALID_SCHEMA")
    if request_id != payload["request_id"]:
        frappe.throw("INVALID_SCHEMA")
    name, mime, encoded = payload["file_name"], payload["mime_type"], payload["content_base64"]
    if (not isinstance(name, str) or not 1 <= len(name) <= 140 or name in {".", ".."}
            or any(character in name for character in ("/", "\\", "\x00", "\n", "\r"))
            or not isinstance(mime, str) or mime not in TYPES or PurePosixPath(name).suffix.lower() not in TYPES[mime][0]
            or not isinstance(encoded, str) or len(encoded) > 28 * 1024 * 1024
            or not isinstance(payload["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", payload["sha256"])):
        frappe.throw("INVALID_SCHEMA")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        frappe.throw("INVALID_SCHEMA")
    if not 1 <= len(content) <= MAX_BYTES or not content.startswith(TYPES[mime][1]):
        frappe.throw("INVALID_SCHEMA")
    if hashlib.sha256(content).hexdigest() != payload["sha256"]:
        frappe.throw("INVALID_SCHEMA")
    return content


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _scope(identity, context):
    require_bridge()
    if not isinstance(identity, dict) or not identity.get("subject"):
        frappe.throw("FORBIDDEN", frappe.PermissionError)
    if not isinstance(context, dict) or not all(context.get(key) for key in
            ("source_instance", "organization_id", "laboratory_id")):
        frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)
    laboratory = frappe.get_doc("Laboratory Profile", context["laboratory_id"])
    # The Bridge supplies a laboratory from its active organization mapping.
    # A second local allowlist makes accidental cross-instance mapping fail closed.
    bindings = frappe.conf.get("reli_lims_portal_laboratories") or []
    binding = {"source_instance": context["source_instance"], "organization_id": context["organization_id"],
               "laboratory_id": laboratory.name}
    if binding not in bindings:
        frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)
    return laboratory


def _request_key(context, request_id):
    return _hash([context["source_instance"], context["organization_id"], request_id])


def _receipt(request):
    result = {"schemaVersion": 2, "requestId": request.request_id,
              "sourceId": request.source or None, "documentId": request.document or None,
              "status": request.status, "revision": request.revision}
    if request.status == "failed":
        result["errorCode"] = request.error_code or "DEPENDENCY_UNAVAILABLE"
    return result


def upload(identity, context, payload, idempotency_key):
    laboratory = _scope(identity, context)
    content = validate_file(payload)
    # Serializes request-id and content dedupe even for first-insert races.
    frappe.db.sql("SELECT name FROM `tabLaboratory Profile` WHERE name=%s FOR UPDATE", laboratory.name)
    key = _request_key(context, payload["request_id"])
    payload_hash = _hash({key: value for key, value in payload.items() if key != "content_base64"})
    existing = frappe.db.get_value("Capability Upload", {"request_key": key}, "name")
    if existing:
        request = frappe.get_doc("Capability Upload", existing)
        if request.payload_hash != payload_hash:
            frappe.throw("IDEMPOTENCY_CONFLICT")
        return _receipt(request)
    from wekona_documents.services.parser_registry import lookup
    provider = lookup("MinerULocal")
    if provider.external:
        frappe.throw("FORBIDDEN", frappe.PermissionError)
    parser_version = "MinerULocal:" + str(provider.version)
    dedupe = _hash([laboratory.name, payload["sha256"], parser_version,
                    frappe.conf.get("reli_lims_cnas_extraction_profile")])
    previous = None
    if payload.get("previousRequestId"):
        previous = frappe.db.get_value("Capability Upload", {
            "request_key": _request_key(context, payload["previousRequestId"]),
            "laboratory": laboratory.name}, "name")
        if not previous:
            frappe.throw("NOT_FOUND", frappe.DoesNotExistError)
    duplicate = None if previous else frappe.db.get_value("Capability Upload", {
        "dedupe_key": dedupe, "laboratory": laboratory.name}, "name")
    request = frappe.get_doc({"doctype": "Capability Upload", "request_key": key,
        "request_id": payload["request_id"], "source_instance": context["source_instance"],
        "organization_id": context["organization_id"], "actor_id": identity["subject"],
        "laboratory": laboratory.name, "payload_hash": payload_hash,
        "content_hash": payload["sha256"], "parser_version": parser_version,
        "dedupe_key": dedupe, "previous_request": previous, "status": "uploaded", "revision": 1})
    request.insert(ignore_permissions=True)
    if previous:
        original = frappe.get_doc("Capability Upload", previous)
    if previous and original.content_hash == payload["sha256"]:
        if not original.document:
            frappe.throw("DEPENDENCY_UNAVAILABLE")
        request.document = original.document
        request.revision = original.revision + 1
        request.save(ignore_permissions=True)
        frappe.enqueue("reli_lims.portal_capabilities.start_processing", request_name=request.name,
                       enqueue_after_commit=True)
        return _receipt(request)
    if duplicate:
        original = frappe.get_doc("Capability Upload", duplicate)
        request.document, request.source, request.status = original.document, original.source, original.status
        request.reused_request, request.parse_run = original.name, original.parse_run
        request.error_code = original.error_code
        request.save(ignore_permissions=True)
        return _receipt(request)
    from frappe.utils.file_manager import save_file
    file = save_file(payload["file_name"], content, "Capability Upload", request.name, is_private=1)
    from wekona_documents.services.intake import saved_document
    saved_document(file.file_url, kinds=("pdf", "image", "image_jpeg"))
    document = frappe.get_doc({"doctype": "Incoming Document", "title": payload["file_name"],
        "source_file": file.file_url, "parser_engine": "MinerULocal",
        "extraction_profile": frappe.conf.get("reli_lims_cnas_extraction_profile"),
        "ai_provider": _local_ai_provider()})
    document.insert(ignore_permissions=True)
    request.document = document.name
    request.save(ignore_permissions=True)
    # Enqueue after commit, preserving an uploaded receipt if the parser is down.
    frappe.enqueue("reli_lims.portal_capabilities.start_processing", request_name=request.name,
                   enqueue_after_commit=True)
    return _receipt(request)


def start_processing(request_name):
    require_bridge()
    request = frappe.get_doc("Capability Upload", request_name, for_update=True)
    document = frappe.get_doc("Incoming Document", request.document)
    from wekona_documents.services.document_package import start_parse
    from wekona_documents.services.parser_registry import lookup
    from wekona_documents.services.intake import saved_document
    frappe.db.savepoint("cnas_parse")
    try:
        _path, _digest, kind, _mime = saved_document(document.source_file, kinds=("pdf", "image", "image_jpeg"))
        if kind not in lookup("MinerULocal").kinds:
            raise ValueError("No installed local parser for this type")
        result = start_parse(document.name, "MinerULocal", str(document.modified), "{}", 0)
        request.parse_run = result["run"]
        request.status, request.error_code = "parsing", None
    except Exception:
        frappe.db.rollback(save_point="cnas_parse")
        request.status, request.error_code = "failed", "DEPENDENCY_UNAVAILABLE"
    request.revision += 1
    request.save(ignore_permissions=True)


def _synchronize(request):
    document = frappe.get_doc("Incoming Document", request.document)
    previous = (request.status, request.source, request.error_code)
    approved_name = document.get("approved_structured_version")
    if approved_name and request.parse_run:
        approved_run = frappe.db.get_value("Document Approved Version", approved_name, "source_run")
        if approved_run != request.parse_run:
            approved_name = None
    if approved_name:
        version = frappe.get_doc("Document Approved Version", approved_name)
        from wekona_documents.services.intake import saved_document
        from wekona_documents.services.output_versions import resolve
        _path, actual_hash, _kind, _mime = saved_document(document.source_file, kinds=("pdf", "image", "image_jpeg"))
        if actual_hash != request.content_hash:
            frappe.throw("IDEMPOTENCY_CONFLICT")
        extraction = frappe.get_doc("Document Extraction", version.extraction_run)
        _projection, payload, _links = resolve(extraction, approved_version=approved_name)
        if version.version_type != "Structured" or not isinstance(payload, dict) or not payload.get("items"):
            request.status, request.error_code = "failed", "INVALID_SCHEMA"
        elif version.document != document.name:
            frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)
        else:
            source_id = document.name + ":" + str(version.version)
            source = frappe.db.get_value("Capability Source", {"documents_source_id": source_id}, "name")
            if not source:
                source_doc = frappe.get_doc({"doctype": "Capability Source", "laboratory": request.laboratory,
                    "source_type": "CNAS", "certificate_no": payload.get("certificate_no"),
                    "documents_source_id": source_id, "documents_version": str(version.version),
                    "documents_review_status": "Approved", "source_file_url": document.source_file,
                    "issue_date": payload.get("issue_date"), "expiry_date": payload.get("expiry_date"),
                    "structured_json": version.structured_json})
                source_doc.insert(ignore_permissions=True)
                source = source_doc.name
            elif frappe.db.get_value("Capability Source", source, "laboratory") != request.laboratory:
                frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)
            request.source, request.status, request.error_code = source, "approved", None
    elif document.review_status == "Rejected" and not request.previous_request:
        request.status = "rejected"
    elif document.status == "Failed" or document.extraction_status == "Failed":
        request.status, request.error_code = "failed", "DEPENDENCY_UNAVAILABLE"
    elif request.parse_run and document.selected_parse_run != request.parse_run:
        run_status = frappe.db.get_value("Document Processing Run", request.parse_run, "status")
        request.status = "needs_confirmation" if run_status == "Succeeded" else "parsing"
        if run_status == "Failed":
            request.status, request.error_code = "failed", "DEPENDENCY_UNAVAILABLE"
    elif document.selected_extraction_run and frappe.db.get_value(
            "Document Extraction", document.selected_extraction_run, "processing_run") == request.parse_run:
        request.status = "reviewing"
    elif document.selected_parse_run:
        # Extraction uses the existing configured profile and provider. No cloud
        # fallback is enabled here and human review remains mandatory.
        latest_parse = frappe.db.get_value("Document Extraction", document.latest_extraction, "processing_run") if document.latest_extraction else None
        if document.extraction_profile and document.ai_provider and latest_parse != request.parse_run:
            from wekona_documents.services.extraction import queue_extraction
            queue_extraction(document.name)
            request.status = "reviewing"
        else:
            request.status = "needs_confirmation"
    elif document.status in {"Queued", "Processing"}:
        request.status = "parsing"
    if previous != (request.status, request.source, request.error_code):
        request.revision += 1
        request.save(ignore_permissions=True)
    return request


def get(identity, context, payload):
    laboratory = _scope(identity, context)
    if not isinstance(payload, dict) or set(payload) != {"request_id"}:
        frappe.throw("INVALID_SCHEMA")
    name = frappe.db.get_value("Capability Upload", {
        "request_key": _request_key(context, payload["request_id"]), "laboratory": laboratory.name}, "name")
    if not name:
        frappe.throw("NOT_FOUND", frappe.DoesNotExistError)
    request = frappe.get_doc("Capability Upload", name, for_update=True)
    if request.reused_request:
        original = frappe.get_doc("Capability Upload", request.reused_request, for_update=True)
        if original.laboratory != request.laboratory:
            frappe.throw("SCOPE_MISMATCH", frappe.PermissionError)
        original = _synchronize(original) if original.document else original
        request.document, request.source, request.status = original.document, original.source, original.status
        request.parse_run, request.error_code, request.revision = original.parse_run, original.error_code, original.revision
        request.save(ignore_permissions=True)
        return _receipt(request)
    if request.document:
        frappe.db.savepoint("cnas_sync")
        try:
            request = _synchronize(request)
        except frappe.PermissionError:
            raise
        except Exception:
            frappe.db.rollback(save_point="cnas_sync")
            request.reload()
            request.status, request.error_code = "failed", "DEPENDENCY_UNAVAILABLE"
            request.revision += 1
            request.save(ignore_permissions=True)
    return _receipt(request)


def _local_ai_provider():
    name = frappe.conf.get("reli_lims_cnas_ai_provider")
    if not name:
        return None
    provider = frappe.get_doc("Document AI Provider", name)
    host = urlsplit(provider.base_url or "").hostname
    try:
        private = host == "localhost" or ipaddress.ip_address(host or "").is_private
    except ValueError:
        private = False
    if not provider.enabled or not private:
        frappe.throw("DEPENDENCY_UNAVAILABLE")
    return name
