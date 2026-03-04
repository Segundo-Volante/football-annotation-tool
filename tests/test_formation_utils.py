"""Tests for backend/formation_utils.py."""

import pytest

from backend.models import Player
from backend.squad_loader import TeamSquad
from backend.formation_utils import (
    parse_formation,
    assign_players_to_formation,
    SUPPORTED_FORMATIONS,
    POSITION_TO_ROW,
    _formation_row_names,
)


# ── Helpers ──

def _make_team(formation: str, players_data: list[tuple[int, str, str]]) -> TeamSquad:
    """Create a TeamSquad from (jersey, name, position) tuples."""
    players = [Player(jersey_number=n, name=nm, position=pos) for n, nm, pos in players_data]
    return TeamSquad(name="Test FC", formation=formation, players=players)


def _make_442_team() -> TeamSquad:
    """Standard 4-4-2 team with 11 players."""
    return _make_team("4-4-2", [
        (1, "GK1", "GK"),
        (2, "RB1", "RB"), (3, "CB1", "CB"), (4, "CB2", "CB"), (5, "LB1", "LB"),
        (6, "RM1", "RM"), (7, "CM1", "CM"), (8, "CM2", "CM"), (9, "LM1", "LM"),
        (10, "ST1", "ST"), (11, "ST2", "ST"),
    ])


# ═══════════════════════════════════════════════════════════
#  parse_formation
# ═══════════════════════════════════════════════════════════


class TestParseFormation:
    """Tests for parse_formation()."""

    def test_standard_442(self):
        assert parse_formation("4-4-2") == [4, 4, 2]

    def test_standard_433(self):
        assert parse_formation("4-3-3") == [4, 3, 3]

    def test_standard_4231(self):
        assert parse_formation("4-2-3-1") == [4, 2, 3, 1]

    def test_352(self):
        assert parse_formation("3-5-2") == [3, 5, 2]

    def test_343(self):
        assert parse_formation("3-4-3") == [3, 4, 3]

    def test_532(self):
        assert parse_formation("5-3-2") == [5, 3, 2]

    def test_541(self):
        assert parse_formation("5-4-1") == [5, 4, 1]

    def test_4141(self):
        assert parse_formation("4-1-4-1") == [4, 1, 4, 1]

    def test_451(self):
        assert parse_formation("4-5-1") == [4, 5, 1]

    def test_4411(self):
        assert parse_formation("4-4-1-1") == [4, 4, 1, 1]

    def test_3412(self):
        assert parse_formation("3-4-1-2") == [3, 4, 1, 2]

    def test_empty_string(self):
        assert parse_formation("") == []

    def test_whitespace_only(self):
        assert parse_formation("   ") == []

    def test_invalid_letters(self):
        assert parse_formation("abc") == []

    def test_mixed_letters_numbers(self):
        assert parse_formation("4-a-2") == []

    def test_whitespace_stripped(self):
        assert parse_formation("  4-4-2  ") == [4, 4, 2]

    def test_wrong_total_too_few(self):
        assert parse_formation("3-3-2") == []  # sum = 8

    def test_wrong_total_too_many(self):
        assert parse_formation("5-5-2") == []  # sum = 12

    @pytest.mark.parametrize("formation", SUPPORTED_FORMATIONS)
    def test_all_supported_formations_valid(self, formation):
        result = parse_formation(formation)
        assert len(result) >= 2, f"Failed for {formation}"
        assert sum(result) == 10, f"Outfield count wrong for {formation}"


# ═══════════════════════════════════════════════════════════
#  assign_players_to_formation
# ═══════════════════════════════════════════════════════════


