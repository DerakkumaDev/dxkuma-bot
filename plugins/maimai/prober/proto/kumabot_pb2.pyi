from google.protobuf import wrappers_pb2 as _wrappers_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LxnsBestsRequest(_message.Message):
    __slots__ = ("devToken", "qq", "personalToken")
    DEVTOKEN_FIELD_NUMBER: _ClassVar[int]
    QQ_FIELD_NUMBER: _ClassVar[int]
    PERSONALTOKEN_FIELD_NUMBER: _ClassVar[int]
    devToken: str
    qq: _wrappers_pb2.UInt32Value
    personalToken: _wrappers_pb2.StringValue
    def __init__(self, devToken: _Optional[str] = ..., qq: _Optional[_Union[_wrappers_pb2.UInt32Value, _Mapping]] = ..., personalToken: _Optional[_Union[_wrappers_pb2.StringValue, _Mapping]] = ...) -> None: ...

class DivingFishBestsRequest(_message.Message):
    __slots__ = ("qq", "frame", "plate", "icon")
    QQ_FIELD_NUMBER: _ClassVar[int]
    FRAME_FIELD_NUMBER: _ClassVar[int]
    PLATE_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    qq: int
    frame: int
    plate: int
    icon: int
    def __init__(self, qq: _Optional[int] = ..., frame: _Optional[int] = ..., plate: _Optional[int] = ..., icon: _Optional[int] = ...) -> None: ...

class LxnsListRequest(_message.Message):
    __slots__ = ("personalToken", "level", "page")
    PERSONALTOKEN_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    personalToken: str
    level: str
    page: int
    def __init__(self, personalToken: _Optional[str] = ..., level: _Optional[str] = ..., page: _Optional[int] = ...) -> None: ...

class DivingFishListRequest(_message.Message):
    __slots__ = ("token", "qq", "level", "page", "plate", "icon")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    QQ_FIELD_NUMBER: _ClassVar[int]
    LEVEL_FIELD_NUMBER: _ClassVar[int]
    PAGE_FIELD_NUMBER: _ClassVar[int]
    PLATE_FIELD_NUMBER: _ClassVar[int]
    ICON_FIELD_NUMBER: _ClassVar[int]
    token: str
    qq: int
    level: str
    page: int
    plate: int
    icon: int
    def __init__(self, token: _Optional[str] = ..., qq: _Optional[int] = ..., level: _Optional[str] = ..., page: _Optional[int] = ..., plate: _Optional[int] = ..., icon: _Optional[int] = ...) -> None: ...

class ImageResponse(_message.Message):
    __slots__ = ("data",)
    DATA_FIELD_NUMBER: _ClassVar[int]
    data: bytes
    def __init__(self, data: _Optional[bytes] = ...) -> None: ...
