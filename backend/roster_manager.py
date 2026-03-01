import json
from pathlib import Path
from typing import Optional

from backend.models import Player


class RosterManager:
    def __init__(self, roster_path: str | Path = "config/roster.json"):
        self.roster_path = Path(roster_path)
        self.team_name = ""
        self.season = ""
        self.players: dict[int, Player] = {}
        self.load()

    def load(self):
        if not self.roster_path.exists():
            return
        data = json.loads(self.roster_path.read_text(encoding="utf-8"))
        self.team_name = data.get("team_name", "")
        self.season = data.get("season", "")
        self.players.clear()
        for p in data.get("players", []):
            player = Player(
                jersey_number=p["number"],
                name=p["name"],
                position=p["position"],
                nationality=p["nationality"],
            )
            self.players[player.jersey_number] = player

    def lookup_by_number(self, number: int) -> Optional[Player]:
        return self.players.get(number)

    def get_all_players(self) -> list[Player]:
        return sorted(self.players.values(), key=lambda p: p.jersey_number)

    def add_player(self, number: int, name: str, position: str, nationality: str):
        self.players[number] = Player(number, name, position, nationality)

    def remove_player(self, number: int):
        self.players.pop(number, None)

    def save(self):
        data = {
            "team_name": self.team_name,
            "season": self.season,
            "players": [
                {
                    "number": p.jersey_number,
                    "name": p.name,
                    "position": p.position,
                    "nationality": p.nationality,
                }
                for p in self.get_all_players()
            ],
        }
        self.roster_path.parent.mkdir(parents=True, exist_ok=True)
        self.roster_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
