import orjson
from typing import Any, Optional, Union

def dumps(obj: Any, **kwargs) -> str:
    """Сериализует объект в JSON-строку с поддержкой datetime."""
    options = 0
    if kwargs.get('indent'):
        options |= orjson.OPT_INDENT_2
    return orjson.dumps(obj, option=options).decode('utf-8')

def loads(s: Union[str, bytes], **kwargs) -> Any:
    """Десериализует JSON-строку в объект Python."""
    if isinstance(s, str):
        s = s.encode('utf-8')
    return orjson.loads(s)