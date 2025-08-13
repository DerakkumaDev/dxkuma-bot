from typing import Optional
import grpc
from google.protobuf import wrappers_pb2

from util.Config import config
from .proto import kumabot_pb2
from .proto import kumabot_pb2_grpc


class BestsApiClient:
    def __init__(self, server_address: Optional[str] = None):
        self.server_address = (
            config.backend_url if server_address is None else server_address
        )
        self.channel = None
        self.stub = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        self.channel = grpc.aio.insecure_channel(self.server_address)
        self.stub = kumabot_pb2_grpc.BestsApiStub(self.channel)

    async def close(self):
        if self.channel:
            await self.channel.close()

    async def get_from_lxns(
        self,
        dev_token: str,
        qq: Optional[int] = None,
        personal_token: Optional[str] = None,
    ):
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = kumabot_pb2.LxnsBestsRequest()
        request.devToken = dev_token

        if qq is not None:
            request.qq.CopyFrom(wrappers_pb2.UInt32Value(value=qq))

        if personal_token is not None:
            request.personalToken.CopyFrom(
                wrappers_pb2.StringValue(value=personal_token)
            )

        async for response in self.stub.GetFromLxns(request):
            yield response

    async def get_anime_from_lxns(
        self,
        dev_token: str,
        qq: Optional[int] = None,
        personal_token: Optional[str] = None,
    ):
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = kumabot_pb2.LxnsBestsRequest()
        request.devToken = dev_token

        if qq is not None:
            request.qq.CopyFrom(wrappers_pb2.UInt32Value(value=qq))

        if personal_token is not None:
            request.personalToken.CopyFrom(
                wrappers_pb2.StringValue(value=personal_token)
            )

        async for response in self.stub.GetAnimeFromLxns(request):
            yield response

    async def get_from_diving_fish(
        self,
        qq: int,
        frame: Optional[int] = None,
        plate: Optional[int] = None,
        icon: Optional[int] = None,
    ):
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = kumabot_pb2.DivingFishBestsRequest()
        request.qq = qq

        if frame is not None:
            request.frame = frame
        if plate is not None:
            request.plate = plate
        if icon is not None:
            request.icon = icon

        async for response in self.stub.GetFromDivingFish(request):
            yield response

    async def get_anime_from_diving_fish(
        self,
        qq: int,
        frame: Optional[int] = None,
        plate: Optional[int] = None,
        icon: Optional[int] = None,
    ):
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = kumabot_pb2.DivingFishBestsRequest()
        request.qq = qq

        if frame is not None:
            request.frame = frame
        if plate is not None:
            request.plate = plate
        if icon is not None:
            request.icon = icon

        async for response in self.stub.GetAnimeFromDivingFish(request):
            yield response


class ListApiClient:
    def __init__(self, server_address: Optional[str] = None):
        self.server_address = (
            config.backend_url if server_address is None else server_address
        )
        self.channel = None
        self.stub = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def connect(self):
        self.channel = grpc.aio.insecure_channel(self.server_address)
        self.stub = kumabot_pb2_grpc.ListApiStub(self.channel)

    async def close(self):
        if self.channel:
            await self.channel.close()

    async def get_from_lxns(
        self,
        personal_token: str,
        level: str,
        page: Optional[int] = None,
    ):
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = kumabot_pb2.LxnsListRequest()
        request.personalToken = personal_token
        request.level = level
        if page is not None:
            request.page = page

        async for response in self.stub.GetFromLxns(request):
            yield response

    async def get_from_diving_fish(
        self,
        token: str,
        qq: Optional[int] = None,
        level: Optional[str] = None,
        page: Optional[int] = None,
        plate: Optional[int] = None,
        icon: Optional[int] = None,
    ):
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        request = kumabot_pb2.DivingFishListRequest()
        request.token = token
        if qq is not None:
            request.qq = qq
        if level is not None:
            request.level = level
        if page is not None:
            request.page = page
        if plate is not None:
            request.plate = plate
        if icon is not None:
            request.icon = icon

        async for response in self.stub.GetFromDivingFish(request):
            yield response
