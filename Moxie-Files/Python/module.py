# README: Co-developed this file with my team. Eventually became the main author.

# README: This file takes in the data of a designer's interactive activity
# (called a "module") in the form of a JSON file and parses it to later
# correctly generate the desired speech and behaviors.

import csv
import inspect
import logging

from jinja2 import Environment, FileSystemLoader
from typing import List, Tuple, Any
import os

from build_scripts.patterns import pattern_macro_parser
from . import type_data
from .datatables import content_index
from .datatables.content_index import ContentIndexTable
from .module_type_data import ModuleTypeData
from ..logs import log
from ..objects.tags.content_tag import ContentTag
from ..objects.elements.flexible.type_data import FlexibleModuleComplete1
from ..objects.elements.utility.exits.type_data import ExitModule
from ..patterns import pattern
from ..patterns.pattern import Pattern
from ..utils import compiler_cache
from ...empath import document
from ...empath.boards import board
from ...empath.utils import utils
from ...renderer.filters import DEFINED_FILTERS
from ... import globals
from .... import EMPATH_PATTERNS_DIR


# These originated from the abbreviation csv table (now ModuleActivities.csv)
CONTENT_TYPES: List[str] = [
    "default",
    "conversation",
    "drawing",
    "pretend_play",
    "primary_mission",
    "mindfulness",
    "movement_game",
    "reading",
    "star_goal",
    "story"
]


