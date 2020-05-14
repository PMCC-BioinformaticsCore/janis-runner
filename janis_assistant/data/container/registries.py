from typing import Optional
import json
from enum import Enum
from abc import ABC, abstractmethod

from urllib import request, parse, error

from janis_core import Logger

from janis_assistant.data.container.info import ContainerInfo

DIGEST_HEADER_NAME = "Docker-Content-Digest"
MANIFEST_V2_MEDIA_TYPE = "application/vnd.docker.distribution.manifest.v2+json"
MANIFEST_LIST_V2_MEDIA_TYPE = (
    "application/vnd.docker.distribution.manifest.list.v2+json"
)


class ContainerRegistry(Enum):
    dockerhub = "docker"
    quay = "quay"
    gcr = "gcr"

    @staticmethod
    def from_host(host):
        if host is None or not host:
            return ContainerRegistry.dockerhub
        elif "quay.io" in host:
            return ContainerRegistry.quay
        elif "gcr" in host:
            return ContainerRegistry.gcr

    def to_registry(self):
        if self == ContainerRegistry.dockerhub:
            return DockerHubRegistry()
        elif self == ContainerRegistry.quay:
            raise NotImplementedError("Come back soon!")
        elif self == ContainerRegistry.gcr:
            raise NotImplementedError("Come back soon!")


class ContainerRegistryBase(ABC):
    @abstractmethod
    def host_name(self) -> str:
        pass

    def build_token_request(self, info: ContainerInfo) -> Optional[request.Request]:
        return None

    def build_request(
        self, info: ContainerInfo, token: Optional[str]
    ) -> Optional[request.Request]:
        host = self.host_name()
        repo = info.without_version(empty_repo="library")
        url = f"https://{host}/v2/{repo}/manifests/{info.tag}"

        headers = {"accept": MANIFEST_V2_MEDIA_TYPE}

        if token:
            headers["authorization"] = "Bearer " + token

        return request.Request(url=url, headers=headers,)

    def get_digest(self, info: ContainerInfo) -> Optional[str]:
        try:
            token = self.get_token(info)
        except Exception as e:
            Logger.critical(
                f"Couldn't get digest for container '{str(info)}': {str(e)}"
            )
            return None
        if token:
            print(f"Got token for '{info}': {token[: min(5, len(token) - 1)]}...")
        req = self.build_request(info, token)
        print(f"Requesting digest from: {req.full_url}", req.header_items())
        with request.urlopen(req) as response:
            rheaders = response.headers
            digest = rheaders.get("etag", rheaders.get("Docker-Content-Digest"))

        return digest

    def get_token(self, info: ContainerInfo) -> Optional[str]:
        req = self.build_token_request(info)
        if req is None:
            return None
        print("Requesting token with: " + req.full_url)
        response = request.urlopen(req)
        data = response.read()
        res = json.loads(data.decode(response.info().get_content_charset("utf-8")))
        return res.get("token")


class DockerHubRegistry(ContainerRegistryBase):
    def host_name(self) -> str:
        return "registry.hub.docker.com"

    def build_token_request(self, info: ContainerInfo) -> request.Request:
        # In future, might want to insert credentials in here from JanisConfig
        repo = info.without_version(empty_repo="library")
        url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
        return request.Request(url=url)
