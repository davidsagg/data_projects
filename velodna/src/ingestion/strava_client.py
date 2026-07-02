import requests

_BASE_URL = "https://www.strava.com/api/v3"


class StravaClient:
    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._headers = {"Authorization": f"Bearer {access_token}"}

    def get_activities(self, limit: int = 200, page: int = 1) -> list:
        """GET /athlete/activities — retorna lista de atividades resumidas."""
        resp = requests.get(
            f"{_BASE_URL}/athlete/activities",
            headers=self._headers,
            params={"per_page": limit, "page": page},
        )
        return resp.json()

    def get_activity_streams(self, activity_id: int) -> dict:
        """GET /activities/{id}/streams — retorna streams brutos da atividade."""
        resp = requests.get(
            f"{_BASE_URL}/activities/{activity_id}/streams",
            headers=self._headers,
            params={"keys": "time,watts,heartrate,cadence,velocity_smooth,altitude",
                    "key_by_type": "true"},
        )
        return resp.json()
