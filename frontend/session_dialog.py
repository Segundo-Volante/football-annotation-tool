import json
import logging
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFileDialog, QButtonGroup, QRadioButton, QGroupBox, QGridLayout,
    QFrame, QSlider,
)

logger = logging.getLogger(__name__)

try:
    from backend.model_manager import AI_AVAILABLE
except ImportError:
    AI_AVAILABLE = False

from backend.i18n import I18n, t

# Language options with country flag emoji and native "Language" label
LANGUAGE_OPTIONS = [
    ("en", "\U0001F1EC\U0001F1E7  Language", "English"),
    ("es", "\U0001F1EA\U0001F1F8  Idioma", "Espa\u00f1ol"),
    ("it", "\U0001F1EE\U0001F1F9  Lingua", "Italiano"),
    ("de", "\U0001F1E9\U0001F1EA  Sprache", "Deutsch"),
    ("pt", "\U0001F1F5\U0001F1F9  Idioma", "Portugu\u00eas"),
    ("fr", "\U0001F1EB\U0001F1F7  Langue", "Fran\u00e7ais"),
]


class SessionDialog(QDialog):
    """Startup dialog: language selector, folder, roster CSV, session defaults.

    Horizontal two-column layout: left column for data/match config,
    right column for annotation settings.
    """

    def __init__(self, parent=None, project_config=None):
        super().__init__(parent)
        self.setWindowTitle(t("session.window_title"))
        self.setFixedWidth(920)
        self.setStyleSheet("""
            QDialog { background: #1E1E2E; }
            QLabel { color: #E8E8F0; font-size: 12px; }
            QLineEdit, QComboBox {
                background: #2A2A3C; color: #E8E8F0; border: 1px solid #404060;
                border-radius: 4px; padding: 6px; font-size: 12px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #F5A623; }
            QPushButton {
                background: #404060; color: #E8E8F0; padding: 8px 16px;
                border-radius: 4px; font-size: 12px; border: none;
            }
            QPushButton:hover { background: #505070; }
            QGroupBox {
                color: #8888A0; font-size: 11px; border: 1px solid #404060;
                border-radius: 6px; margin-top: 8px; padding-top: 16px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QRadioButton { color: #E8E8F0; font-size: 11px; spacing: 6px; }
            QRadioButton::indicator { width: 14px; height: 14px; }
        """)

        # Load metadata options
        opts_path = Path(__file__).parent.parent / "config" / "metadata_options.json"
        self._meta_opts = json.loads(opts_path.read_text(encoding="utf-8"))

        self._project_config = project_config
        self._folder_path = ""
        self._roster_path = ""
        self._result = {}
        self._selected_lang = I18n.lang()

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(20, 16, 20, 16)

        # ── Top header: Title (left) + Language buttons (right) ──
        header_row = QHBoxLayout()
        header_row.setSpacing(6)
        self._title_label = QLabel(t("main.window_title"))
        self._title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #F5A623;")
        header_row.addWidget(self._title_label)
        header_row.addStretch()

        self._lang_buttons: list[QPushButton] = []
        for code, native_word, display_name in LANGUAGE_OPTIONS:
            flag = native_word.split("  ")[0]
            btn = QPushButton(f"{flag} {display_name}")
            btn.setProperty("lang_code", code)
            btn.setFixedHeight(26)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _checked, c=code: self._on_language_changed(c))
            self._lang_buttons.append(btn)
            header_row.addWidget(btn)
        layout.addLayout(header_row)
        self._update_lang_buttons()

        # Separator after header
        header_sep = QFrame()
        header_sep.setFrameShape(QFrame.Shape.HLine)
        header_sep.setStyleSheet("color: #404060;")
        layout.addWidget(header_sep)

        # ══════════════════════════════════════════════════════════
        #  Two-column content layout
        # ══════════════════════════════════════════════════════════
        columns = QHBoxLayout()
        columns.setSpacing(16)

        # ═══ LEFT COLUMN: Data & Match ═══════════════════════════
        left_col = QVBoxLayout()
        left_col.setSpacing(6)

        # ── Bundle detection banner (hidden by default) ──
        self._bundle_banner = QLabel("")
        self._bundle_banner.setWordWrap(True)
        self._bundle_banner.setStyleSheet(
            "background: #1A3A5C; color: #B8D8F8; font-size: 11px;"
            " border: 1px solid #2A5A8C; border-radius: 6px;"
            " padding: 8px 12px;"
        )
        self._bundle_banner.setVisible(False)
        left_col.addWidget(self._bundle_banner)

        # Bundle state
        self._is_bundle = False
        self._bundle_match_data: dict = {}
        self._bundle_frame_count = 0

        # ── Folder row ──
        self._folder_label = QLabel(t("session.folder_label"))
        self._folder_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        left_col.addWidget(self._folder_label)
        folder_row = QHBoxLayout()
        self._folder_input = QLineEdit()
        self._folder_input.setPlaceholderText(t("session.folder_placeholder"))
        self._folder_input.setReadOnly(True)
        folder_row.addWidget(self._folder_input, stretch=1)
        self._browse_folder_btn = QPushButton(t("button.browse"))
        self._browse_folder_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self._browse_folder_btn)
        left_col.addLayout(folder_row)

        # ── Roster CSV row ──
        self._roster_label = QLabel(t("session.roster_label"))
        self._roster_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        left_col.addWidget(self._roster_label)
        roster_row = QHBoxLayout()
        self._roster_input = QLineEdit()
        self._roster_input.setPlaceholderText(t("session.roster_placeholder"))
        self._roster_input.setReadOnly(True)
        roster_row.addWidget(self._roster_input, stretch=1)
        self._browse_roster_btn = QPushButton(t("button.browse"))
        self._browse_roster_btn.clicked.connect(self._browse_roster)
        roster_row.addWidget(self._browse_roster_btn)
        left_col.addLayout(roster_row)

        # Roster info label
        self._roster_info = QLabel("")
        self._roster_info.setStyleSheet("color: #F5A623; font-size: 11px;")
        left_col.addWidget(self._roster_info)

        # ── Squad JSON row ──
        self._squad_label = QLabel("Squad File (squad.json)")
        self._squad_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        left_col.addWidget(self._squad_label)
        squad_row = QHBoxLayout()
        self._squad_input = QLineEdit()
        self._squad_input.setPlaceholderText("Auto-detected or browse...")
        self._squad_input.setReadOnly(True)
        squad_row.addWidget(self._squad_input, stretch=1)
        self._browse_squad_btn = QPushButton(t("button.browse"))
        self._browse_squad_btn.clicked.connect(self._browse_squad)
        squad_row.addWidget(self._browse_squad_btn)
        self._generate_squad_btn = QPushButton("Generate from SquadList")
        self._generate_squad_btn.setToolTip(
            "Scan a SquadList folder of player headshot images\n"
            "and auto-generate squad.json from the filenames.\n"
            "Image names should be: {number}_{Name}.png"
        )
        self._generate_squad_btn.setStyleSheet("""
            QPushButton {
                background: #2D5A27; color: #A8E6A1; padding: 8px 12px;
                border-radius: 4px; font-size: 11px; border: none;
            }
            QPushButton:hover { background: #3A7A32; }
        """)
        self._generate_squad_btn.clicked.connect(self._generate_squad_from_folder)
        squad_row.addWidget(self._generate_squad_btn)
        left_col.addLayout(squad_row)

        self._squad_info = QLabel("")
        self._squad_info.setStyleSheet("color: #F5A623; font-size: 11px;")
        left_col.addWidget(self._squad_info)
        self._squad_path = ""

        # ── Separator before match info ──
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #404060;")
        left_col.addWidget(sep1)

        # ══ Team Mode Toggle ══
        team_mode_row = QHBoxLayout()
        team_mode_row.setSpacing(10)
        self._team_mode_label = QLabel("Team Mode:")
        self._team_mode_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        team_mode_row.addWidget(self._team_mode_label)

        self._team_mode_group = QButtonGroup(self)
        self._one_team_radio = QRadioButton("One Team")
        self._one_team_radio.setChecked(True)
        self._one_team_radio.setToolTip(
            "Club analyst mode — annotate from your team's perspective.\n"
            "You pick an opponent and venue (Home / Away / Neutral)."
        )
        self._all_team_radio = QRadioButton("All Team")
        self._all_team_radio.setToolTip(
            "Match analyst mode — annotate both teams equally.\n"
            "You specify Team 1 and Team 2 with their venue."
        )
        self._team_mode_group.addButton(self._one_team_radio, 0)
        self._team_mode_group.addButton(self._all_team_radio, 1)
        team_mode_row.addWidget(self._one_team_radio)
        team_mode_row.addWidget(self._all_team_radio)
        team_mode_row.addStretch()
        left_col.addLayout(team_mode_row)

        # Connect mode toggle BEFORE building the match-info widgets
        self._team_mode_group.idToggled.connect(self._on_team_mode_toggled)

        # ── Source / Round (shared by both modes) ──
        grid = QGridLayout()
        grid.setSpacing(8)
        self._source_label = QLabel(t("session.source_label"))
        grid.addWidget(self._source_label, 0, 0)
        self._source_combo = QComboBox()
        self._source_combo.setEditable(True)
        self._source_combo.lineEdit().setPlaceholderText(t("session.source_placeholder"))
        if self._project_config and self._project_config.exists:
            competitions = self._project_config.get_competitions()
        else:
            competitions = [
                "LaLiga", "LaLiga2", "CopadelRey", "Supercopa",
                "EPL", "EFL_Championship", "FA_Cup", "EFL_Cup",
                "Ligue1", "Ligue2", "CoupeDeFrance", "TropheeDesChampions",
                "SerieA", "SerieB", "CoppaItalia", "SupercoppaItaliana",
                "Bundesliga", "Bundesliga2", "DFB_Pokal", "DFL_Supercup",
                "LigaPortugal", "LigaPortugal2", "TacaDePortugal", "Supertaca",
                "Eredivisie", "EersteDivisie", "KNVB_Beker", "JohanCruyffSchaal",
                "UCL", "UEL", "UECL", "Friendly",
            ]
        self._source_combo.addItems(competitions)
        grid.addWidget(self._source_combo, 0, 1)

        self._round_label = QLabel(t("session.round_label"))
        grid.addWidget(self._round_label, 0, 2)
        self._round_input = QLineEdit()
        self._round_input.setPlaceholderText(t("session.round_placeholder"))
        grid.addWidget(self._round_input, 0, 3)

        # ── One Team Mode: Opponent row ──
        self._opponent_label = QLabel(t("session.opponent_label"))
        grid.addWidget(self._opponent_label, 1, 0)
        self._opponent_combo = QComboBox()
        self._opponent_combo.setEditable(True)
        self._opponent_combo.lineEdit().setPlaceholderText(t("session.opponent_placeholder"))
        if self._project_config and self._project_config.exists:
            opponent_names = self._project_config.get_opponent_names()
            if opponent_names:
                self._opponent_combo.addItems(opponent_names)
        grid.addWidget(self._opponent_combo, 1, 1, 1, 3)

        # ── All Team Mode: Team 1 / Team 2 rows (hidden by default) ──
        self._team1_label = QLabel("Team 1:")
        self._team1_label.setVisible(False)
        grid.addWidget(self._team1_label, 2, 0)
        self._team1_combo = QComboBox()
        self._team1_combo.setEditable(True)
        self._team1_combo.lineEdit().setPlaceholderText("Home team name...")
        self._team1_combo.setVisible(False)
        # Populate with known team names from project config
        if self._project_config and self._project_config.exists:
            all_teams = []
            if self._project_config.team_name:
                all_teams.append(self._project_config.team_name)
            opp_names = self._project_config.get_opponent_names()
            if opp_names:
                all_teams.extend(opp_names)
            if all_teams:
                self._team1_combo.addItems(all_teams)
        grid.addWidget(self._team1_combo, 2, 1, 1, 3)

        self._team2_label = QLabel("Team 2:")
        self._team2_label.setVisible(False)
        grid.addWidget(self._team2_label, 3, 0)
        self._team2_combo = QComboBox()
        self._team2_combo.setEditable(True)
        self._team2_combo.lineEdit().setPlaceholderText("Away team name...")
        self._team2_combo.setVisible(False)
        if self._project_config and self._project_config.exists:
            all_teams2 = []
            if self._project_config.team_name:
                all_teams2.append(self._project_config.team_name)
            opp_names2 = self._project_config.get_opponent_names()
            if opp_names2:
                all_teams2.extend(opp_names2)
            if all_teams2:
                self._team2_combo.addItems(all_teams2)
        grid.addWidget(self._team2_combo, 3, 1, 1, 3)

        # Update venue labels when team names change (All Team Mode)
        self._team1_combo.currentTextChanged.connect(self._update_venue_labels)
        self._team2_combo.currentTextChanged.connect(self._update_venue_labels)

        left_col.addLayout(grid)

        # Keep refs to One-Team-Mode widgets for toggling
        self._one_team_widgets = [self._opponent_label, self._opponent_combo]
        self._all_team_widgets = [
            self._team1_label, self._team1_combo,
            self._team2_label, self._team2_combo,
        ]

        # ── Match Venue ──
        self._venue_label = QLabel(t("session.venue_label"))
        self._venue_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        left_col.addWidget(self._venue_label)

        venue_row = QHBoxLayout()
        self._venue_group = QButtonGroup(self)
        self._venue_home = QRadioButton(t("session.venue_home"))
        self._venue_home.setProperty("value", "home")
        self._venue_home.setChecked(True)
        self._venue_away = QRadioButton(t("session.venue_away"))
        self._venue_away.setProperty("value", "away")
        self._venue_neutral = QRadioButton(t("session.venue_neutral"))
        self._venue_neutral.setProperty("value", "neutral")
        self._venue_group.addButton(self._venue_home, 0)
        self._venue_group.addButton(self._venue_away, 1)
        self._venue_group.addButton(self._venue_neutral, 2)
        venue_row.addWidget(self._venue_home)
        venue_row.addWidget(self._venue_away)
        venue_row.addWidget(self._venue_neutral)
        venue_row.addStretch()
        left_col.addLayout(venue_row)

        # Auto-fill hint (shown when venue detected from match.json)
        self._venue_auto_hint = QLabel("")
        self._venue_auto_hint.setStyleSheet("color: #8888A0; font-size: 10px; font-style: italic;")
        self._venue_auto_hint.setVisible(False)
        left_col.addWidget(self._venue_auto_hint)

        left_col.addStretch()
        columns.addLayout(left_col, stretch=1)

        # ── Vertical separator ──
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setStyleSheet("color: #404060;")
        columns.addWidget(vsep)

        # ═══ RIGHT COLUMN: Annotation Settings ═══════════════════
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        # ── Annotation Mode ──
        self._mode_label = QLabel(t("session.annotation_mode_label"))
        self._mode_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        right_col.addWidget(self._mode_label)

        mode_row = QHBoxLayout()
        self._mode_group = QButtonGroup(self)
        self._manual_radio = QRadioButton(t("session.mode_manual"))
        self._manual_radio.setChecked(True)
        self._ai_radio = QRadioButton(t("session.mode_ai_assisted"))
        if not AI_AVAILABLE:
            self._ai_radio.setEnabled(False)
            self._ai_radio.setToolTip(t("session.ai_unavailable_tooltip"))
        self._mode_group.addButton(self._manual_radio, 0)
        self._mode_group.addButton(self._ai_radio, 1)
        mode_row.addWidget(self._manual_radio)
        mode_row.addWidget(self._ai_radio)
        right_col.addLayout(mode_row)

        # Model selection
        model_row = QHBoxLayout()
        self._model_label = QLabel(t("session.model_label"))
        model_row.addWidget(self._model_label)
        self._model_combo = QComboBox()
        self._model_items = [
            ("Football — RF-DETR-n  (fast)", "football-rfdetr-n", "football"),
            ("Football — RF-DETR-s  (balanced)", "football-rfdetr-s", "football"),
            ("Football — RF-DETR-m  (accurate)", "football-rfdetr-m", "football"),
            ("Football — YOLO11n  (fast)", "football-yolo11n", "football"),
            ("Football — YOLO11s  (balanced)", "football-yolo11s", "football"),
            ("Football — YOLO11m  (accurate)", "football-yolo11m", "football"),
            ("COCO — YOLOv8n  (fast, 80 classes)", "yolov8n", "coco"),
            ("COCO — YOLOv8s  (balanced, 80 classes)", "yolov8s", "coco"),
            ("COCO — YOLOv8m  (accurate, 80 classes)", "yolov8m", "coco"),
            ("Custom model...", "custom", "custom"),
        ]
        for display, _key, _group in self._model_items:
            self._model_combo.addItem(display)
        # Default: Football — YOLO11s (index 4)
        self._model_combo.setCurrentIndex(4)
        self._model_combo.setEnabled(False)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        model_row.addWidget(self._model_combo, stretch=1)
        right_col.addLayout(model_row)

        # Model description line
        self._model_desc = QLabel(t("session.model_desc_football"))
        self._model_desc.setStyleSheet("color: #6A6A8A; font-size: 10px; padding-left: 4px;")
        self._model_desc.setWordWrap(True)
        self._model_desc.setVisible(False)
        right_col.addWidget(self._model_desc)

        # Custom model file picker (hidden by default)
        custom_row = QHBoxLayout()
        self._custom_model_input = QLineEdit()
        self._custom_model_input.setPlaceholderText(t("session.custom_model_placeholder"))
        self._custom_model_input.setReadOnly(True)
        self._custom_model_input.setVisible(False)
        custom_row.addWidget(self._custom_model_input, stretch=1)
        self._browse_model_btn = QPushButton(t("button.browse"))
        self._browse_model_btn.setVisible(False)
        self._browse_model_btn.clicked.connect(self._browse_custom_model)
        custom_row.addWidget(self._browse_model_btn)
        right_col.addLayout(custom_row)

        # Confidence slider
        conf_row = QHBoxLayout()
        self._conf_label = QLabel(t("session.confidence_label"))
        conf_row.addWidget(self._conf_label)
        self._conf_slider = QSlider(Qt.Orientation.Horizontal)
        self._conf_slider.setRange(10, 90)
        self._conf_slider.setValue(30)
        self._conf_slider.setEnabled(False)
        self._conf_slider.setFixedWidth(200)
        self._conf_value_label = QLabel("0.30")
        self._conf_value_label.setFixedWidth(35)
        self._conf_slider.valueChanged.connect(
            lambda v: self._conf_value_label.setText(f"{v / 100:.2f}")
        )
        conf_row.addWidget(self._conf_slider)
        conf_row.addWidget(self._conf_value_label)
        conf_row.addStretch()
        right_col.addLayout(conf_row)

        # Connect mode toggle
        self._mode_group.idToggled.connect(self._on_mode_toggled)

        # ── Separator before session defaults ──
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: #404060;")
        right_col.addWidget(sep3)

        self._defaults_label = QLabel(t("session.defaults_label"))
        self._defaults_label.setStyleSheet("color: #8888A0; font-size: 11px; font-weight: bold;")
        right_col.addWidget(self._defaults_label)

        # Build session-level radio groups dynamically from config array
        self._session_groups: dict[str, QButtonGroup] = {}
        self._session_boxes: list[QGroupBox] = []
        for dim in self._meta_opts.get("session_level", []):
            key = dim["key"]
            label = t(f"meta.label.{key}")
            options = dim.get("options", [])
            group = QButtonGroup(self)
            box = QGroupBox(label)
            box.setProperty("meta_key", key)
            box_layout = QHBoxLayout(box)
            for i, opt in enumerate(options):
                rb = QRadioButton(t(f"meta.opt.{opt}"))
                rb.setProperty("value", opt)
                group.addButton(rb, i)
                box_layout.addWidget(rb)
                if i == 0:
                    rb.setChecked(True)
            self._session_groups[key] = group
            self._session_boxes.append(box)
            right_col.addWidget(box)

        # Set better defaults for known keys
        if "lighting" in self._session_groups:
            for btn in self._session_groups["lighting"].buttons():
                if btn.property("value") == "floodlight":
                    btn.setChecked(True)
                    break

        right_col.addStretch()

        # ── Start button ──
        self._start_btn = QPushButton(t("button.start_annotating"))
        self._start_btn.setStyleSheet("""
            QPushButton {
                background: #F5A623; color: #1E1E2E; font-size: 14px;
                font-weight: bold; padding: 12px; border-radius: 6px;
            }
            QPushButton:hover { background: #FFB833; }
            QPushButton:disabled { background: #404060; color: #666; }
        """)
        self._start_btn.clicked.connect(self._on_start)
        right_col.addWidget(self._start_btn)

        columns.addLayout(right_col, stretch=1)
        layout.addLayout(columns, stretch=1)

        # Pre-fill roster from project config or fallback to default
        default_roster = None
        if self._project_config and self._project_config.exists:
            default_roster = self._project_config.get_home_roster_path()
        if not default_roster:
            fallback = Path(__file__).parent.parent / "rosters" / "atletico_madrid_2024-25.csv"
            if fallback.exists():
                default_roster = fallback
        if default_roster:
            self._roster_path = str(default_roster)
            self._roster_input.setText(str(default_roster))
            self._preview_roster(default_roster)

    # ── Team Mode switching ──

    def _on_team_mode_toggled(self, id: int, checked: bool):
        """Switch between One Team Mode and All Team Mode."""
        is_all_team = self._all_team_radio.isChecked()

        # Toggle One Team widgets
        for w in self._one_team_widgets:
            w.setVisible(not is_all_team)

        # Toggle All Team widgets
        for w in self._all_team_widgets:
            w.setVisible(is_all_team)

        # Update venue labels
        if is_all_team:
            self._update_venue_labels()
        else:
            self._venue_home.setText(t("session.venue_home"))
            self._venue_away.setText(t("session.venue_away"))
            self._venue_neutral.setText(t("session.venue_neutral"))

    def _update_venue_labels(self):
        """Update venue radio labels with team names (All Team Mode)."""
        if not self._all_team_radio.isChecked():
            return
        t1 = self._team1_combo.currentText().strip() or "Team 1"
        t2 = self._team2_combo.currentText().strip() or "Team 2"
        self._venue_home.setText(f"{t1} Home")
        self._venue_away.setText(f"{t2} Home")
        self._venue_neutral.setText(t("session.venue_neutral"))

    # ── Language switching ──

    def _update_lang_buttons(self):
        """Highlight the active language button."""
        for btn in self._lang_buttons:
            code = btn.property("lang_code")
            if code == self._selected_lang:
                btn.setStyleSheet(
                    "QPushButton { background: #F5A623; color: #1E1E2E; "
                    "font-weight: bold; font-size: 11px; border-radius: 4px; "
                    "padding: 4px 10px; border: none; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: #333348; color: #AAAACC; "
                    "font-size: 11px; border-radius: 4px; "
                    "padding: 4px 10px; border: 1px solid #555570; }"
                    "QPushButton:hover { background: #3A3A50; }"
                )

    def _on_language_changed(self, lang_code: str):
        """Reload i18n and update all translatable labels."""
        if lang_code == self._selected_lang:
            return
        self._selected_lang = lang_code
        config_dir = Path(__file__).parent.parent / "config"
        I18n.load(lang_code, config_dir)

        # Update all translatable text in the dialog
        self.setWindowTitle(t("session.window_title"))
        self._title_label.setText(t("main.window_title"))
        self._folder_label.setText(t("session.folder_label"))
        self._folder_input.setPlaceholderText(t("session.folder_placeholder"))
        self._browse_folder_btn.setText(t("button.browse"))
        self._roster_label.setText(t("session.roster_label"))
        self._roster_input.setPlaceholderText(t("session.roster_placeholder"))
        self._browse_roster_btn.setText(t("button.browse"))
        self._browse_squad_btn.setText(t("button.browse"))
        self._source_label.setText(t("session.source_label"))
        self._source_combo.lineEdit().setPlaceholderText(t("session.source_placeholder"))
        self._round_label.setText(t("session.round_label"))
        self._round_input.setPlaceholderText(t("session.round_placeholder"))
        self._opponent_label.setText(t("session.opponent_label"))
        self._opponent_combo.lineEdit().setPlaceholderText(t("session.opponent_placeholder"))
        self._venue_label.setText(t("session.venue_label"))
        if self._all_team_radio.isChecked():
            self._update_venue_labels()
        else:
            self._venue_home.setText(t("session.venue_home"))
            self._venue_away.setText(t("session.venue_away"))
            self._venue_neutral.setText(t("session.venue_neutral"))
        if self._venue_auto_hint.isVisible():
            self._venue_auto_hint.setText(t("session.venue_auto_detected"))
        self._defaults_label.setText(t("session.defaults_label"))
        self._mode_label.setText(t("session.annotation_mode_label"))
        self._manual_radio.setText(t("session.mode_manual"))
        self._ai_radio.setText(t("session.mode_ai_assisted"))
        if not AI_AVAILABLE:
            self._ai_radio.setToolTip(t("session.ai_unavailable_tooltip"))
        self._model_label.setText(t("session.model_label"))
        self._conf_label.setText(t("session.confidence_label"))
        self._custom_model_input.setPlaceholderText(t("session.custom_model_placeholder"))
        # Update model description if visible
        if self._model_desc.isVisible():
            self._on_model_changed(self._model_combo.currentIndex())
        self._start_btn.setText(t("button.start_annotating"))

        # Update session-level radio group labels and option text
        for box in self._session_boxes:
            key = box.property("meta_key")
            box.setTitle(t(f"meta.label.{key}"))
        for key, group in self._session_groups.items():
            for btn in group.buttons():
                opt_val = btn.property("value")
                btn.setText(t(f"meta.opt.{opt_val}"))

        self._update_lang_buttons()

        # Save language preference to project config
        if self._project_config and self._project_config.exists:
            self._project_config.set_language(lang_code)

    # ── Annotation Mode ──

    def _on_mode_toggled(self, id: int, checked: bool):
        ai_mode = self._ai_radio.isChecked()
        self._model_combo.setEnabled(ai_mode)
        self._conf_slider.setEnabled(ai_mode)
        self._model_desc.setVisible(ai_mode)
        if ai_mode:
            self._on_model_changed(self._model_combo.currentIndex())

    def _on_model_changed(self, index: int):
        if index < 0 or index >= len(self._model_items):
            return
        _display, _key, group = self._model_items[index]
        is_custom = (group == "custom")
        self._custom_model_input.setVisible(is_custom)
        self._browse_model_btn.setVisible(is_custom)
        # Update description
        if group == "football":
            self._model_desc.setText(t("session.model_desc_football"))
        elif group == "coco":
            self._model_desc.setText(t("session.model_desc_coco"))
        else:
            self._model_desc.setText(t("session.model_desc_custom"))

    def _browse_custom_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("dialog.select_model"), "",
            "PyTorch Models (*.pt);;All Files (*)",
        )
        if path:
            self._custom_model_input.setText(path)

    # ── File browsing ──

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, t("dialog.select_folder"))
        if folder:
            self._folder_path = folder
            self._folder_input.setText(folder)
            # Auto-detect squad.json in selected folder
            self._auto_detect_squad(folder)
            # Check for screenshotter bundle (match.json + frame_metadata.json)
            self._detect_bundle(folder)

    def _browse_roster(self):
        path, _ = QFileDialog.getOpenFileName(
            self, t("dialog.select_roster"),
            str(Path(__file__).parent.parent / "rosters"),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self._roster_path = path
            self._roster_input.setText(path)
            self._preview_roster(Path(path))

    def _browse_squad(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Squad File",
            str(Path(self._folder_path) if self._folder_path else Path.home()),
            "JSON Files (*.json);;All Files (*)",
        )
        if path:
            self._squad_path = path
            self._squad_input.setText(path)
            self._preview_squad(Path(path))

    def _generate_squad_from_folder(self):
        """Generate squad.json from a SquadList folder of player images."""
        from backend.squad_loader import (
            find_squad_list_folder, generate_squad_json, _IMAGE_EXTS,
        )

        # Try to find SquadList folder automatically first
        sl_folder = None
        if self._folder_path:
            sl_folder = find_squad_list_folder(self._folder_path)

        if not sl_folder:
            # Let user browse for it
            chosen = QFileDialog.getExistingDirectory(
                self, "Select SquadList Folder",
                str(Path(self._folder_path) if self._folder_path else Path.home()),
            )
            if not chosen:
                return
            sl_folder = Path(chosen)

        # Count valid images
        image_count = sum(
            1 for f in sl_folder.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
            and "_" in f.stem
        )
        if image_count == 0:
            self._squad_info.setText(
                "No valid player images found. Files should be named: {number}_{Name}.png"
            )
            self._squad_info.setStyleSheet("color: #E74C3C; font-size: 11px;")
            return

        # Determine output path: put squad.json next to the SquadList folder
        output_dir = sl_folder.parent
        output_path = output_dir / "squad.json"

        # Get team name from project config or roster
        team_name = ""
        if self._project_config and self._project_config.exists:
            team_name = self._project_config.team_name

        result = generate_squad_json(sl_folder, output_path, team_name=team_name)
        if result:
            self._squad_path = str(result)
            self._squad_input.setText(str(result))
            self._preview_squad(result)
            self._squad_info.setStyleSheet("color: #27AE60; font-size: 11px;")
            info_text = self._squad_info.text()
            self._squad_info.setText(
                f"Generated from {image_count} images in SquadList/  |  {info_text}"
            )
        else:
            self._squad_info.setText("Failed to generate squad.json — no valid images found")
            self._squad_info.setStyleSheet("color: #E74C3C; font-size: 11px;")

    def _detect_bundle(self, folder: str):
        """Detect screenshotter bundle and auto-fill session fields."""
        from backend.file_manager import FileManager

        try:
            self._detect_bundle_impl(folder)
        except Exception as e:
            logger.warning("Bundle detection failed: %s", e, exc_info=True)
            self._is_bundle = False
            self._bundle_banner.setVisible(False)
            # Fall back to venue-only auto-fill
            self._auto_fill_venue_from_match_json(folder)

    def _detect_bundle_impl(self, folder: str):
        """Internal bundle detection — may raise on unexpected data."""
        from backend.file_manager import FileManager

        if not FileManager.is_screenshotter_bundle(folder):
            # Not a bundle — just try venue auto-fill from match.json alone
            self._auto_fill_venue_from_match_json(folder)
            self._is_bundle = False
            self._bundle_banner.setVisible(False)
            return

        # ── Full bundle detected ──
        self._is_bundle = True
        bundle_root = FileManager.get_bundle_root(folder)
        match_data = FileManager.load_match_json(bundle_root)
        if not match_data:
            # match.json exists but is invalid
            self._is_bundle = False
            self._bundle_banner.setVisible(False)
            return

        self._bundle_match_data = match_data
        frame_meta = FileManager.load_frame_metadata(bundle_root)
        self._bundle_frame_count = len(frame_meta)

        # Auto-fill: Venue
        ha = match_data.get("home_away", "").upper()
        venue_mapping = {"H": self._venue_home, "A": self._venue_away, "N": self._venue_neutral}
        venue_btn = venue_mapping.get(ha)
        if venue_btn:
            venue_btn.setChecked(True)
            self._venue_auto_hint.setText(t("session.venue_auto_detected"))
            self._venue_auto_hint.setVisible(True)

        # Auto-fill: Opponent (One Team) and Team 1/Team 2 (All Team)
        opponent = match_data.get("opponent", "")
        if opponent:
            self._opponent_combo.setCurrentText(opponent)

        # Auto-fill All Team Mode fields from bundle data
        home_team_name = match_data.get("home_team_name", "")
        away_team_name = match_data.get("away_team_name", "")
        if home_team_name:
            self._team1_combo.setCurrentText(home_team_name)
        if away_team_name:
            self._team2_combo.setCurrentText(away_team_name)
        # If no explicit team names, derive from opponent + home_away
        if not home_team_name and opponent:
            team_name = ""
            if self._project_config and self._project_config.exists:
                team_name = self._project_config.team_name or ""
            if ha == "A":
                # Our team is away, opponent is home
                self._team1_combo.setCurrentText(opponent)
                if team_name:
                    self._team2_combo.setCurrentText(team_name)
            else:
                # Our team is home, opponent is away
                if team_name:
                    self._team1_combo.setCurrentText(team_name)
                self._team2_combo.setCurrentText(opponent)

        # Auto-fill: Competition
        competition = match_data.get("competition", "")
        if competition:
            # Try to match an existing item first
            idx = self._source_combo.findText(competition)
            if idx >= 0:
                self._source_combo.setCurrentIndex(idx)
            else:
                self._source_combo.setCurrentText(competition)

        # Auto-fill: Matchday / Round
        matchday = match_data.get("matchday", "")
        if matchday:
            self._round_input.setText(str(matchday))

        # Auto-fill: Date (store for result but no separate field)

        # Build banner text
        venue_label = {"H": "Home", "A": "Away", "N": "Neutral"}.get(ha, "")
        parts = []
        if matchday:
            parts.append(f"MD{matchday}")
        if opponent:
            parts.append(f"vs {opponent}")
        if venue_label:
            parts.append(f"({venue_label})")
        match_summary = " ".join(parts) if parts else "Match info loaded"
        frame_text = f"{self._bundle_frame_count} frames" if self._bundle_frame_count else "frames"

        self._bundle_banner.setText(
            f"\U0001F4C2 Screenshotter bundle detected\n"
            f"Match info auto-loaded: {match_summary}\n"
            f"{frame_text} ready for annotation"
        )
        self._bundle_banner.setVisible(True)

        # Check squad.json for empty players and show note
        self._check_bundle_squad(str(bundle_root))

    def _check_bundle_squad(self, folder: str):
        """Check squad.json in bundle for empty player lists."""
        from backend.squad_loader import load_squad_json
        squad_path = Path(folder) / "squad.json"
        if not squad_path.exists():
            return

        squad = load_squad_json(squad_path)
        if squad and squad.is_loaded:
            # Already handled by _auto_detect_squad — all good
            return

        # squad.json exists but players arrays are empty (placeholder)
        self._squad_info.setText(
            "Squad file found but has no players. "
            "Add players to squad.json or select a roster CSV."
        )
        self._squad_info.setStyleSheet("color: #E6A817; font-size: 11px;")

    def _auto_fill_venue_from_match_json(self, folder: str):
        """Auto-fill venue from match.json if present (non-bundle fallback)."""
        match_path = Path(folder) / "match.json"
        if not match_path.exists():
            self._venue_auto_hint.setVisible(False)
            return
        try:
            data = json.loads(match_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        ha = data.get("home_away", "").upper()
        mapping = {"H": self._venue_home, "A": self._venue_away, "N": self._venue_neutral}
        btn = mapping.get(ha)
        if btn:
            btn.setChecked(True)
            self._venue_auto_hint.setText(t("session.venue_auto_detected"))
            self._venue_auto_hint.setVisible(True)
        else:
            self._venue_auto_hint.setVisible(False)

        # Also populate team names for All Team Mode
        home_team_name = data.get("home_team_name", "")
        away_team_name = data.get("away_team_name", "")
        if home_team_name:
            self._team1_combo.setCurrentText(home_team_name)
        if away_team_name:
            self._team2_combo.setCurrentText(away_team_name)

    def _auto_detect_squad(self, folder: str):
        """Auto-detect squad.json or SquadList folder in the session folder."""
        from backend.squad_loader import find_squad_json, find_squad_list_folder, _IMAGE_EXTS

        # 1. Try to find existing squad.json
        found = find_squad_json(folder)
        if found:
            self._squad_path = str(found)
            self._squad_input.setText(str(found))
            self._preview_squad(found)
            return

        # 2. Check for SquadList folder and show hint
        sl_folder = find_squad_list_folder(folder)
        if sl_folder:
            image_count = sum(
                1 for f in sl_folder.iterdir()
                if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
                and "_" in f.stem
            )
            if image_count > 0:
                self._squad_path = ""
                self._squad_input.setText("")
                self._squad_info.setText(
                    f"SquadList/ found ({image_count} images) — "
                    f"click \"Generate from SquadList\" to create squad.json"
                )
                self._squad_info.setStyleSheet("color: #3498DB; font-size: 11px;")
                return

        # Nothing found
        self._squad_path = ""
        self._squad_input.setText("")
        self._squad_info.setText("")

    def _preview_squad(self, path: Path):
        """Show a brief preview of the squad.json contents."""
        from backend.squad_loader import load_squad_json
        squad = load_squad_json(path)
        if squad and squad.is_loaded:
            parts = []
            if squad.home_team.players:
                parts.append(f"Home: {squad.home_team.name or 'Team'} ({len(squad.home_team.players)} players)")
            if squad.away_team.players:
                parts.append(f"Away: {squad.away_team.name or 'Team'} ({len(squad.away_team.players)} players)")
            self._squad_info.setText(" | ".join(parts))
        else:
            self._squad_info.setText("Invalid squad.json file")

    def _preview_roster(self, path: Path):
        """Read first row of CSV to show team + season info."""
        import csv
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                row = next(reader, None)
                if row:
                    team = row.get("team", "?")
                    season = row.get("season", "?")
                    # Count players
                    count = 1
                    for _ in reader:
                        count += 1
                    self._roster_info.setText(t("session.roster_preview",
                                                team=team, season=season, count=count))
                else:
                    self._roster_info.setText(t("session.roster_empty"))
        except Exception:
            self._roster_info.setText(t("session.roster_error"))

    def _on_start(self):
        if not self._folder_path or not self._round_input.text().strip():
            return

        is_all_team = self._all_team_radio.isChecked()
        team_mode = "all_team" if is_all_team else "one_team"

        self._result = {
            "folder": self._folder_path,
            "roster": self._roster_path,
            "squad_json": self._squad_path,
            "source": self._source_combo.currentText(),
            "round": self._round_input.text().strip(),
            "language": self._selected_lang,
            "is_bundle": self._is_bundle,
            "team_mode": team_mode,
        }

        if is_all_team:
            # All Team Mode: Team 1 (home) and Team 2 (away)
            self._result["team1"] = self._team1_combo.currentText().strip()
            self._result["team2"] = self._team2_combo.currentText().strip()
            self._result["opponent"] = ""  # No single opponent in all-team mode
        else:
            # One Team Mode: single opponent
            self._result["opponent"] = self._opponent_combo.currentText().strip()
            self._result["team1"] = ""
            self._result["team2"] = ""

        # Venue
        venue_btn = self._venue_group.checkedButton()
        self._result["venue"] = venue_btn.property("value") if venue_btn else "home"
        # AI-Assisted mode settings
        if self._ai_radio.isChecked():
            model_idx = self._model_combo.currentIndex()
            _display, model_key, _group = self._model_items[model_idx]
            self._result["annotation_mode"] = "ai_assisted"
            if model_key == "custom":
                self._result["model_name"] = "custom"
                self._result["custom_model_path"] = self._custom_model_input.text()
            else:
                self._result["model_name"] = model_key
            self._result["model_confidence"] = self._conf_slider.value() / 100.0
        else:
            self._result["annotation_mode"] = "manual"
            self._result["model_name"] = ""
            self._result["model_confidence"] = 0.30

        # Collect session-level values from dynamic radio groups
        defaults = {"weather": "clear", "lighting": "floodlight"}
        for key, group in self._session_groups.items():
            btn = group.checkedButton()
            self._result[key] = btn.property("value") if btn else defaults.get(key, "")
        self.accept()

    def get_result(self) -> dict:
        return self._result
