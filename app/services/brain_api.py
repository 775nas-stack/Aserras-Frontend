"""Client abstraction around the Aserras Brain API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx
from fastapi import status

from app.settings import Settings


class BrainAPIError(Exception):
    """Base error for Brain API failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class BrainAPIUnavailable(BrainAPIError):
    """Raised when Brain cannot be reached."""


@dataclass(slots=True)
class BrainAPIClient:
    """Simple async HTTP client that communicates with the Brain backend."""

    settings: Settings

    @property
    def base_url(self) -> str:
        return self.settings.BRAIN_API_URL.rstrip("/")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: Any | None = None,
        data: Any | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(timeout=self.settings.BRAIN_API_TIMEOUT) as client:
                response = await client.request(
                    method,
                    url,
                    json=json,
                    data=data,
                    params=params,
                    headers=headers,
                )
        except httpx.RequestError as exc:
            raise BrainAPIUnavailable(
                "Unable to reach Aserras Brain at the moment."
            ) from exc

        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise BrainAPIUnavailable("Aserras Brain is temporarily unavailable.")

        if response.status_code >= status.HTTP_400_BAD_REQUEST:
            detail: str | None = None
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    detail = response.json().get("detail")
                except ValueError:
                    detail = None
            if detail is None:
                detail = response.text
            raise BrainAPIError(detail or "Request to Aserras Brain failed.", status_code=response.status_code)

        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                return response.json()
            except ValueError:
                raise BrainAPIError("Brain response was not valid JSON", status_code=response.status_code)
        return response.content

    async def login(self, email: str, password: str) -> Mapping[str, Any]:
        return await self._request(
            "POST",
            "/auth/login",
            json={"email": email, "password": password},
        )

    async def register(self, name: str, email: str, password: str) -> Mapping[str, Any]:
        return await self._request(
            "POST",
            "/auth/register",
            json={"name": name, "email": email, "password": password},
        )

    async def get_profile(self, token: str) -> Mapping[str, Any]:
        return await self._request("GET", "/auth/me", token=token)

    async def update_profile(self, token: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return await self._request("PATCH", "/auth/me", token=token, json=payload)

    async def list_models(self, token: str | None = None) -> list[Mapping[str, Any]]:
        data = await self._request("GET", "/models/list", token=token)
        return data if isinstance(data, list) else data.get("models", [])

    async def text_completion(self, prompt: str, *, token: str, model: str | None = None) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"prompt": prompt}
        if model:
            payload["model"] = model
        return await self._request("POST", "/ai/text", token=token, json=payload)

    async def image_generation(self, prompt: str, *, token: str, size: str | None = None) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"prompt": prompt}
        if size:
            payload["size"] = size
        return await self._request("POST", "/ai/image", token=token, json=payload)

    async def code_generation(
        self,
        instructions: str,
        *,
        token: str,
        language: str | None = None,
        model: str | None = None,
    ) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"instructions": instructions}
        if language:
            payload["language"] = language
        if model:
            payload["model"] = model
        return await self._request("POST", "/ai/code", token=token, json=payload)

    async def get_history(self, token: str) -> list[Mapping[str, Any]]:
        data = await self._request("GET", "/history", token=token)
        return data if isinstance(data, list) else data.get("items", [])
