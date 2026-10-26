"""Small atomic JSON writer shared by local imports and HTTP services."""
import json
import os
import uuid
from pathlib import Path

def write_json(path, value):
    path = Path(path)
    content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    temporary.write_text(content)
    os.replace(temporary,path)
