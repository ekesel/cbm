import io, json, gzip, datetime as dt
from typing import Optional, Tuple
import boto3
from botocore.client import Config
from django.conf import settings

def _client():
    use_ssl = bool(int(str(getattr(settings, "S3_USE_SSL", "0"))))
    endpoint = getattr(settings, "S3_ENDPOINT", None)
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=getattr(settings, "S3_ACCESS_KEY", None),
        aws_secret_access_key=getattr(settings, "S3_SECRET_KEY", None),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        use_ssl=use_ssl,
        verify=use_ssl,
    )

def ensure_bucket(bucket: str):
    s3 = _client()
    # idempotent: try HEAD then create
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:
        s3.create_bucket(Bucket=bucket)

def build_key(prefix: str, *, source: str, board_id: str, object_type: str, external_id: str, fetched_at) -> str:
    ts = fetched_at or dt.datetime.utcnow()
    if hasattr(ts, "strftime"):
        yyyy = ts.strftime("%Y"); mm = ts.strftime("%m"); dd = ts.strftime("%d")
        stamp = ts.strftime("%Y%m%dT%H%M%S")
    else:
        yyyy = "0000"; mm = "00"; dd = "00"; stamp = "00000000T000000"
    safe_bid = (board_id or "na").replace("/", "_")
    safe_ext = (external_id or "unknown").replace("/", "_")
    return f"{prefix}/{source}/{safe_bid}/{object_type}/{yyyy}/{mm}/{dd}/{safe_ext}_{stamp}.json.gz"

def put_json_gz(bucket: str, key: str, obj) -> int:
    """Return bytes written."""
    data = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", compresslevel=6) as gz:
        gz.write(data)
    body = out.getvalue()
    _client().put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json", ContentEncoding="gzip")
    return len(body)

def get_json_gz(bucket: str, key: str):
    resp = _client().get_object(Bucket=bucket, Key=key)
    raw = resp["Body"].read()
    with gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb") as gz:
        return json.loads(gz.read().decode("utf-8"))

def delete_object(bucket: str, key: str):
    _client().delete_object(Bucket=bucket, Key=key)
