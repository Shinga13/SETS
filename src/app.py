import os

from PySide6.QtCore import QSettings, Qt, QThread
from PySide6.QtGui import QFontDatabase, QTextOption
from PySide6.QtWidgets import QApplication, QFrame, QPlainTextEdit, QScrollArea, QTabWidget, QWidget

from .constants import (
    ACENTER, AHCENTER, ALEFT, ARIGHT, ATOP, CAREERS, FACTIONS, PRIMARY_SPECS, SCROLLOFF, SCROLLON,
    SECONDARY_SPECS, SMAXMAX, SMAXMIN, SMINMAX, SMINMIN)
from .iofunc import create_folder, get_asset_path, load_icon, store_json
from .subwindows import ItemEditor, Picker, ShipSelector
from .widgets import (
    Cache, ContextMenu, GridLayout, HBoxLayout, ImageLabel, ShipButton, ShipImage, VBoxLayout,
    WidgetStorage)

# only for developing; allows to terminate the qt event loop with keyboard interrupt
from signal import signal, SIGINT, SIG_DFL
signal(SIGINT, SIG_DFL)


class SETS():

    from .callbacks import (
            clear_all, clear_slot, clear_build_callback, copy_equipment_item, edit_equipment_item,
            elite_callback, faction_combo_callback, load_build_callback, open_wiki_context,
            paste_equipment_item, save_build_callback, set_build_item, select_ship,
            ship_info_callback, spec_combo_callback, species_combo_callback, switch_main_tab,
            tier_callback)
    from .datafunctions import autosave, cache_skills, empty_build, init_backend
    from .splash import enter_splash, exit_splash, splash_text
    from .style import (
            create_style_sheet, get_style, get_style_class, prepare_tooltip_css, theme_font)
    from .widgetbuilder import (
            create_boff_station_ground, create_boff_station_space, create_build_section,
            create_button, create_button_series, create_checkbox, create_combo_box,
            create_doff_section, create_entry, create_frame, create_item_button, create_label,
            create_personal_trait_section, create_skill_button_ground, create_skill_group_space,
            create_starship_trait_section)

    app_dir = None
    # (release version, dev version)
    versions = ('', '')
    # see main.py for contents
    config = {}
    # see main.py for contents
    theme = {}
    # see main.py for defaults
    settings: QSettings
    # stores widgets that need to be accessed from outside their creating function
    widgets: WidgetStorage
    # stores refined cargo data
    cache: Cache
    # stores current build
    build: dict
    # height of items
    box_height: int
    # width of items
    box_width: int
    # for picking items
    picker_window: Picker
    # for selecting ships
    ship_selector_window: ShipSelector
    # for editing equipment items
    edit_window: ItemEditor
    # context menu for equipment
    context_menu: ContextMenu

    def __init__(self, theme, args, path, config, versions):
        """
        Creates new Instance of SETS

        Parameters:
        - :param version: version of the app
        - :param theme: dict -> default theme
        - :param args: command line arguments
        - :param path: absolute path to directory containing the main.py file
        - :param config: app configuration (!= settings these are not changed by the user)
        """
        self.versions = versions
        self.theme = theme
        self.args = args
        self.app_dir = path
        self.config = config
        self.widgets = WidgetStorage()
        self.cache = Cache()
        self.init_settings()
        self.init_config()
        self.prepare_tooltip_css()
        self.init_environment()
        self.app, self.window = self.create_main_window()
        self.building = True
        self.build = self.empty_build()
        self.setup_main_layout()
        self.picker_window = Picker(self, self.window)
        self.edit_window = ItemEditor(self, self.window)
        self.ship_selector_window = ShipSelector(self, self.window)
        self.context_menu = self.create_context_menu()
        self.window.show()
        self.init_backend()

    def run(self) -> int:
        """
        Runs the event loop.

        :return: exit code of event loop
        """
        return self.app.exec()

    def init_settings(self):
        """
        Prepares settings. Loads stored settings. Saves current settings for next startup.
        """
        settings_path = os.path.abspath(self.app_dir + self.config['settings_path'])
        self.settings = QSettings(settings_path, QSettings.Format.IniFormat)
        for setting, value in self.config['default_settings'].items():
            if self.settings.value(setting, None) is None:
                self.settings.setValue(setting, value)

    def init_config(self):
        """
        Prepares config.
        """
        config_folder = os.path.abspath(
                self.app_dir + self.config['config_folder_path'])
        self.config['config_folder_path'] = config_folder
        for folder, path in self.config['config_subfolders'].items():
            self.config['config_subfolders'][folder] = config_folder + path
        self.config['autosave_filename'] = f'{config_folder}\\{self.config['autosave_filename']}'
        self.config['ui_scale'] = self.settings.value('ui_scale', type=float)
        self.box_width = self.config['box_width'] * self.config['ui_scale'] * 0.8
        self.box_height = self.config['box_height'] * self.config['ui_scale'] * 0.8

    def init_environment(self):
        """
        Creates required folders if necessary.
        """
        create_folder(self.config['config_folder_path'])
        create_folder(self.config['config_subfolders']['library'])
        create_folder(self.config['config_subfolders']['cache'])
        create_folder(self.config['config_subfolders']['cargo'])
        create_folder(self.config['config_subfolders']['images'])
        create_folder(self.config['config_subfolders']['ship_images'])
        if not os.path.exists(self.config['autosave_filename']):
            store_json(self.empty_build(), self.config['autosave_filename'])

    def main_window_close_callback(self, event):
        """
        Executed when application is closed.
        """
        window_geometry = self.window.saveGeometry()
        self.settings.setValue('geometry', window_geometry)
        self.autosave()
        event.accept()

    # ----------------------------------------------------------------------------------------------
    # GUI functions below
    # ----------------------------------------------------------------------------------------------

    def create_main_window(self, argv=[]) -> tuple[QApplication, QWidget]:
        """
        Creates and initializes main window

        :return: QApplication, QWidget
        """
        app = QApplication(argv)
        font_database = QFontDatabase()
        font_database.addApplicationFont(
                get_asset_path('Overpass-VariableFont_wght.ttf', self.app_dir))
        app.setStyleSheet(self.create_style_sheet(self.theme['app']['style']))
        window = QWidget()
        window.setWindowIcon(load_icon('SETS_icon_small.png', self.app_dir))
        window.setWindowTitle('STO Equipment and Trait Selector')
        if self.settings.value('geometry'):
            window.restoreGeometry(self.settings.value('geometry'))
        window.closeEvent = self.main_window_close_callback
        app.focusWindowChanged.connect(self.hide_tooltips)
        QThread.currentThread().setPriority(QThread.Priority.TimeCriticalPriority)
        return app, window

    def setup_main_layout(self):
        """
        Creates the main layout and places it into the main window.
        """
        # master layout: banner, borders and splash screen
        layout = VBoxLayout(margins=0, spacing=0)
        background_frame = self.create_frame(
                style_override={'background-color': '@sets'}, size_policy=SMINMIN)
        layout.addWidget(background_frame)
        self.window.setLayout(layout)
        main_layout = VBoxLayout(margins=0, spacing=0)
        banner = ImageLabel(get_asset_path('sets_banner.png', self.app_dir), (2880, 126))
        main_layout.addWidget(banner)
        frame_width = 8 * self.config['ui_scale']
        tabber_layout = VBoxLayout(margins=frame_width, spacing=0)
        splash_tabber = QTabWidget()
        splash_tabber.setStyleSheet(self.get_style_class('QTabWidget', 'tabber'))
        splash_tabber.tabBar().setStyleSheet(self.get_style_class('QTabBar', 'tabber_tab'))
        splash_tabber.setSizePolicy(SMINMIN)
        self.widgets.splash_tabber = splash_tabber
        tabber_layout.addWidget(splash_tabber)
        main_layout.addLayout(tabber_layout)
        background_frame.setLayout(main_layout)
        content_frame = self.create_frame()
        splash_frame = self.create_frame()
        splash_tabber.addTab(content_frame, 'Main')
        splash_tabber.addTab(splash_frame, 'Splash')
        self.setup_splash(splash_frame)

        content_layout = GridLayout(margins=0, spacing=0)
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 4)

        margin = 3 * self.config['ui_scale']
        menu_layout = GridLayout(margins=(margin, margin, margin, 0), spacing=0)
        menu_layout.setColumnStretch(0, 2)
        menu_layout.setColumnStretch(1, 5)
        menu_layout.setColumnStretch(2, 2)
        left_button_group = {
            'Save': {'callback': self.save_build_callback},
            'Open': {'callback': self.load_build_callback},
            'Clear': {'callback': self.clear_build_callback},
            'Clear all': {'callback': self.clear_all}
        }
        menu_layout.addLayout(self.create_button_series(left_button_group), 0, 0, ALEFT | ATOP)
        center_button_group = {
            'default': {'font': ('Overpass', 16, 'medium')},
            'SPACE': {'callback': lambda: self.switch_main_tab(0), 'stretch': 1, 'size': SMINMAX},
            'GROUND': {'callback': lambda: self.switch_main_tab(1), 'stretch': 1, 'size': SMINMAX},
            'SPACE SKILLS': {
                'callback': lambda: self.switch_main_tab(2),
                'stretch': 1,
                'size': SMINMAX
            },
            'GROUND SKILLS': {
                'callback': lambda: self.switch_main_tab(3),
                'stretch': 1,
                'size': SMINMAX
            }
        }
        center_buttons = self.create_button_series(center_button_group, 'heavy_button')
        menu_layout.addLayout(center_buttons, 0, 1)
        right_button_group = {
            'Export': {'callback': lambda: None},
            'Settings': {'callback': lambda: self.switch_main_tab(5)},
        }
        menu_layout.addLayout(self.create_button_series(right_button_group), 0, 2, ARIGHT | ATOP)
        content_layout.addLayout(menu_layout, 0, 0, 1, 2)

        # sidebar
        sidebar = self.create_frame(size_policy=SMINMIN)
        self.widgets.sidebar = sidebar
        sidebar_layout = GridLayout(margins=0, spacing=0)

        sidebar_tabber = QTabWidget()
        sidebar_tabber.setStyleSheet(self.get_style_class('QTabWidget', 'tabber'))
        sidebar_tabber.tabBar().setStyleSheet(self.get_style_class('QTabBar', 'tabber_tab'))
        sidebar_tabber.setSizePolicy(SMINMIN)
        self.widgets.sidebar_tabber = sidebar_tabber
        sidebar_tab_names = (
                'space', 'ground', 'space_skills', 'ground_skills', 'empty', 'settings')
        for tab_name in sidebar_tab_names:
            tab_frame = self.create_frame()
            sidebar_tabber.addTab(tab_frame, tab_name)
            self.widgets.sidebar_frames.append(tab_frame)
        self.setup_ship_frame()
        sidebar_layout.addWidget(sidebar_tabber, 0, 0)

        character_tabber = QTabWidget()
        character_tabber.setStyleSheet(self.get_style_class('QTabWidget', 'tabber'))
        character_tabber.tabBar().setStyleSheet(self.get_style_class('QTabBar', 'tabber_tab'))
        character_tabber.setSizePolicy(SMINMAX)
        self.widgets.character_tabber = character_tabber
        char_frame = self.create_frame()
        self.setup_character_frame(char_frame)
        character_tabber.addTab(char_frame, 'char')
        empty_frame = self.create_frame()
        character_tabber.addTab(empty_frame, 'empty')
        settings_frame = self.create_frame()
        character_tabber.addTab(settings_frame, 'settings')
        self.widgets.character_frames = [char_frame, empty_frame, settings_frame]
        sidebar_layout.addWidget(character_tabber, 1, 0)

        seperator = self.create_frame(size_policy=SMAXMIN, style_override={
                'background-color': '@sets', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        seperator.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        sidebar_layout.addWidget(seperator, 0, 1, 2, 1)
        sidebar.setLayout(sidebar_layout)
        content_layout.addWidget(sidebar, 1, 0)

        # build section
        build_tabber = QTabWidget()
        build_tabber.setStyleSheet(self.get_style_class('QTabWidget', 'tabber'))
        build_tabber.tabBar().setStyleSheet(self.get_style_class('QTabBar', 'tabber_tab'))
        build_tabber.setSizePolicy(SMINMIN)
        self.widgets.build_tabber = build_tabber
        build_tab_names = (
                'space_build', 'ground_build', 'space_skills', 'ground_skills', 'library',
                'settings')
        for tab_name in build_tab_names:
            tab_frame = self.create_frame()
            build_tabber.addTab(tab_frame, tab_name)
            self.widgets.build_frames.append(tab_frame)
        content_layout.addWidget(build_tabber, 1, 1)
        self.setup_build_frames()

        content_frame.setLayout(content_layout)

    def setup_ship_frame(self):
        """
        Creates ship info frame
        """
        frame = self.widgets.sidebar_frames[0]
        csp = self.theme['defaults']['csp'] * self.config['ui_scale']
        layout = VBoxLayout(margins=csp, spacing=csp)

        image_frame = self.create_frame(size_policy=SMINMIN)
        image_layout = GridLayout(margins=0, spacing=0)
        ship_image = ShipImage()
        ship_image.setSizePolicy(SMINMIN)
        self.widgets.ship['image'] = ship_image
        image_layout.addWidget(ship_image, 0, 0)
        image_frame.setLayout(image_layout)
        layout.addWidget(image_frame, stretch=1)

        ship_frame = self.create_frame(size_policy=SMINMIN)
        ship_layout = GridLayout(margins=0, spacing=csp)
        ship_layout.setRowStretch(4, 1)
        ship_layout.setColumnStretch(2, 1)
        ship_selector = ShipButton('<Pick Ship>')
        ship_selector.setSizePolicy(SMINMAX)
        ship_selector.setStyleSheet(
                self.get_style_class('ShipButton', 'button', override={'margin': 0}))
        ship_selector.setFont(self.theme_font(font_spec='@subhead'))
        ship_selector.clicked.connect(self.select_ship)
        self.widgets.ship['button'] = ship_selector
        ship_layout.addWidget(ship_selector, 0, 0, 1, 3, alignment=ATOP)
        tier_label = self.create_label('Ship Tier:')
        ship_layout.addWidget(tier_label, 1, 0)
        tier_combo = self.create_combo_box()
        tier_combo.currentTextChanged.connect(self.tier_callback)
        tier_combo.setSizePolicy(SMAXMAX)
        self.widgets.ship['tier'] = tier_combo
        ship_layout.addWidget(tier_combo, 1, 1, alignment=ALEFT)
        info_button = self.create_button('Ship Info', style_override={'margin': 0})
        info_button.clicked.connect(self.ship_info_callback)
        ship_layout.addWidget(info_button, 1, 2, alignment=ARIGHT)
        name_label = self.create_label('Ship Name:')
        ship_layout.addWidget(name_label, 2, 0)
        name_entry = self.create_entry()
        name_entry.editingFinished.connect(
                lambda: self.set_build_item(self.build['space'], 'ship_name', name_entry.text()))
        self.widgets.ship['name'] = name_entry
        name_entry.setSizePolicy(SMINMAX)
        ship_layout.addWidget(name_entry, 2, 1, 1, 2)
        desc_label = self.create_label('Build Description:')
        ship_layout.addWidget(desc_label, 3, 0, 1, 3)
        desc_edit = QPlainTextEdit()
        desc_edit.setSizePolicy(SMINMIN)
        desc_edit.setStyleSheet(self.get_style_class('QPlainTextEdit', 'textedit'))
        desc_edit.setFont(self.theme_font('textedit'))
        desc_edit.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        desc_edit.textChanged.connect(lambda: self.set_build_item(
                self.build['space'], 'ship_desc', desc_edit.toPlainText(), autosave=False))
        self.widgets.ship['desc'] = desc_edit
        ship_layout.addWidget(desc_edit, 4, 0, 1, 3)
        ship_frame.setLayout(ship_layout)
        layout.addWidget(ship_frame, stretch=2)
        frame.setLayout(layout)

    def setup_build_frames(self):
        """
        Creates build areas
        """
        self.setup_space_build_frame()
        self.setup_ground_build_frame()
        self.cache_skills()
        self.setup_space_skill_frame()
        self.setup_ground_skill_frame()

    def setup_space_build_frame(self):
        """
        Creates space build layout
        """
        frame = self.widgets.build_frames[0]
        isp = self.theme['defaults']['isp'] * 2 * self.config['ui_scale']
        layout = GridLayout(margins=isp, spacing=isp)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(10, 1)
        layout.setRowStretch(7, 1)

        # Equipment
        fore_layout = self.create_build_section('Fore Weapons', 5, 'space', 'fore_weapons', True)
        layout.addLayout(fore_layout, 0, 1, alignment=ALEFT)
        aft_layout = self.create_build_section(
                'Aft Weapons', 5, 'space', 'aft_weapons', True, 'aft_weapons_label')
        layout.addLayout(aft_layout, 1, 1, alignment=ALEFT)
        exp_layout = self.create_build_section(
                'Experimental Weapon', 1, 'space', 'experimental', True, 'experimental_label')
        layout.addLayout(exp_layout, 2, 1, alignment=ALEFT)
        device_layout = self.create_build_section('Devices', 6, 'space', 'devices', True)
        layout.addLayout(device_layout, 3, 1, alignment=ALEFT)
        hangar_layout = self.create_build_section(
                'Hangars', 2, 'space', 'hangars', True, 'hangars_label')
        layout.addLayout(hangar_layout, 4, 1, alignment=ALEFT)
        sep1 = self.create_frame(size_policy=SMAXMIN, style_override={
            'background-color': '@bg', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        sep1.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        layout.addWidget(sep1, 0, 2, 5, 1)

        deflector_layout = self.create_build_section('Deflector', 1, 'space', 'deflector', True)
        layout.addLayout(deflector_layout, 0, 3, alignment=ALEFT)
        secdef_layout = self.create_build_section(
                'Sec-Def', 1, 'space', 'sec_def', True, 'sec_def_label')
        layout.addLayout(secdef_layout, 1, 3, alignment=ALEFT)
        engine_layout = self.create_build_section('Engines', 1, 'space', 'engines', True)
        layout.addLayout(engine_layout, 2, 3, alignment=ALEFT)
        warp_layout = self.create_build_section('Warp Core', 1, 'space', 'core', True)
        layout.addLayout(warp_layout, 3, 3, alignment=ALEFT)
        shield_layout = self.create_build_section('Shield', 1, 'space', 'shield', True)
        layout.addLayout(shield_layout, 4, 3, alignment=ALEFT)
        sep2 = self.create_frame(size_policy=SMAXMIN, style_override={
            'background-color': '@bg', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        sep2.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        layout.addWidget(sep2, 0, 4, 5, 1)

        uni_layout = self.create_build_section(
                'Universal Consoles', 3, 'space', 'uni_consoles', True, 'uni_consoles_label')
        layout.addLayout(uni_layout, 0, 5, alignment=ALEFT)
        eng_layout = self.create_build_section(
                'Engineering Consoles', 5, 'space', 'eng_consoles', True, 'eng_consoles_label')
        layout.addLayout(eng_layout, 1, 5, alignment=ALEFT)
        sci_layout = self.create_build_section(
                'Science Consoles', 5, 'space', 'sci_consoles', True, 'sci_consoles_label')
        layout.addLayout(sci_layout, 2, 5, alignment=ALEFT)
        tac_layout = self.create_build_section(
                'Tactical Consoles', 5, 'space', 'tac_consoles', True, 'tac_consoles_label')
        layout.addLayout(tac_layout, 3, 5, alignment=ALEFT)
        sep3 = self.create_frame(size_policy=SMAXMIN, style_override={
            'background-color': '@bg', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        sep3.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        layout.addWidget(sep3, 0, 6, 5, 1)

        # Boffs
        boff_1_layout = self.create_boff_station_space('Universal', 'Miracle Worker', boff_id=0)
        layout.addLayout(boff_1_layout, 0, 7, alignment=ALEFT)
        boff_2_layout = self.create_boff_station_space('Universal', 'Command', boff_id=1)
        layout.addLayout(boff_2_layout, 1, 7, alignment=ALEFT)
        boff_3_layout = self.create_boff_station_space('Universal', 'Intelligence', boff_id=2)
        layout.addLayout(boff_3_layout, 2, 7, alignment=ALEFT)
        boff_4_layout = self.create_boff_station_space('Universal', 'Pilot', boff_id=3)
        layout.addLayout(boff_4_layout, 3, 7, alignment=ALEFT)
        boff_5_layout = self.create_boff_station_space('Universal', 'Temporal', boff_id=4)
        layout.addLayout(boff_5_layout, 4, 7, alignment=ALEFT)
        boff_6_layout = self.create_boff_station_space('Universal', boff_id=5)
        width_placeholder = self.create_combo_box(size_policy=SMAXMAX)
        width_placeholder.addItem('Engineering / Miracle Worker')
        width_placeholder_sizepolicy = width_placeholder.sizePolicy()
        width_placeholder_sizepolicy.setRetainSizeWhenHidden(True)
        width_placeholder.setSizePolicy(width_placeholder_sizepolicy)
        width_placeholder.setFixedHeight(1)
        boff_6_layout.addWidget(width_placeholder, 2, 0, 1, 4)
        width_placeholder.hide()
        layout.addLayout(boff_6_layout, 5, 7, alignment=ALEFT)
        # no seperator here as the width placehoder takes care of it

        # Traits
        trait_layout = GridLayout(margins=0, spacing=isp)
        personal_trait_layout = self.create_personal_trait_section('space')
        trait_layout.addLayout(personal_trait_layout, 0, 0, alignment=ALEFT)
        starship_trait_layout = self.create_starship_trait_section()
        trait_layout.addLayout(starship_trait_layout, 1, 0)
        rep_trait_layout = self.create_build_section('Reputation Traits', 5, 'space', 'rep_traits')
        trait_layout.addLayout(rep_trait_layout, 2, 0)
        active_trait_layout = self.create_build_section(
                'Active Reputation Traits', 5, 'space', 'active_rep_traits')
        trait_layout.addLayout(active_trait_layout, 3, 0)
        layout.addLayout(trait_layout, 0, 9, 6, 1, alignment=ATOP)

        # Doffs
        spacing = self.theme['defaults']['bw'] * self.config['ui_scale']
        doff_container = self.create_frame(size_policy=SMINMAX)
        doff_container_layout = VBoxLayout(spacing=spacing * 2)
        doff_label = self.create_label('Space Duty Officers')
        doff_container_layout.addWidget(doff_label, alignment=ALEFT)
        doff_frame = self.create_frame('doff_frame', size_policy=SMINMAX)
        doff_frame_layout = VBoxLayout()
        doff_style_nullifier = self.create_frame(size_policy=SMINMAX)
        doff_frame_layout.addWidget(doff_style_nullifier)
        doff_layout = self.create_doff_section('space')
        doff_style_nullifier.setLayout(doff_layout)
        doff_frame.setLayout(doff_frame_layout)
        doff_container_layout.addWidget(doff_frame)
        doff_container.setLayout(doff_container_layout)
        layout.addWidget(doff_container, 5, 1, 2, 5)

        frame.setLayout(layout)

    def setup_ground_build_frame(self):
        """
        Creates Ground build frame
        """
        frame = self.widgets.build_frames[1]
        isp = self.theme['defaults']['isp'] * 2 * self.config['ui_scale']
        layout = GridLayout(margins=isp, spacing=isp)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(8, 1)
        layout.setRowStretch(5, 1)

        # Equipment
        modules_layout = self.create_build_section('Kit Modules:', 6, 'ground', 'kit_modules', True)
        layout.addLayout(modules_layout, 0, 1, alignment=ALEFT)
        weapons_layout = self.create_build_section('Weapons:', 2, 'ground', 'weapons', True)
        layout.addLayout(weapons_layout, 1, 1, alignment=ALEFT)
        devices_layout = self.create_build_section('Devices:', 5, 'ground', 'ground_devices', True)
        layout.addLayout(devices_layout, 2, 1, alignment=ALEFT)
        sep1 = self.create_frame(size_policy=SMAXMIN, style_override={
            'background-color': '@bg', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        sep1.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        layout.addWidget(sep1, 0, 2)
        kit_layout = self.create_build_section('Kit Frame:', 1, 'ground', 'kit', True)
        layout.addLayout(kit_layout, 0, 3, alignment=ALEFT)
        armor_layout = self.create_build_section('Armor:', 1, 'ground', 'armor', True)
        layout.addLayout(armor_layout, 1, 3, alignment=ALEFT)
        ev_layout = self.create_build_section('EV Suit:', 1, 'ground', 'ev_suit', True)
        layout.addLayout(ev_layout, 2, 3, alignment=ALEFT)
        shield_layout = self.create_build_section('Shield:', 1, 'ground', 'personal_shield', True)
        layout.addLayout(shield_layout, 3, 3, alignment=ALEFT)
        sep2 = self.create_frame(size_policy=SMAXMIN, style_override={
            'background-color': '@bg', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        sep2.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        layout.addWidget(sep2, 0, 4)

        # Boffs
        boff_1_layout = self.create_boff_station_ground(boff_id=0)
        layout.addLayout(boff_1_layout, 0, 5, alignment=ALEFT)
        boff_2_layout = self.create_boff_station_ground(boff_id=1)
        layout.addLayout(boff_2_layout, 1, 5, alignment=ALEFT)
        boff_3_layout = self.create_boff_station_ground(boff_id=2)
        layout.addLayout(boff_3_layout, 2, 5, alignment=ALEFT)
        boff_4_layout = self.create_boff_station_ground(boff_id=3)
        layout.addLayout(boff_4_layout, 3, 5, alignment=ALEFT)
        sep3 = self.create_frame(size_policy=SMAXMIN, style_override={
            'background-color': '@bg', 'margin-top': '@isp', 'margin-bottom': '@isp'})
        sep3.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        layout.addWidget(sep3, 0, 6)

        # Traits
        trait_layout = GridLayout(margins=0, spacing=isp)
        personal_trait_layout = self.create_personal_trait_section('ground')
        trait_layout.addLayout(personal_trait_layout, 0, 0, alignment=ALEFT)
        rep_trait_layout = self.create_build_section('Reputation Traits', 5, 'ground', 'rep_traits')
        trait_layout.addLayout(rep_trait_layout, 1, 0)
        active_trait_layout = self.create_build_section(
                'Active Reputation Traits', 5, 'ground', 'active_rep_traits')
        trait_layout.addLayout(active_trait_layout, 2, 0)
        layout.addLayout(trait_layout, 0, 7, 4, 1, alignment=ATOP)

        # Doffs
        spacing = self.theme['defaults']['bw'] * self.config['ui_scale']
        doff_container = self.create_frame(size_policy=SMINMAX)
        doff_container_layout = VBoxLayout(spacing=spacing * 2)
        doff_label = self.create_label('Ground Duty Officers')
        doff_container_layout.addWidget(doff_label, alignment=ALEFT)
        doff_frame = self.create_frame('doff_frame', size_policy=SMINMAX)
        doff_frame_layout = VBoxLayout()
        doff_style_nullifier = self.create_frame(size_policy=SMINMAX)
        doff_frame_layout.addWidget(doff_style_nullifier)
        doff_layout = self.create_doff_section('ground')
        doff_style_nullifier.setLayout(doff_layout)
        doff_frame.setLayout(doff_frame_layout)
        doff_container_layout.addWidget(doff_frame)
        doff_container.setLayout(doff_container_layout)
        layout.addWidget(doff_container, 4, 1, 1, 7)

        frame.setLayout(layout)

    def setup_character_frame(self, frame: QFrame):
        """
        Creates character customization area.
        """
        csp = self.theme['defaults']['csp'] * self.config['ui_scale']
        layout = GridLayout(margins=csp, spacing=csp)
        layout.setColumnStretch(1, 1)
        seperator = self.create_frame(size_policy=SMINMAX, style_override={
                'background-color': '@sets', 'margin': '@isp'})
        sep = self.theme['defaults']['sep'] * self.config['ui_scale']
        seperator.setFixedHeight(sep)
        layout.addWidget(seperator, 0, 0, 1, 2, alignment=ATOP)  # ATOP makes it respect the margin?
        char_name = self.create_entry(placeholder='NAME')
        char_name.setAlignment(AHCENTER)
        char_name.setSizePolicy(SMINMAX)
        char_name.editingFinished.connect(
                lambda: self.set_build_item(self.build['captain'], 'name', char_name.text()))
        layout.addWidget(char_name, 1, 0, 1, 2)
        elite_label = self.create_label('Elite Captain')
        layout.addWidget(elite_label, 2, 0, alignment=ARIGHT)
        elite_checkbox = self.create_checkbox()
        elite_checkbox.checkStateChanged.connect(self.elite_callback)
        layout.addWidget(elite_checkbox, 2, 1, alignment=ALEFT)
        career_label = self.create_label('Captain Career')
        layout.addWidget(career_label, 3, 0, alignment=ARIGHT)
        career_combo = self.create_combo_box()
        career_combo.addItems({''} | CAREERS)
        career_combo.currentTextChanged.connect(
                lambda t: self.set_build_item(self.build['captain'], 'career', t))
        layout.addWidget(career_combo, 3, 1)
        faction_label = self.create_label('Faction')
        layout.addWidget(faction_label, 4, 0, alignment=ARIGHT)
        faction_combo = self.create_combo_box()
        faction_combo.addItems({''} | FACTIONS)
        faction_combo.currentTextChanged.connect(self.faction_combo_callback)
        layout.addWidget(faction_combo, 4, 1)
        species_label = self.create_label('Species')
        layout.addWidget(species_label, 5, 0, alignment=ARIGHT)
        species_combo = self.create_combo_box()
        species_combo.addItems({''})
        species_combo.currentTextChanged.connect(lambda t: self.species_combo_callback(t))
        layout.addWidget(species_combo, 5, 1)
        primary_label = self.create_label('Primary Spec')
        layout.addWidget(primary_label, 6, 0, alignment=ARIGHT)
        primary_combo = self.create_combo_box()
        primary_combo.addItems({''} | PRIMARY_SPECS)
        primary_combo.currentTextChanged.connect(lambda t: self.spec_combo_callback(True, t))
        layout.addWidget(primary_combo, 6, 1)
        secondary_label = self.create_label('Secondary Spec', style_override={'margin-bottom': 0})
        layout.addWidget(secondary_label, 7, 0, alignment=ARIGHT)
        secondary_combo = self.create_combo_box()
        secondary_combo.addItems({''} | PRIMARY_SPECS | SECONDARY_SPECS)
        secondary_combo.currentTextChanged.connect(lambda t: self.spec_combo_callback(False, t))
        layout.addWidget(secondary_combo, 7, 1)
        frame.setLayout(layout)
        self.widgets.character = {
            'name': char_name,
            'elite': elite_checkbox,
            'career': career_combo,
            'faction': faction_combo,
            'species': species_combo,
            'primary': primary_combo,
            'secondary': secondary_combo,
        }

    def setup_space_skill_frame(self):
        """
        Creates Space skill GUI
        """
        frame = self.widgets.build_frames[2]
        isp = self.theme['defaults']['isp'] * self.config['ui_scale']
        csp = self.theme['defaults']['csp'] * self.config['ui_scale']
        col_layout = GridLayout(margins=isp, spacing=csp)
        col_layout.setRowStretch(0, 1)
        col_layout.setColumnStretch(0, 3)
        col_layout.setColumnStretch(2, 1)
        scroll_frame = self.create_frame()
        scroll_area = QScrollArea()
        scroll_area.setSizePolicy(SMINMIN)
        scroll_area.setHorizontalScrollBarPolicy(SCROLLOFF)
        scroll_area.setVerticalScrollBarPolicy(SCROLLON)
        scroll_area.setAlignment(AHCENTER)
        col_layout.addWidget(scroll_area, 0, 0)
        scroll_layout = GridLayout(margins=isp, spacing=isp * 4)
        scroll_layout.setColumnStretch(0, 1)
        scroll_layout.setColumnStretch(1, 1)
        scroll_layout.setColumnStretch(2, 1)
        scroll_layout.setColumnStretch(3, 1)
        scroll_layout.setColumnStretch(4, 1)
        scroll_layout.setColumnStretch(5, 1)
        # skill tree
        for rank, skill_groups in enumerate(self.cache.skills['space']):
            for group_id, group_data in enumerate(skill_groups):
                id_offset = rank * 6 + (group_id % 2) * 3
                group_layout = self.create_skill_group_space(group_data, id_offset)
                scroll_layout.addLayout(group_layout, rank, group_id)

        scroll_frame.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_frame)
        seperator = self.create_frame(size_policy=SMAXMIN, style_override={
                'background-color': '@sets'})
        seperator.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        col_layout.addWidget(seperator, 0, 1)
        bonus_bar_container = self.create_frame(size_policy=SMINMIN)
        # bonus bars
        col_layout.addWidget(bonus_bar_container, 0, 2)
        frame.setLayout(col_layout)

    def setup_ground_skill_frame(self):
        """
        Creates Ground skill GUI
        """
        frame = self.widgets.build_frames[3]
        isp = self.theme['defaults']['isp'] * self.config['ui_scale']
        csp = self.theme['defaults']['csp'] * self.config['ui_scale']
        col_layout = GridLayout(margins=isp, spacing=csp)
        col_layout.setRowStretch(0, 1)
        col_layout.setColumnStretch(0, 3)
        col_layout.setColumnStretch(2, 1)
        tree_frame = self.create_frame(size_policy=SMINMIN)
        col_layout.addWidget(tree_frame, 0, 0)
        # skill tree
        tree_layout = GridLayout(spacing=5 * isp)
        tree_layout.setColumnStretch(0, 1)
        tree_layout.setColumnStretch(3, 1)
        tree_layout.setRowStretch(0, 1)
        tree_layout.setRowStretch(3, 1)
        skills = self.cache.skills['ground']
        group_layout = GridLayout(spacing=csp)
        group_layout.addWidget(self.create_skill_button_ground(skills[0], 0, 0), 0, 1)
        group_layout.addWidget(self.create_skill_button_ground(skills[0], 1, 1), 1, 1)
        group_layout.addWidget(self.create_skill_button_ground(skills[1], 2, 0), 1, 0)
        group_layout.addWidget(self.create_skill_button_ground(skills[1], 3, 1), 2, 0)
        group_layout.addWidget(self.create_skill_button_ground(skills[2], 4, 0), 1, 2)
        group_layout.addWidget(self.create_skill_button_ground(skills[2], 5, 1), 2, 2)
        tree_layout.addLayout(group_layout, 1, 1)
        group_layout = GridLayout(spacing=csp)
        group_layout.addWidget(self.create_skill_button_ground(skills[3], 0, 0), 0, 1)
        group_layout.addWidget(self.create_skill_button_ground(skills[3], 1, 1), 1, 1)
        group_layout.addWidget(self.create_skill_button_ground(skills[4], 2, 0), 1, 0)
        group_layout.addWidget(self.create_skill_button_ground(skills[4], 3, 1), 2, 0)
        group_layout.addWidget(self.create_skill_button_ground(skills[5], 4, 0), 1, 2)
        group_layout.addWidget(self.create_skill_button_ground(skills[5], 5, 1), 2, 2)
        tree_layout.addLayout(group_layout, 1, 2)
        group_layout = GridLayout(spacing=csp)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[6], 0, 0), 0, 0, 1, 2, alignment=AHCENTER)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[6], 1, 1), 1, 0, alignment=ARIGHT)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[7], 2, 0), 1, 1, alignment=ALEFT)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[7], 3, 1), 2, 1, alignment=ALEFT)
        tree_layout.addLayout(group_layout, 2, 1)
        group_layout = GridLayout(spacing=csp)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[8], 0, 0), 0, 0, 1, 2, alignment=AHCENTER)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[8], 1, 1), 1, 1, alignment=ALEFT)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[9], 2, 0), 1, 0, alignment=ARIGHT)
        group_layout.addWidget(
                self.create_skill_button_ground(skills[9], 3, 1), 2, 0, alignment=ARIGHT)
        tree_layout.addLayout(group_layout, 2, 2)

        tree_frame.setLayout(tree_layout)
        seperator = self.create_frame(size_policy=SMAXMIN, style_override={
                'background-color': '@sets'})
        seperator.setFixedWidth(self.theme['defaults']['sep'] * self.config['ui_scale'])
        col_layout.addWidget(seperator, 0, 1)
        bonus_bar_container = self.create_frame(size_policy=SMINMIN)
        # bonus bars
        col_layout.addWidget(bonus_bar_container, 0, 2)
        frame.setLayout(col_layout)

    def setup_splash(self, frame: QFrame):
        """
        Creates Splash screen.
        """
        layout = GridLayout(margins=0, spacing=0)
        layout.setRowStretch(0, 1)
        layout.setRowStretch(3, 1)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 3)
        loading_image = ImageLabel(get_asset_path('sets_loading.png', self.app_dir), (1, 1))
        layout.addWidget(loading_image, 1, 1)
        loading_label = self.create_label('Loading: ...', 'label_subhead')
        self.widgets.loading_label = loading_label
        layout.addWidget(loading_label, 2, 0, 1, 3, alignment=AHCENTER)
        frame.setLayout(layout)

    def create_context_menu(self) -> ContextMenu:
        """
        Creates context menu for rightclick operations on equipment items
        """
        menu = ContextMenu()
        menu.setStyleSheet(self.get_style_class('ContextMenu', 'context_menu'))
        menu.setFont(self.theme_font('context_menu'))
        menu.addAction(load_icon('copy.png', self.app_dir), 'Copy Item', self.copy_equipment_item)
        menu.addAction(
                load_icon('paste.png', self.app_dir), 'Paste Item', self.paste_equipment_item)
        menu.addAction(load_icon('clear.png', self.app_dir), 'Clear Slot', self.clear_slot)
        menu.addAction(
                load_icon('external_link.png', self.app_dir), 'Open Wiki', self.open_wiki_context)
        menu.addAction(load_icon('edit.png', self.app_dir), 'Edit Slot', self.edit_equipment_item)
        return menu

    def hide_tooltips(self):
        """
        Hides tooltip windows when main window isn't the active window anymore.
        """
        if not self.window.isActiveWindow():
            for window in self.app.topLevelWindows():
                if window.type() == Qt.WindowType.ToolTip:
                    window.hide()
