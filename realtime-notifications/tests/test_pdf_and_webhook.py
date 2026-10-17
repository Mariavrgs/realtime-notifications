import hashlib
import hmac

from app.tasks.tasks import build_pdf, sign_payload


def test_build_pdf_creates_valid_file(tmp_path):
    out = tmp_path / "r.pdf"
    build_pdf(out, 7, [("paid", 3, 120.5), ("pending", 1, 10)])
    assert out.read_bytes().startswith(b"%PDF")


def test_sign_payload_matches_hmac_sha256():
    body = b'{"a":1}'
    expected = hmac.new(b"segredo", body, hashlib.sha256).hexdigest()
    assert sign_payload("segredo", body) == expected
