"""Fail closed on machine locations or credential-like text in public results."""
import ipaddress
import re

PRIVATE = re.compile(r'(?:/(?:mnt|root|home|tmp|var|data|Users)/|[A-Za-z]:\\|(?:https?|cpfs|oss|file|s3)://|'
                     r'\bcpfs\b|sk-[A-Za-z0-9]{12,}|Bearer\s+\S+|\b(?:AKIA[A-Z0-9]{16}|LTAI[A-Za-z0-9]{16,})\b|'
                     r'\blocalhost\b|\b[\w.-]+\.dsw-gateway-[\w.-]+\b|\b[\w.-]+\.(?:internal|local)\b)',re.I)
IPV4 = re.compile(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])')
IPV6 = re.compile(r'(?<![A-Za-z0-9])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?![A-Za-z0-9])')
PRIVATE_KEYS = {'api_key','token','access_token','access_key','secret_key','authorization','credential','credentials',
                'endpoint','password','model_path','served_model','tokenizer_path','source_url','source_path',
                'source_root','source_files','checkpoint_path','runner_pid','username','user_name'}

def public_text(value):
    if PRIVATE.search(value): raise ValueError('Public text contains private location or credential-like content')
    for match in [*IPV4.finditer(value),*IPV6.finditer(value)]:
        try: ipaddress.ip_address(match.group())
        except ValueError: continue
        raise ValueError('Public text contains a network address')
    return value

def assert_public_document(value):
    if isinstance(value,str):public_text(value)
    elif isinstance(value,dict):
        for key,item in value.items():
            if str(key).lower() in PRIVATE_KEYS:raise ValueError('Private field is not allowed in public results')
            public_text(str(key));assert_public_document(item)
    elif isinstance(value,(tuple,list)):
        for item in value:assert_public_document(item)