class TestAssignPlayersToFormation:
    """Tests for assign_players_to_formation()."""

    def test_442_full_squad(self):
        team = _make_442_team()
        rows, subs = assign_players_to_formation(team)
        assert len(rows) == 4  # GK, DEF, MID, FWD
        assert len(rows[0]) == 1  # GK
        assert len(rows[1]) == 4  # DEF
        assert len(rows[2]) == 4  # MID
        assert len(rows[3]) == 2  # FWD
        assert len(subs) == 0

    def test_gk_in_first_row(self):
        team = _make_442_team()
        rows, _ = assign_players_to_formation(team)
        assert rows[0][0].position == "GK"

    def test_lateral_sorting_defense(self):
        team = _make_442_team()
        rows, _ = assign_players_to_formation(team)
        # Defense row: LB should be left (index 0), RB should be right (last)
        positions = [p.position for p in rows[1]]
        assert positions[0] == "LB"
        assert positions[-1] == "RB"

    def test_lateral_sorting_midfield(self):
        team = _make_442_team()
        rows, _ = assign_players_to_formation(team)
        # Midfield row: LM should be left, RM should be right
        positions = [p.position for p in rows[2]]
        assert positions[0] == "LM"
        assert positions[-1] == "RM"

    def test_extra_players_become_subs(self):
        team = _make_team("4-4-2", [
            (1, "GK1", "GK"),
            (12, "GK2", "GK"),  # extra GK → sub
            (2, "RB", "RB"), (3, "CB1", "CB"), (4, "CB2", "CB"), (5, "LB", "LB"),
            (6, "RM", "RM"), (7, "CM1", "CM"), (8, "CM2", "CM"), (9, "LM", "LM"),
            (10, "ST1", "ST"), (11, "ST2", "ST"),
            (14, "ST3", "ST"),  # extra forward → sub
        ])
        rows, subs = assign_players_to_formation(team)
        assert len(subs) == 2
        sub_numbers = {p.jersey_number for p in subs}
        assert 12 in sub_numbers  # extra GK
        assert 14 in sub_numbers  # extra forward

    def test_no_formation_string(self):
        team = _make_team("", [
            (1, "GK", "GK"), (2, "CB", "CB"),
        ])
        rows, subs = assign_players_to_formation(team)
        assert rows == []
        assert len(subs) == 2

    def test_players_without_position_become_subs(self):
        team = _make_team("4-4-2", [
            (1, "GK1", "GK"),
            (2, "RB", "RB"), (3, "CB1", "CB"), (4, "CB2", "CB"), (5, "LB", "LB"),
            (6, "RM", "RM"), (7, "CM1", "CM"), (8, "CM2", "CM"), (9, "LM", "LM"),
            (10, "ST1", "ST"), (11, "ST2", "ST"),
            (20, "Mystery", ""),  # no position → sub
        ])
        rows, subs = assign_players_to_formation(team)
        assert len(subs) == 1
        assert subs[0].jersey_number == 20

    def test_4231_structure(self):
        """4-2-3-1 should produce 5 rows: GK + 4 formation rows."""
        team = _make_team("4-2-3-1", [
            (1, "GK", "GK"),
            (2, "RB", "RB"), (3, "CB1", "CB"), (4, "CB2", "CB"), (5, "LB", "LB"),
            (6, "CDM1", "CDM"), (7, "CDM2", "CDM"),
            (8, "RW", "RW"), (9, "CAM", "CAM"), (10, "LW", "LW"),
            (11, "ST", "ST"),
        ])
        rows, subs = assign_players_to_formation(team)
        assert len(rows) == 5  # GK + 4 segments
        assert len(rows[0]) == 1  # GK
        assert len(rows[1]) == 4  # DEF
        assert len(rows[2]) == 2  # DEF MID (CDM)
        assert len(rows[3]) == 3  # ATT MID (RW, CAM, LW)
        assert len(rows[4]) == 1  # FWD
        assert len(subs) == 0

    def test_4231_cdms_in_first_midfield_row(self):
        """In 4-2-3-1, CDMs should go to the first midfield row (row 2)."""
        team = _make_team("4-2-3-1", [
            (1, "GK", "GK"),
            (2, "RB", "RB"), (3, "CB1", "CB"), (4, "CB2", "CB"), (5, "LB", "LB"),
            (6, "CDM1", "CDM"), (7, "CDM2", "CDM"),
            (8, "RW", "RW"), (9, "CAM", "CAM"), (10, "LW", "LW"),
            (11, "ST", "ST"),
        ])
        rows, _ = assign_players_to_formation(team)
        # Row 2 is the defensive midfield (2 CDMs)
        dm_positions = [p.position for p in rows[2]]
        assert dm_positions == ["CDM", "CDM"]

    def test_4231_attacking_mids_lateral_order(self):
        """In 4-2-3-1 attacking midfield row, LW should be left, RW right."""
        team = _make_team("4-2-3-1", [
            (1, "GK", "GK"),
            (2, "RB", "RB"), (3, "CB1", "CB"), (4, "CB2", "CB"), (5, "LB", "LB"),
            (6, "CDM1", "CDM"), (7, "CDM2", "CDM"),
            (8, "RW", "RW"), (9, "CAM", "CAM"), (10, "LW", "LW"),
            (11, "ST", "ST"),
        ])
        rows, _ = assign_players_to_formation(team)
        # Row 3 is the attacking midfield (LW, CAM, RW)
        att_mid_positions = [p.position for p in rows[3]]
        assert att_mid_positions[0] == "LW"
        assert att_mid_positions[-1] == "RW"

    def test_352_structure(self):
        team = _make_team("3-5-2", [
            (1, "GK", "GK"),
            (2, "CB1", "CB"), (3, "CB2", "CB"), (4, "CB3", "CB"),
            (5, "LM", "LM"), (6, "CDM", "CDM"), (7, "CM1", "CM"),
            (8, "CM2", "CM"), (9, "RM", "RM"),
            (10, "ST1", "ST"), (11, "ST2", "ST"),
        ])
        rows, subs = assign_players_to_formation(team)
        assert len(rows) == 4  # GK + 3 segments
        assert len(rows[0]) == 1  # GK
        assert len(rows[1]) == 3  # DEF
        assert len(rows[2]) == 5  # MID
        assert len(rows[3]) == 2  # FWD
        assert len(subs) == 0

    def test_sample_squad_json_structure(self):
        """Mirrors config/sample_squad.json: 14 players, 4-4-2, 3 subs."""
        team = _make_team("4-4-2", [
            (13, "Oblak", "GK"),
            (4, "Molina", "RB"), (15, "Savić", "CB"),
            (3, "Le Normand", "CB"), (23, "Reinildo", "LB"),
            (11, "Lemar", "RM"), (6, "Koke", "CM"),
            (8, "Barrios", "CM"), (10, "Correa", "LM"),
            (7, "Griezmann", "ST"), (19, "Álvarez", "ST"),
            # Subs
            (9, "Sorloth", "ST"),
            (21, "Galán", "LB"),
            (22, "Azpilicueta", "CB"),
        ])
        rows, subs = assign_players_to_formation(team)
        assert len(rows[0]) == 1  # GK
        assert len(rows[1]) == 4  # DEF
        assert len(rows[2]) == 4  # MID
        assert len(rows[3]) == 2  # FWD
        # 3 subs: extra defenders/forwards overflow
        assert len(subs) == 3
        # The exact subs depend on lateral sort order within buckets:
        # defense bucket sorted LB→CB→RB: 2 LBs + 2 CBs fill 4 slots, leaving RB(4) + CB(22)
        # forward bucket sorted by jersey: 7, 9 fill 2 slots, leaving 19
        sub_numbers = {p.jersey_number for p in subs}
        assert sub_numbers == {4, 19, 22}

    def test_case_insensitive_positions(self):
        """Position lookup should be case-insensitive."""
        team = _make_team("4-4-2", [
            (1, "GK", "gk"),
            (2, "RB", "rb"), (3, "CB1", "cb"), (4, "CB2", "Cb"), (5, "LB", "lb"),
            (6, "RM", "rm"), (7, "CM1", "cm"), (8, "CM2", "Cm"), (9, "LM", "lm"),
            (10, "ST1", "st"), (11, "ST2", "St"),
        ])
        rows, subs = assign_players_to_formation(team)
        assert len(rows) == 4
        assert len(subs) == 0