class Module(document.Document):
    class EntryPoint:
        _MODULE_ENTRY_POINT_PATTERN_KEY = "pattern"
        _MODULE_ENTRY_POINT_PATTERN_SAMPLE_KEY = "patternSamples"
        _MODULE_ENTRY_POINT_RESPONSE_KEY = "linesCSV"
        _MODULE_ENTRY_POINT_CONTENT_ID_KEY = "contentID"
        _MODULE_ENTRY_POINT_IS_DEFAULT_ENTRY_KEY = "isDefaultEntry"
        _MODULE_ENTRY_POINT_IS_CONTENT_ID_ENTRY_KEY = "isContentIDEntry"
        _MODULE_ENTRY_POINT_IS_GLOBAL_ENTRY_KEY = "isGlobalEntry"
        _MODULE_ENTRY_POINT_CODE_KEY = "variables"

        _MODULE_GLOBAL_PATTERN_MACRO_NAME_KV_KEY = "pm_global_entry"

        name: str
        uuid: str

        entry_board_name: str
        entry_board: board.Board
        entry_topic: str

        pattern: str
        pattern_examples_pos: List[str]
        pattern_examples_neg: List[str]

        lines_csv: str
        pattern_macro_name: str

        content_id: str

        is_default_entry: bool
        is_content_id_entry: bool
        is_global_entry: bool

        init_code: str

        def __init__(self, _empath_mod, _module_data: dict, entry_type: str = ""):
            self.name = _module_data[_empath_mod._NAME_KEY].strip().upper().replace(" ", "_")
            self.validate_name(_empath_mod, entry_type)

            self.uuid = _module_data[_empath_mod._UUID_KEY]

            self.content_id = _module_data.get(self._MODULE_ENTRY_POINT_CONTENT_ID_KEY, "")
            self.entry_board_name = _module_data.get(_empath_mod._MODULE_START_BOARD_KEY, "")
            self.entry_board, self.entry_topic = self.get_board_info(_empath_mod, entry_type)

            self.init_code = _module_data.get(self._MODULE_ENTRY_POINT_CODE_KEY, "")

            self.is_default_entry = _module_data.get(self._MODULE_ENTRY_POINT_IS_DEFAULT_ENTRY_KEY, False)
            self.is_content_id_entry = _module_data.get(self._MODULE_ENTRY_POINT_IS_CONTENT_ID_ENTRY_KEY, False)
            
            # The old global entries are automatically considered a "global entry" in the new module entries system.
            # Standard module entries can decide where or not to be a "global entry" as well.
            if entry_type == "global":
                self.is_global_entry = True
            else:
                self.is_global_entry = _module_data.get(self._MODULE_ENTRY_POINT_IS_GLOBAL_ENTRY_KEY, False)

            if self.is_content_id_entry:
                self.validate_content_id(_empath_mod)

            if self.is_global_entry:
                self.lines_csv = self.get_entry_lines_csv(_empath_mod, _module_data, entry_type)
                self.pattern_macro_name = self.get_pattern_macro_name(_empath_mod)

                self.pattern = _module_data.get(self._MODULE_ENTRY_POINT_PATTERN_KEY, "").replace("\n", "")
                self.validate_pattern(_empath_mod, entry_type)
                self.pattern_examples_pos, self.pattern_examples_neg = self.get_pattern_samples(_empath_mod, _module_data, entry_type)

            else:
                self.lines_csv = ""
                self.pattern_macro_name = ""

                self.pattern = ""
                self.pattern_examples_pos = []
                self.pattern_examples_neg = []

        def validate_name(self, _empath_mod, entry_type: str):
            if not self.name:
                raise Exception(f"Every {entry_type} entry for '{_empath_mod.module_name}' MUST have an entry name. "
                                f"{log.context(_empath_mod, _empath_mod._NAME_KEY)}")

        def validate_pattern(self, _empath_mod, entry_type: str):
            if pattern.Pattern.is_empty_string(self.pattern):
                raise ValueError(f"Empty string or all-spaces as pattern is not allowed ({entry_type} pattern): "
                                 f"{_empath_mod.filename} {log.context(_empath_mod, self._MODULE_ENTRY_POINT_PATTERN_KEY)}")

            patterns_list = [self.pattern]
            for pat in patterns_list:
                pattern.Pattern.validate(pat, filepath=_empath_mod.filepath)

        def validate_content_id(self, _empath_mod):
            if not self.content_id:
                raise Exception(f"Every Content ID entry for '{_empath_mod.module_name}' MUST have an assigned Content ID. "
                                f"{log.context(_empath_mod, self._MODULE_ENTRY_POINT_CONTENT_ID_KEY)}")

        def get_pattern_samples(self, _empath_mod, _module_data: dict, entry_type: str) -> Tuple[list, list]:
            samples = Pattern.get_samples(_module_data,
                                            board=None,
                                            override_pattern_sample_key=self._MODULE_ENTRY_POINT_PATTERN_SAMPLE_KEY)
            _pattern_examples_pos, _pattern_examples_neg = samples
            if len(_pattern_examples_pos) < 1:
                raise Exception(f"Every {entry_type} entry pattern for '{_empath_mod.module_name}' MUST have at least one positive "
                                f"sample text {log.context(_empath_mod, self._MODULE_ENTRY_POINT_PATTERN_SAMPLE_KEY)}")

            return _pattern_examples_pos, _pattern_examples_neg

        def get_entry_lines_csv(self, _empath_mod, _module_data: dict, entry_type: str) -> str:
            if self._MODULE_ENTRY_POINT_RESPONSE_KEY not in _module_data or not _module_data[self._MODULE_ENTRY_POINT_RESPONSE_KEY]:
                raise Exception(f"Every {entry_type} entry for '{_empath_mod.module_name}' MUST have '{self._MODULE_ENTRY_POINT_RESPONSE_KEY}' assigned "
                                f"{log.context(_empath_mod, self._MODULE_ENTRY_POINT_RESPONSE_KEY)}")

            return _empath_mod.get_check_csv(_module_data[self._MODULE_ENTRY_POINT_RESPONSE_KEY], self._MODULE_ENTRY_POINT_RESPONSE_KEY,
                                             f"{_empath_mod.module_name} {entry_type} entry lines")

        def get_board_info(self, _empath_mod, entry_type: str) -> Tuple[str, str]:
            if not self.entry_board_name:
                raise Exception(f"Every {entry_type} entry for '{_empath_mod.module_name}' MUST have a '{_empath_mod._MODULE_START_BOARD_KEY}' assigned "
                                f"{log.context(_empath_mod, _empath_mod._MODULE_START_BOARD_KEY)}")

            _board = _empath_mod.get_board_by_name(self.entry_board_name)
            # Check start board is not excluded
            if _board is None:
                if _empath_mod.is_board_name_excluded(self.entry_board_name):
                    excluded_board = _empath_mod.get_board_by_name(self.entry_board_name,
                                                                  include_excluded_boards=True)

                    raise Exception(f"Start board '{self.entry_board_name}' (in {entry_type} entry) cannot be marked as 'excluded' "
                                    f"{log.context(excluded_board)}: file://{_empath_mod.filename}")

                raise Exception(f"Start board '{self.entry_board_name}' (in {entry_type} entry) cannot be found in document: "
                                f"file://{_empath_mod.filename} {log.context(_empath_mod, _empath_mod._MODULE_START_BOARD_KEY)}")

            # Check start board is not a function board with a missing/empty content ID
            elif _board.is_function_board() and not self.content_id:
                raise Exception(f"Start board (in {entry_type} entry) cannot be a function board with an empty content ID, "
                                f"which '{self.entry_board_name}' is {log.context(_board)}: file://{_empath_mod.filename}")

            _topic = _board.get_intro_topic()
            if _topic is None:
                raise Exception(f"Starting topic could not be found within '{self.entry_board_name}'. "
                                f"file://{_empath_mod.filename} {log.context(_empath_mod, _empath_mod._MODULE_START_BOARD_KEY)}")

            return _board, _topic

        def get_pattern_macro_name(self, _empath_mod) -> str:
            return f"{_empath_mod.module_id}_module_entry_{self.name}"
        
    _DEFAULT_MODULE_JINJA_TEMPLATE_DIR = "ModuleOverrides"
    _DEFAULT_MODULE_JINJA_TEMPLATE = "BaseTemplates/base_module_controller.jinja"
    _MODULE_SETTINGS_KEY = "moduleInfo"
    _MODULE_OVERRIDE_KEY = "moduleOverride"
    _MODULE_OVERRIDE_NONE_VALUE = "None"
    _MODULE_REPORT_KEY = "moduleCompletionReportToGRL"
    _MODULE_COMPLETION_KEY = "moduleCompletionMessage"
    _MODULE_TYPE_KEY = "moduleType"
    _MODULE_CONTEXT_KEY = "moduleContext"
    _THERAPY_CATEGORIES_KEY = "therapyCategories"

    _MODULE_STATUS_KEY = "documentStatus"
    _MODULE_STATUS_FINALIZED = "finalized"

    _UUID_KEY = "uuid"
    _MODULE_ID_KEY = "moduleId"
    _MODULE_NAME_KEY = "moduleName"
    # _MODULE_TAGS_KEY = "moduleTags"
    _MODULE_START_BOARD_KEY = "startBoard"
    _MODULE_CSV_RELATIVE_PATHS_KEY = "csvRelativePaths"

    _MODULE_AVAIL_GLOBAL_KEY = "availableGlobalEntry"
    _MODULE_GLOBAL_ENTRY_POINT_KEY = "globalEntryPoints"

    _MODULE_AVAIL_ROULETTE_KEY = "availableRoulette"
    _MODULE_ROULETTE_SUGGESTION_KEY = "rouletteSuggestionLinesCSV"
    _MODULE_ROULETTE_ENTRY_POINT_KEY = "rouletteEntryPoints"

    _MODULE_AVAIL_MODULE_KEY = "availableModuleEntry"
    _MODULE_ENTRY_POINT_KEY = "moduleEntryPoints"

    _MODULE_RETURNABLE = "moduleReturnable"
    _MODULE_RETURNABLE_CSV_KEY = "moduleReturnableCSV"

    _MODULE_REWARDING_BADGE_KEY = "isRewardingBadge"
    _MODULE_REWARDING_BADGE_NAME_KEY = "rewardBadgeIconName"

    _MODULE_LOCKED_KEY = "lockedByDefault"
    _MODULE_LOCKED_CSV_KEY = "lockedModuleLinesCSV"
    _MODULE_AVAIL_BEDTIME_KEY = "accessibleAtBedtime"
    _MODULE_AVAIL_BEDTIME_COLUMN_NAME = "bedtime"
    _MODULE_IS_BEDTIME_VALUES = ["true", "false"]
    _MODULE_IS_BEDTIME_TRUE_VALUES = ["true"]

    _MODULE_ICON_KEY = "moduleIcon"
    _MODULE_SFX_IN_KEY = "moduleTransInSFX"
    _MODULE_SFX_OUT_KEY = "moduleTransOutSFX"

    _CONTENT_TAG_KEY = "contentTags"

    boards: List[board.Board]
    index_tables: List[ContentIndexTable]

    uuid: str
    module_id: str
    module_name: str
    module_template_name: str
    does_report_completion: bool
    module_completion_message: str
    module_type: str
    module_context: str
    therapy_categories: List[str]

    start_board_name: str
    start_board: board.Board
    start_topic: str

    csv_paths: List[str]

    # IMPORTANT NOTE: "global entries" are module entries with patterns
    is_global: bool
    global_entries: List[EntryPoint]

    # IMPORTANT NOTE: "roulette entries" are currently deprecated
    is_roulette: bool
    roulette_suggestion_csv: str
    roulette_entries: List[EntryPoint]

    # IMPORTANT NOTE: holds all entries regardless of whether or not they have patterns
    is_module_entry: bool
    all_module_entries: List[EntryPoint]
    default_entry: EntryPoint

    is_locked: bool
    locked_csv: str

    is_returnable: bool
    return_csv: str

    is_bedtime: bool
    is_rewarding_badge: bool
    reward_badge_icon_name: str

    icon_name: str
    sfx_in_name: str
    sfx_out_name: str

    module_content_etags: List[ContentTag]

    document_status: str

    def __init__(self):
        super().__init__()
        self.is_bedtime = False
        self.is_global = False
        self.is_roulette = False
        self.is_locked = False
        self.is_returnable = False
        self.is_rewarding_badge = False

        self.global_entries = []
        self.roulette_entries = []
        self.all_module_entries = []

        self.module_content_tags = []

        self.default_entry = None

    @property
    def chat_content_indices(self) -> List[content_index.ChatConversationIndex]:
        result = []
        for index_table in self.index_tables:
            if index_table.is_chat:
                result.extend(index_table.content_indices)
        return result

    @property
    def excluded(self):
        return False

    def is_status_finalized(self) -> bool:
        return self.document_status == self._MODULE_STATUS_FINALIZED

    @classmethod
    def from_json(cls, file_data: dict, filename: str = None, shallow: bool = False, **kwargs):
        empath_mod = cls()
        module_data = file_data[cls._MODULE_SETTINGS_KEY]

        module_data_keys = module_data.keys()
        empath_mod.uuid = module_data[cls._UUID_KEY]
        empath_mod.module_id = module_data[cls._MODULE_ID_KEY]
        if len(empath_mod.module_id.replace(" ", "")) == 0:
            raise Exception(f"Module ID cannot be left blank! file://{empath_mod.filepath} {log.context(empath_mod, cls._MODULE_ID_KEY)}")
        empath_mod.index_tables = []

        if not shallow:
            # CSVs - doing this one early since function boards in this module might need data from index tables
            if cls._MODULE_CSV_RELATIVE_PATHS_KEY in module_data_keys:
                empath_mod.csv_paths = module_data[cls._MODULE_CSV_RELATIVE_PATHS_KEY]

                # Check and add any index table objects ONLY
                cache_file_obj = compiler_cache.get_instance().files.get(filename)
                for csv_path in empath_mod.csv_paths:
                    if not ContentIndexTable.is_index_table(csv_path):
                        raise Exception(f"Only index csv sheets are allowed in a module's 'CSV Relative Paths'. Found this csv '{csv_path}' "
                                        f"in '{empath_mod.module_id}' module. {log.context(empath_mod, cls._MODULE_CSV_RELATIVE_PATHS_KEY)}")

                    # Add all CSVs to be related to this module file
                    abs_path = os.path.join(globals.CHATSCRIPT_ROOT, "chatscript", csv_path)
                    if abs_path not in cache_file_obj.related_files:
                        cache_file_obj.related_files.append(abs_path)
                        compiler_cache.get_instance().files.add_related(abs_path, cache_file_obj)

                    # Retrieve the content ID index csv sheet
                    c_index_table = ContentIndexTable.from_csv(
                        csv_path,
                        module_id=empath_mod.module_id,
                        empath_file=filename)

                    for c_index in c_index_table.content_indices:
                        # Ensure every content ID is written in a valid way
                        if not c_index.content_id.replace("_", "").isalnum():
                            raise Exception(f"Every content ID in a module must contain only letters, numbers and/or underscores. "
                                            f"Found content ID '{c_index.content_id}' in '{empath_mod.module_id}' module {log.context(empath_mod)}")
                        # Add all related .CC files to be related to this .CM file
                        if c_index_table.is_chat:
                            if c_index.chat_object.filepath not in cache_file_obj.related_files:
                                cache_file_obj.related_files.append(c_index.chat_object.filepath)
                            compiler_cache.get_instance().files.add_related(c_index.chat_object.filepath, cache_file_obj)

                    empath_mod.index_tables.append(c_index_table)

        empath_mod = super().from_json(file_data=file_data, filename=filename, class_obj=empath_mod, module_id=empath_mod.module_id, shallow=shallow)

        # Constraints
        if not shallow:
            if empath_mod.uses_explicit_exits:
                module_exit_node_found = False
                num_exit_nodes = 0
                for _board in empath_mod.boards:
                    exit_nodes = _board.get_exit_nodes()
                    num_exit_nodes += len(exit_nodes)
                    for exit_node in exit_nodes:
                        if issubclass(exit_node.subtype_data.__class__, ExitModule):
                            module_exit_node_found = True
                            break
                    if module_exit_node_found:
                        break
                if not module_exit_node_found:
                    raise Exception(f"Module requires at least one instance of a '{ExitModule.__name__}' exit-node. "
                                    f"None were found out of {num_exit_nodes} exit-nodes in file://{empath_mod.filepath} {log.context(empath_mod)}")

            # Make sure at least one module complete node exists
            # TODO: Does NOT guarantee the node is hooked in the conversation's path.
            #       That can be something we test in topic-traversal instead
            mod_completion_nodes = []
            for b in empath_mod.boards:
                mod_completion_nodes.extend(b.get_nodes_with_subtype(FlexibleModuleComplete1))
            if len(mod_completion_nodes) < 1:
                raise Exception(f"Module requires at least one instance of '{FlexibleModuleComplete1.__name__}' node. "
                                f"file://{empath_mod.filepath} {log.context(empath_mod)}")
            else:
                # In lieu of a perfect solution, check the node at least has in and out connections as a partial test
                valid = False
                for n in mod_completion_nodes:
                    if len(n.connections_in) > 0 and len(n.connections_out) > 0:
                        valid = True
                        break
                if not valid:
                    raise Exception(f"Module '{FlexibleModuleComplete1.__name__}' node(s) must be connected. "
                                    f"file://{empath_mod.filepath} {log.context(empath_mod)}")

            # Check for module override
            empath_mod.module_template_name = cls._DEFAULT_MODULE_JINJA_TEMPLATE
            if cls._MODULE_OVERRIDE_KEY in module_data_keys:
                override_value = module_data[cls._MODULE_OVERRIDE_KEY]
                if override_value != cls._MODULE_OVERRIDE_NONE_VALUE:
                    empath_mod.module_template_name = os.path.join(cls._DEFAULT_MODULE_JINJA_TEMPLATE_DIR, override_value)
                    logging.debug(f"Module template overridden with '{empath_mod.module_template_name}'")
            if not os.path.exists(os.path.join(globals.JINJA_TEMPLATE_DIR, empath_mod.module_template_name)):
                raise FileNotFoundError(f"Module template file not found file://{os.path.join(globals.JINJA_TEMPLATE_DIR, empath_mod.module_template_name)}")
            if not shallow:
                cache_file_obj = compiler_cache.get_instance().files.get(filename)
                if empath_mod.module_template_name not in cache_file_obj.related_files:
                    cache_file_obj.related_files.append(os.path.join(globals.JINJA_TEMPLATE_DIR, empath_mod.module_template_name))

        if cls._MODULE_NAME_KEY in module_data_keys:
            empath_mod.module_name = module_data[cls._MODULE_NAME_KEY]
        else:
            empath_mod.module_name = empath_mod.module_id

        # Module Context
        if cls._MODULE_CONTEXT_KEY in module_data_keys:
            empath_mod.module_context = module_data[cls._MODULE_CONTEXT_KEY]
        else:
            empath_mod.module_context = ""

        # Therapy categories
        empath_mod.therapy_categories = []
        if cls._THERAPY_CATEGORIES_KEY in module_data_keys:
            for therapy_category in module_data[cls._THERAPY_CATEGORIES_KEY]:
                if module_data[cls._THERAPY_CATEGORIES_KEY][therapy_category]:
                    empath_mod.therapy_categories.append(therapy_category)

        # Activity reporting
        empath_mod.does_report_completion = module_data.get(cls._MODULE_REPORT_KEY, False)
        if cls._MODULE_COMPLETION_KEY in module_data_keys and \
                module_data[cls._MODULE_COMPLETION_KEY].replace(" ", "") != "":
            empath_mod.module_completion_message = module_data[cls._MODULE_COMPLETION_KEY]
        else:
            empath_mod.module_completion_message = f"Completed {empath_mod.module_name}."
        if cls._MODULE_TYPE_KEY in module_data_keys:
            empath_mod.module_type = module_data[cls._MODULE_TYPE_KEY]
        else:
            empath_mod.module_type = CONTENT_TYPES[0]

        # Badge rewards
        if cls._MODULE_REWARDING_BADGE_KEY in module_data_keys:
            empath_mod.is_rewarding_badge = module_data[cls._MODULE_REWARDING_BADGE_KEY]

            if cls._MODULE_REWARDING_BADGE_NAME_KEY not in module_data_keys:
                raise Exception(f"Badge rewarding module '{empath_mod.module_id}' does not have badge icon name "
                                f"data serialized to '{cls._MODULE_REWARDING_BADGE_NAME_KEY}' "
                                f"{log.context(empath_mod)}")

            empath_mod.reward_badge_icon_name = module_data[cls._MODULE_REWARDING_BADGE_NAME_KEY]
        else:
            empath_mod.is_rewarding_badge = False

        # Module Entry (i.e. Default, content ID & Global Entries)
        empath_mod.start_topic = "" # Initialize this now just in case we don't set it later
        empath_mod.is_module_entry = module_data.get(cls._MODULE_AVAIL_MODULE_KEY, None)
        if empath_mod.is_module_entry:
            unique_content_ids = []
            for entry_point in module_data.get(cls._MODULE_ENTRY_POINT_KEY, []):
                new_entry = cls.EntryPoint(empath_mod, entry_point, "module")
                empath_mod.all_module_entries.append(new_entry)
                # store default entry as a module attirbute for later testing/rendering purposes
                if new_entry.is_default_entry:
                    empath_mod.default_entry = new_entry
                    if new_entry.is_content_id_entry:
                        raise Exception(f"A Default Entry cannot also be a Content ID Entry. Found Default entry '{new_entry.name}' in "
                                        f"module '{empath_mod.module_name}' that is also a Content ID entry. {log.context(new_entry)}")
                # ensure every content ID entry has a unique content ID
                elif new_entry.is_content_id_entry:
                    if new_entry.content_id in unique_content_ids:
                        raise Exception(f"Every Content ID entry in module '{empath_mod.module_name}' must have a uniquely assigned content ID. "
                                        f"Found entry '{new_entry.name}' with duplicate ID '{new_entry.content_id}'. {log.context(new_entry)}")
                    else:
                        unique_content_ids.append(new_entry.content_id)
                # if this is a global entry, add it to our global entries list for later testing/rendering purposes
                if new_entry.is_global_entry:
                    empath_mod.global_entries.append(new_entry)
            if empath_mod.default_entry is None:
                raise Exception(f"Module '{empath_mod.module_name}' has module entries but is missing a default module entry. {log.context(empath_mod)}")
            # Set the global variable to true if we have global entries for later testing/rendering purposes
            if empath_mod.global_entries:
                empath_mod.is_global = True

        # Support GlobalEntry v1.0 if Module Entries are not active
        else:
            # Retrieve a default start board first
            if not shallow:
                if cls._MODULE_START_BOARD_KEY in module_data_keys and module_data[cls._MODULE_START_BOARD_KEY]:
                    empath_mod.start_board_name = module_data[cls._MODULE_START_BOARD_KEY]
                    empath_mod.start_board = empath_mod.get_board_by_name(empath_mod.start_board_name)
                    # Check start board is not excluded
                    if empath_mod.start_board is None:
                        if empath_mod.is_board_name_excluded(empath_mod.start_board_name):
                            excluded_board = empath_mod.get_board_by_name(empath_mod.start_board_name,
                                                                          include_excluded_boards=True)
                            raise Exception(f"Start board '{empath_mod.start_board_name}' cannot be marked as 'excluded'. Either fix "
                                            f"this or enable module entries. {log.context(excluded_board)}: file://{empath_mod.filename}")

                        raise Exception(f"Start board '{empath_mod.start_board_name}' cannot be found in document: file://{empath_mod.filename}; "
                                        f"either fix this or enable module entries. {log.context(empath_mod, cls._MODULE_START_BOARD_KEY)}")

                    # Check start board is not a function board
                    elif empath_mod.start_board.is_function_board():
                        raise Exception(f"Start board cannot be a function board, which '{empath_mod.start_board_name}' is. Either fix "
                                        f"this or enable module entries. {log.context(empath_mod.start_board)}: file://{empath_mod.filename}")

                    empath_mod.start_topic = empath_mod.start_board.get_intro_topic()
            if not empath_mod.start_topic:
                raise Exception(f"Module '{empath_mod.module_name}' has no module entries and thus requires a start board. {log.context(empath_mod)}")
            # Now grab any old global entries that still exist
            if module_data.get(cls._MODULE_AVAIL_GLOBAL_KEY, False):
                global_entries = [cls.EntryPoint(empath_mod, entry_point, "global") for entry_point in module_data.get(cls._MODULE_GLOBAL_ENTRY_POINT_KEY, [])]
                if global_entries:
                    empath_mod.all_module_entries.extend(global_entries)
                    empath_mod.global_entries.extend(global_entries)
                    empath_mod.is_global = True

        # Returnable
        if cls._MODULE_RETURNABLE in module_data_keys:
            empath_mod.is_returnable = module_data[cls._MODULE_RETURNABLE]
        if empath_mod.is_returnable:
            if cls._MODULE_RETURNABLE_CSV_KEY in module_data_keys and module_data[cls._MODULE_RETURNABLE_CSV_KEY]:
                empath_mod.return_csv = empath_mod.get_check_csv(module_data[cls._MODULE_RETURNABLE_CSV_KEY], cls._MODULE_RETURNABLE_CSV_KEY,
                                                                 f"{empath_mod.module_name} returnable lines")
            else:
                raise Exception(f"Returnable module '{empath_mod.module_name}' must have CSV lines assigned {log.context(empath_mod, cls._MODULE_RETURNABLE_CSV_KEY)}")

        # Locked
        if cls._MODULE_LOCKED_KEY in module_data_keys:
            empath_mod.is_locked = module_data[cls._MODULE_LOCKED_KEY]
        if empath_mod.is_locked:
            if cls._MODULE_LOCKED_CSV_KEY in module_data_keys and module_data[cls._MODULE_LOCKED_CSV_KEY]:
                empath_mod.locked_csv = empath_mod.get_check_csv(module_data[cls._MODULE_LOCKED_CSV_KEY], cls._MODULE_LOCKED_CSV_KEY,
                                                                 f"{empath_mod.module_name} locked lines", required=False)
            else:
                logging.warning(f"Module '{empath_mod.module_name}' is marked as 'locked' but no CSV lines are assigned. "
                                f"A default locked line will be auto-generated. {log.context(empath_mod, cls._MODULE_LOCKED_CSV_KEY)}")

        # bedtime accessible
        if cls._MODULE_AVAIL_BEDTIME_KEY in module_data_keys:
            empath_mod.is_bedtime = module_data[cls._MODULE_AVAIL_BEDTIME_KEY]
        
        # if bedtime is enabled, ensure every index table in the module has a "bedtime" column with "true" and "false" values only
        if empath_mod.is_bedtime:
            for index_table in empath_mod.index_tables:
                with open(abs_path, "r") as f:
                    f.readline()
                    csv_rows = csv.DictReader(f)

                    if cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME not in csv_rows.fieldnames:
                        raise Exception(f"The index table for module '{empath_mod.module_id}' must have a column named exactly '{cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME}' (since it's accessible during bedtime). "
                                        f"file://{abs_path} {log.context(empath_mod)}")

                    else:
                        _num_available_cid = 0
                        for row in csv_rows:
                            if row[cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME] not in cls._MODULE_IS_BEDTIME_VALUES:
                                raise Exception(f"The index table for module '{empath_mod.module_id}' uses the '{cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME}' column but has this invalid value '{row[cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME]}'. All values in '{cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME}' must be written exactly as one of the following: {cls._MODULE_IS_BEDTIME_VALUES}. "
                                                f"file://{abs_path} {log.context(empath_mod)}")

                            elif row[cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME] in cls._MODULE_IS_BEDTIME_TRUE_VALUES:
                                _num_available_cid += 1

                        if _num_available_cid == 0:
                            raise Exception(f"The index table for module '{empath_mod.module_id}' uses the '{cls._MODULE_AVAIL_BEDTIME_COLUMN_NAME}' column but does not have any bedtime available content. Please ensure at least one content ID is available (during bedtime) with the following value(s): {cls._MODULE_IS_BEDTIME_TRUE_VALUES}. "
                                            f"file://{abs_path} {log.context(empath_mod)}")

        if cls._MODULE_ICON_KEY in module_data_keys:
            empath_mod.icon_name = module_data[cls._MODULE_ICON_KEY]
        if cls._MODULE_SFX_IN_KEY in module_data_keys:
            empath_mod.sfx_in_name = module_data[cls._MODULE_SFX_IN_KEY]
        if cls._MODULE_SFX_OUT_KEY in module_data_keys:
            empath_mod.sfx_out_name = module_data[cls._MODULE_SFX_OUT_KEY]
        
        # Riely 5/31/22: create ContentTag objects from the ContentTag string included with the module from Empath
        if cls._CONTENT_TAG_KEY in module_data:
            empath_mod.module_content_tags = ContentTag.get_content_tags_from_string(
                content_tag_str=module_data[cls._CONTENT_TAG_KEY], 
                source_uuid=module_data[cls._UUID_KEY]
            )
        
        if cls._MODULE_STATUS_KEY in module_data:
            cls.document_status = module_data[cls._MODULE_STATUS_KEY]

        return empath_mod

    def get_check_csv(self, csv_relative_path: str, property_key: str, context: str, required: bool = True) -> str:
        """
        Resolves the full path to the CSV and check for existence. Also checks for required 'ignore' metadata field
        """
        full_path = os.path.join(globals.CHATSCRIPT_ROOT, "chatscript", csv_relative_path)
        if not os.path.isfile(full_path):
            if required:
                raise Exception(f"Relative CSV path for '{context}' not found: '{csv_relative_path}'"
                                f" {log.context(self, property_key)}")
            else:
                return ""

        # Check for required 'ignore' metadata
        with open(full_path, "r") as f:
            first_row = f.readline().strip().lower()
            if "ignore" not in first_row:
                raise Exception(f"CSV table used in module must have 'ignore' in its first-row metadata: "
                                f"file://{full_path} {log.context(self, property_key)}")

        return full_path

    def is_module(self):
        return True

    def get_tags(self) -> List[str]:
        result = []
        if self.is_global:
            if not self.is_locked:
                result.append("unlocked")
            if self.is_roulette:
                result.append("suggest")

        if self.is_bedtime:
            result.append("bedtime")
        if self.is_returnable and not globals.DISABLE_MODULE_RETURNABLE:
            result.append("returnable")
        return result

    def render_and_write_module_entry_patterns(self) -> str:
        logging.debug(f"generating {self.module_name} entry patterns")
        if not os.path.isdir(EMPATH_PATTERNS_DIR):
            os.makedirs(EMPATH_PATTERNS_DIR)
        out_entry_patterns_file = os.path.join(EMPATH_PATTERNS_DIR, self.module_id + "_GlobalEntryPatterns.top")
        with open(out_entry_patterns_file, "w") as f:
            data_string: str = ""
            # For every global entry point in the module, generate its respective patternmacro and samples
            for global_entry in self.global_entries:
                for pos_example in global_entry.pattern_examples_pos:
                    data_string += f"# {pos_example}\n"
                # this is currently not hooked up because a "#!!F" coomment will cause a CS compile error
                # TODO: come up with a clean solution to this crash so that we can generate negative sample patterns
                # for neg_example in global_entry.pattern_examples_neg:
                    # data_string += f"#!!F {neg_example}\n"
                data_string += f"patternmacro: ^{global_entry.pattern_macro_name}()\n"
                data_string += "[\n"
                data_string += f"{global_entry.pattern}\n"
                data_string += "]\n\n"

            f.write(data_string)
            del data_string
        self.out_file_paths.append(out_entry_patterns_file)
        # Remove all module entry pattern cache objects since they MAY now be outdated
        c_cache = compiler_cache.get_instance(from_cache=True)
        num_objects_removed = c_cache.remove_objects_for_file(abs_path=out_entry_patterns_file)

        return out_entry_patterns_file

    def render(self) -> Tuple[str, str]:
        # Render the module .top files as their own files
        jinja_environment = Environment(loader=FileSystemLoader(
            globals.JINJA_TEMPLATE_DIR), extensions=['jinja2.ext.do'])
        for k,v in DEFINED_FILTERS.items():
            jinja_environment.globals[k] = v
        logging.debug(f"Rendering module '{self.name}' with template {self.module_template_name}")
        template = jinja_environment.get_template(self.module_template_name)
        prop_dict = self.__dict__
        prop_dict[self.TEMPORARY_LEGACY_EXIT_JINJA_KEY] = self.TEMPORARY_LEGACY_EXIT
        output_controller = template.render(prop_dict)
        output_controller = utils.clean_topic_output(output_controller)

        # render chat conversation boards
        output_conversation = super().render()
        output_conversation = utils.clean_topic_output(output_conversation)

        return output_controller, output_conversation

    def render_and_write(self,
                         out_file_controller: str,
                         out_file_conversation: str = None,
                         **kwargs
                         ) -> Tuple[str, str]:
        str_controller, str_conversation = self.render()

        # write module controller
        if str_controller != "":
            controller_dir = os.path.dirname(out_file_controller)
            if not os.path.isdir(controller_dir):
                os.makedirs(controller_dir)

            with open(out_file_controller, "w") as f:
                f.write(str_controller)
            if out_file_controller not in self.out_file_paths:
                self.out_file_paths.append(out_file_controller)

        # write module conversation
        if str_conversation != "":
            conversation_dir = os.path.dirname(out_file_conversation)
            if not os.path.dirname(conversation_dir):
                os.makedirs(conversation_dir)

            with open(out_file_conversation, "w") as f:
                f.write(str_conversation)
            if out_file_conversation not in self.out_file_paths:
                self.out_file_paths.append(out_file_conversation)
        
        return out_file_controller, out_file_conversation

    @staticmethod
    def get_subtype_classes() -> List[Any]:
        """
        Returns a list of class objects for flexible node subtypes
        """
        class_objects: List[ModuleTypeData] = []
        members = inspect.getmembers(type_data)
        for name, obj in members:
            if inspect.isclass(obj):
                class_objects.append(obj)

        return class_objects