# ═══════════════════════════════════════════════════════════
#  _formation_row_names
# ═══════════════════════════════════════════════════════════


class TestFormationRowNames:
    """Tests for _formation_row_names()."""

    def test_three_rows(self):
        assert _formation_row_names([4, 4, 2]) == ["defense", "midfield", "forward"]

    def test_four_rows(self):
        assert _formation_row_names([4, 2, 3, 1]) == [
            "defense", "midfield", "midfield", "forward",
        ]

    def test_two_rows(self):
        assert _formation_row_names([6, 4]) == ["defense", "forward"]

    def test_empty(self):
        assert _formation_row_names([]) == []

    def test_single_row(self):
        assert _formation_row_names([10]) == ["defense"]


# ═══════════════════════════════════════════════════════════
#  POSITION_TO_ROW coverage
# ═══════════════════════════════════════════════════════════


class TestPositionToRow:
    """Verify all standard positions are classified."""

    @pytest.mark.parametrize("position,expected_row", [
        ("GK", "gk"),
        ("RB", "defense"), ("CB", "defense"), ("LB", "defense"),
        ("RWB", "defense"), ("LWB", "defense"),
        ("CDM", "midfield"), ("CM", "midfield"), ("CAM", "midfield"),
        ("RM", "midfield"), ("LM", "midfield"),
        ("RW", "midfield"), ("LW", "midfield"),
        ("ST", "forward"), ("CF", "forward"),
    ])
    def test_position_classification(self, position, expected_row):
        assert POSITION_TO_ROW[position] == expected_row
