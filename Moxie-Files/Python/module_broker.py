# README: Co-developed with various members. I was not the original author
# but continually reduced tech debt for better scalability

import os
from copy import copy, deepcopy
from typing import Any, List, Dict, Tuple
import json
import logging

from .module import Module
from . import module_entry_line
from .datatables.content_index import ContentIndexTable, ContentIndex
from .missions_data import MissionsData
from ..document import Document
from ..objects.elements.flexible.flexible import Flexible
from ..objects.tags.sel_tag import SelTag
from ..objects.tags.content_tag import ContentTag
from ... import chat2cs
from .... import GENERATED_EMPATH_FILES, MISSIONS_INDEX

class ModuleInfo:
    """
    API for accessing Module Information data for a given .chatModule.

    Module Information data is Protected, this serves as an API to safely access this protected data.
    """

    # Riely 5/11/22: We need to strip out specific pieces of data from EntryPoint and ContendIndex objects,
    # since the Module obj is refrenced by the Entry Point, we can't write it to JSON.
    # this also reduces the overall data duplication caused by the ModuleBroker,
    # since we only strip out what we need.
    class EntryPointInfo:
        """
        Trimed-Down data container for Module.EntryPoint objects
        """
        _name: str
        _topic: str
        _entry_line: str
        _pattern: str
        _contentID: str

        def __init__(self, entry_point: Module.EntryPoint) -> None:
            self._name = entry_point.name
            self._topic = entry_point.entry_topic
            self._pattern = entry_point.pattern
            self._contentID = entry_point.content_id
            self._entry_line = ''

        def update_entry_line(self, entry_line) -> None:
            self._entry_line = entry_line
        
        @property
        def name(self) -> str:
            return self._name
        
        @property
        def topic(self) -> str:
            return self._topic

        @property
        def entry_line(self) -> str:
            return self._entry_line
        
        @property
        def pattern(self) -> str:
            return self._pattern

        @property
        def contentID(self) -> str:
            return self._contentID
            
    class ContentIndexInfo:
        """
        Trimed-Down data container for ContentIndex objects
        """
        id: str
        set_id: str
        goal_levels: List
        content_tags: List
        detail: str

        def __init__(self, content_index: ContentIndex = None, content_id: str = "", set_id: str = "") -> None:
            """
            If an index is provided, fill in the attributes according to the info found inside it.
            Else assign only the attributes that were provided as arguments.
            """
            if content_index is not None:
                self.id = content_index.content_id
                self.set_id = content_index.csv_dict.get("set_id", "")
                self.goal_levels = [{"goal":goal_level.split(".")[0], "level":goal_level.split(".")[1]} for goal_level in content_index.csv_dict.get("sel_tags", "").split(",") if len(goal_level.split(".")) > 1]
                self.content_tags = [content_tag.strip() for content_tag in content_index.csv_dict.get("content_tags", "").split(",") if content_tag != ""]
                self.detail = content_index.csv_dict.get("detail", "")
            else:
                self.id = content_id
                self.set_id = set_id
                self.goal_levels = []
                self.content_tags = []
                self.detail = ""

        @property
        def content_id(self) -> str:
            return self.id

        @content_id.setter
        def content_id(self, new_id: str):
            if new_id:
                self.id = new_id
        
        @property
        def content_set_id(self) -> str:
            return self.set_id

        @content_set_id.setter
        def content_set_id(self, new_set_id: str):
            if new_set_id:
                self.set_id = new_set_id

        @property
        def content_id_detail(self) -> str:
            return self.detail

        @content_id_detail.setter
        def content_id_detail(self, new_desc: str):
            if new_desc:
                self.detail = new_desc
        
        @property
        def content_id_properties(self) -> str:
            return self.properties

        @content_id_properties.setter
        def content_id_properties(self, new_props: list):
            if new_props:
                self.properties = new_props

    class FallbackContextInfo:
        """
        Trimed-Down data container for Fallback Context objects
        """

        _topic_name: str
        _fallback_type: str
        _fallback_text: str

        def __init__(self, topic_name: str, fallback_type: str, fallback_text: str) -> None:
            self._topic_name = topic_name
            self._fallback_type = fallback_type
            self._fallback_text = fallback_text

        @property
        def topic_name(self) -> str:
            return self._topic_name

        @property
        def fallback_type(self) -> str:
            return self._fallback_type

        @property
        def fallback_text(self) -> str:
            return self._fallback_text

    _SOURCE_DEFAULT = "LOCAL"
    _RULES_DEFAULT = "UNSPECIFIED"
    _CATEGORY_DEFAULT = "UNASSIGNED"
    _DETAIL_DEFAULT = ""
    _DURATION_DEFAULT = ""
    _SCHEDULABLE_DEFAULT = False
    _REQUESTABLE_DEFAULT = False
    _RECOMMENDABLE_DEFAULT = False
    _RECOMMENDABLE_CID_DEFAULT = False

    _uuid: str
    info: Dict
    _module_template_name: str

    _default_entries: List[EntryPointInfo]
    _content_id_entries: List[EntryPointInfo]
    _global_entries: List[EntryPointInfo]

    content_infos: List[ContentIndexInfo]

    _sel_tags: List[SelTag]
    _content_tags: List[ContentTag]

    _module_context: str
    _fallback_contexts: List[FallbackContextInfo]

    rules: str
    category: str
    duration: str
    source: str

    schedulable: bool
    requestable: bool
    recommendable: bool
    recommendable_cid: bool


    def __init__(self, module: Module, compiled_topics: List[Any]) -> None:
        """
        Given a Module obj, extract sharable data fields into ModuleInfo obj
        """
        self._uuid = module.uuid
        self._module_template_name = module.module_template_name
        self.reportable = module.does_report_completion
        
        self._default_entries = self._entry_points_to_dict([entry for entry in module.all_module_entries if entry.is_default_entry])
        self._content_id_entries = self._entry_points_to_dict([entry for entry in module.all_module_entries if entry.is_content_id_entry])
        self._global_entries = self._entry_points_to_dict([entry for entry in module.all_module_entries if entry.is_global_entry])

        self.content_infos = self._index_tables_to_dict(module.index_tables)

        # Use sets to remove duplicate content/sel tags
        self._sel_tags = []
        _sel_tags_set = set(self._extract_sel_tags(module=module, compiled_topics=compiled_topics))
        if _sel_tags_set:
            self._sel_tags.extend(_sel_tags_set)
        del _sel_tags_set
        
        self._content_tags = []
        _content_tags_set = set(self._extract_content_tags(module=module, compiled_topics=compiled_topics))
        if _content_tags_set:
            self._content_tags.extend(_content_tags_set)
        del _content_tags_set

        self.info = {"id": module.module_id, "name": module.module_name, "goal_levels": self._sel_tags, "content_tags": [t.tag_uuid for t in self._content_tags], "detail": getattr(module, "detail", self._DETAIL_DEFAULT), "properties": ["opt_in"] if not module.is_status_finalized() else []}
        self._module_context = getattr(module, "module_context", "")
        self._fallback_contexts = self._extract_fallback_contexts(module=module, compiled_topics=compiled_topics)

        # newer attributes
        self.source = self._SOURCE_DEFAULT
        self.rules = getattr(module, "content_rules", self._RULES_DEFAULT)
        self.category = getattr(module, "category", self._CATEGORY_DEFAULT)
        self.duration = getattr(module, "duration", self._DURATION_DEFAULT)
        self.schedulable = getattr(module, 'is_schedule', self._SCHEDULABLE_DEFAULT)
        self.requestable = getattr(module, 'is_request', self._REQUESTABLE_DEFAULT)
        self.recommendable = getattr(module, 'is_recommend', self._RECOMMENDABLE_DEFAULT)
        self.recommendable_cid = getattr(module, 'is_recommend_cid', self._RECOMMENDABLE_CID_DEFAULT)

    @staticmethod
    def _entry_points_to_dict(entry_points: List[Module.EntryPoint]) -> List[Dict[str, Any]]:
        # Riely 5/10/22: need to do this so we don't write the Board obj to json
        entry_dicts = []
        for ep in entry_points:
            entry_dicts.append(
                ModuleInfo.EntryPointInfo(ep)
            )

        return entry_dicts
    
    @staticmethod
    def _index_tables_to_dict(content_tables: List[ContentIndexTable]) -> List[Dict[str, Any]]:
        # Riely 5/10/22: need to do this so we don't write the Document obj to json
        content_indicies = []
        for table in content_tables:
            for cid in table.content_indices:
                content_indicies.append(
                    ModuleInfo.ContentIndexInfo(content_index=cid)
                )

        return content_indicies
    
    @staticmethod
    def _extract_sel_tags(module: Module, compiled_topics: List[Any]) -> List[SelTag]:
        all_sel_tags = []
        for compiled_topic in compiled_topics:
            # check each topic in the cache to see if it belongs to the given module
            if compiled_topic.filepath == module.filepath:
                for topic_name in compiled_topic.topics:
                    topic_obj = compiled_topic.topics[topic_name]
                    # if the current topic has sel tags, retrieve them
                    if getattr(topic_obj, "sel_tags", []):
                        all_sel_tags.extend(topic_obj.sel_tags)
                    # if the current topic has additional flexible sel tags, retrieve them
                    if getattr(topic_obj, "flex_sel_tags", []):
                        all_sel_tags.extend(topic_obj.flex_sel_tags)

        return all_sel_tags

    @staticmethod
    def _extract_content_tags(module: Module, compiled_topics: List[Any]) -> List[ContentTag]:
        # get module-level content tags
        all_content_tags: List[ContentTag] = []
        if hasattr(module, "module_content_tags"):
            all_content_tags.extend(module.module_content_tags)

        for compiled_topic in compiled_topics:
            # check each topic in the cache to see if it belongs to the given module
            if compiled_topic.filepath == module.filepath:
                for topic_name in compiled_topic.topics:
                    topic_obj = compiled_topic.topics[topic_name]
                    # if the current topic has content tags, retrieve them
                    if getattr(topic_obj, "content_tags", []):
                        all_content_tags.extend(topic_obj.content_tags)
        
        return all_content_tags

    @staticmethod
    def _extract_fallback_contexts(module: Module, compiled_topics: List[Any]) -> List[FallbackContextInfo]:
        # Used to filter out unknown context types
        # @Wilson 3/22/2023 removed CONVERSATION for now
        # removed DEFAULT since any non-listed topic gets treated as DEFAULT already - Juan 7.10.23
        _FALLBACK_CONTEXT_TYPES = ["SILENT", "LOCAL_ONLY", "FALLBACKS_NO_REMOTE"]

        fallback_contexts = []
        for compiled_topic in compiled_topics:
            # check each topic in the cache to see if it belongs to the given module
            if compiled_topic.filepath == module.filepath:
                for topic_name, topic_obj in compiled_topic.topics.items():
                    # if the current topic has a fallback context, retrieve it
                    if getattr(topic_obj, "templated_node_properties", {}):
                        option: str = topic_obj.templated_node_properties.get("fallbackContextType", "")
                        text: str = topic_obj.templated_node_properties.get("fallbackContextText", "")
                        # make sure the fallback type is actually valid (else there's no point in writing it to the file)
                        # also make sure to include any defaults WITH a local fallback context
                        if option in _FALLBACK_CONTEXT_TYPES or (option == "DEFAULT" and text):
                            fallback_contexts.append(
                                ModuleInfo.FallbackContextInfo(topic_name=topic_name,
                                                               fallback_type=option,
                                                               fallback_text=text,
                                                              )
                                                    )
        return fallback_contexts

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def module_id(self) -> str:
        return self.info["id"]
    
    @property
    def module_name(self) -> str:
        return self.info["name"]

    @module_name.setter
    def module_name(self, new_name: str):
        """
        setter function for module name; ONLY WORKS for native modules
        since standard module info objects already have a set module name
        """
        if type(self) is not ModuleInfo and new_name:
            self.info["name"] = new_name

    @property
    def detail(self) -> str:
        return self.info["detail"]

    @detail.setter
    def detail(self, new_detail: str):
        if new_detail:
            self.info["detail"] = new_detail

    @property
    def module_template_name(self) -> str:
        return self._module_template_name
    
    @property
    def index_table(self) -> List[ContentIndexInfo]:
        return self._index_table
    
    @property
    def default_entries(self) -> List[EntryPointInfo]:
        return self._default_entries

    @property
    def content_id_entries(self) -> List[EntryPointInfo]:
        return self._content_id_entries

    @property
    def global_entries(self) -> List[EntryPointInfo]:
        return self._global_entries
    
    @property
    def sel_tags(self) -> List[SelTag]:
        return self._sel_tags
    
    @property
    def content_tags(self) -> List[ContentTag]:
        return self._content_tags

    @property
    def module_context(self) -> str:
        return self._module_context

    @property
    def fallback_contexts(self) -> List[FallbackContextInfo]:
        return self._fallback_contexts

    def get_content_info_by_id(self, content_id: str):
        """
        Given a content ID, return the Content Info associated with it;
        Content IDs are currently not case sensative
        """
        for info in self.content_infos:
            if content_id.lower() == info.content_id.lower():
                return info

        # return None if content not found
        return None

    def add_content_info_by_id(self, content_id: str) -> None:
        if content_id:
            self.content_infos.append(ModuleInfo.ContentIndexInfo(content_id=content_id))

    def add_sel_tags(self, module: Module, compiled_topics: List[Any]) -> None:
        # Use sets to remove duplicate sel tags
        _sel_tags_set = set(self._extract_sel_tags(module=module, compiled_topics=compiled_topics))
        if _sel_tags_set:
            for _sel_tag in _sel_tags_set:
                if _sel_tag not in self.sel_tags:
                    self.sel_tags.append(_sel_tag)
        del _sel_tags_set

    def add_content_tags(self, module: Module, compiled_topics: List[Any]) -> None:
        # Use sets to remove duplicate content tags
        _content_tags_set = set(self._extract_content_tags(module=module, compiled_topics=compiled_topics))
        if _content_tags_set:
            for _content_tag in _content_tags_set:
                if _content_tag not in self.content_tags:
                    self.content_tags.append(_content_tag)
        del _content_tags_set

    def add_fallback_contexts(self, module: Module, compiled_topics: List[Any]) -> None:
        new_fallback_contexts = self._extract_fallback_contexts(module=module, compiled_topics=compiled_topics)
        if new_fallback_contexts:
            self.fallback_contexts.extend(new_fallback_contexts)

    def add_module_info(self, module: Module, compiled_topics: List[Any]):
        self.add_sel_tags(module, compiled_topics)
        self.add_content_tags(module, compiled_topics)
        self.add_fallback_contexts(module, compiled_topics)


# TODO: remove this class and all the places it is called once all the legacy modules have been upgraded - Juan 7.15.22
class NativeModuleInfo(ModuleInfo):
    """
    Functions similarly to ModuleInfo except that this class is for native chatscript modules without an associated .chatModule

    Also contains/accesses less stored data compared to ModuleInfo due to the data limited nature of native modules
    """

    def __init__(self, native_module_id: str) -> None:
        """
        Given a Module id, fill in the minimum requirement for a functional NativeModuleInfo obj 
        """
        self._uuid = native_module_id + "-THIS-ISSS-AAAA-NATIVEEEUUID"
        self._module_template_name = ""
        
        self._default_entries = []
        self._content_id_entries = []
        self._global_entries = []

        self.content_infos = []

        self._sel_tags = [] 
        self._content_tags = []

        self._module_context = ""
        self._fallback_contexts = []
        self.info = {"id": native_module_id, "name": native_module_id, "goal_levels": [], "content_tags": [], "detail": self._DETAIL_DEFAULT, "properties": []}

        # newer attributes
        self.source = self._SOURCE_DEFAULT
        self.rules = self._RULES_DEFAULT
        self.category = self._CATEGORY_DEFAULT
        self.duration = self._DURATION_DEFAULT
        self.schedulable = self._SCHEDULABLE_DEFAULT
        self.requestable = self._REQUESTABLE_DEFAULT
        self.recommendable = self._RECOMMENDABLE_DEFAULT
        self.recommendable_cid = self._RECOMMENDABLE_CID_DEFAULT

        # Unique mission set data that only very specific modules (i.e. Daily Missions) need
        self.MissionData = None
        if native_module_id.upper() == "DM":
            self.MissionData = MissionsData.from_file(MISSIONS_INDEX)

    def add_module_info(self, chat_conversation: Document, compiled_topics: List[Any]):
        """
        Override this function for native module info objects specifically in case it needs to create
        a new ContentIndexInfo object (if the conversation file ends up having a content ID) in a
        unique way. Otherwise, it should behave identically.
        """
        try:
            content_id = chat_conversation.boards[0].info['content_ID']
        except:
            logging.info(f"Module Broker could not find content_ID for '{chat_conversation.name}' in board: "
                         f"'{chat_conversation.boards[0].name}'. Adding all found data to module info instead.")
            super().add_module_info(chat_conversation, compiled_topics)
            # Make sure any newly found sel & content tags are stored inside the info attribute
            self.info["goal_levels"] = self.sel_tags
            self.info["content_tags"] = [t.tag_uuid for t in self.content_tags]
            return

        logging.info(f"Module Broker found content_ID for '{chat_conversation.name}' in board: "
                     f"'{chat_conversation.boards[0].name}'. Adding all found data to its content info.")

        # Determine whether or not the current content ID is part of a (mission) set
        mission_set = ""
        if self.MissionData is not None:
            for mission_data in self.MissionData.missions:
                for activity in mission_data.activities:
                    if activity.contentId == content_id:
                        mission_set = "_".join(mission_data.name.split())

        content_info_exists = False
        for content_info in self.content_infos:
            if content_info.id == content_id:
                content_info_created = content_info
                content_info_exists = True
                break
        if not content_info_exists:
            content_info_created = self.ContentIndexInfo(content_id=content_id, set_id=mission_set)
        _sel_tags_set = set(self._extract_sel_tags(module=chat_conversation, compiled_topics=compiled_topics))
        if _sel_tags_set:
            for _sel_tag in _sel_tags_set:
                if _sel_tag not in content_info_created.goal_levels:
                    content_info_created.goal_levels.append(_sel_tag)
        del _sel_tags_set

        _content_tags_set = set(self._extract_content_tags(module=chat_conversation, compiled_topics=compiled_topics))
        if _content_tags_set:
            for _content_tag in _content_tags_set:
                if _content_tag not in content_info_created.content_tags:
                    content_info_created.content_tags.append(_content_tag.tag_uuid)
        del _content_tags_set

        if not content_info_exists and content_info_created.content_id:
            self.content_infos.append(content_info_created)

        # fallback contexts found inside the current conversation file should be added
        # to module info object since content info objects don't currently hold them
        self.add_fallback_contexts(chat_conversation, compiled_topics)


class ModuleBroker:
    """
    Container Class to link ModuleInfo object data to whatever needs access to it.
    """
    module_info_data: Dict[str, ModuleInfo] # maps UUID to module document
    # Riely 5/2/22: Needs to track object version to update out-of-date ModuleBrokers w/out rebuilding everything
    # stores the version of this 
    _object_version: int
    # keeps track of all the currently existing native module IDs
    _legacy_module_ids: List[Any]
    # the current version of the Module Broker obj
    # Riely 5/11/22: this allows us to make changes to the ModuleBroker, without breaking an outdated compiler cache!
    # NOTE: Be sure to increment this number each time you PR a change to the ModuleBroker or ModulInfo objects!!!!
    LATEST_VERSION: int = 15
    # JSON Write path
    JSON_DICT: str = os.path.join(GENERATED_EMPATH_FILES, "ModuleInfo/")
    JSON_FILE: str = os.path.join(JSON_DICT, "module_info.json")
    JSON_CONTEXT_FILE: str = os.path.join(JSON_DICT, "fallback_contexts.json")
    DM_SUB_MODULE_ID = ["OMR"]

    @property
    def version(self) -> int:
        return self._object_version

    @property
    def object_up_to_date(self) -> bool:
        return self.LATEST_VERSION == self.version

    @property
    def module_info(self) -> List[ModuleInfo]:
        """
        A list representation of all the ModuleInfo objects
        """
        return list(self.module_info_data.values())

    @property
    def module_info_no_underscore_keys(self) -> List[ModuleInfo]:
        """
        A list representation of all the ModuleInfo objects containing only their non-underscore keys
        """
        mod_infos = []
        for mod_info in self.module_info_data.values():
            mod_info_copy = copy(mod_info)
            for key in mod_info.__dict__:
                if key.startswith('_'):
                    delattr(mod_info_copy, key)
            mod_infos.append(mod_info_copy)
        return mod_infos

    def __init__(self, module_list: List[Module], compiled_topics: List[Any]) -> None:
        self.module_info_data = {}
        self._object_version = self.LATEST_VERSION
        self._legacy_module_ids = []
        # for every module, create a ModuleInfo API to access module information
        for module in module_list:

            # if passed in an object that is NOT derrived from Module, throw an exception
            if not issubclass(module.__class__, Module):
                raise Exception(f"Module Broker passed invalid class object type {module.__class__}, expected only classes derrived from {Module}")
            
            # Riely 4/20/22: the ModuleBroker represents all the Compiled Modules active in the project.
            # If a module is excluded, then it is not part of the project.
            # if the module is excluded, skip it
            if module.excluded:
                continue
            mod_uuid: str = module.uuid
            new_mod_info = ModuleInfo(module, compiled_topics)
            self.module_info_data[mod_uuid] = new_mod_info

            # add additional info (i.e. tags) from any related chat conversations
            self._update_by_content_indices(module, new_mod_info, compiled_topics)

        # now add all the currently existing native modules
        self._update_native_modules_id_list()
        self._update_native_modules()
    
    def __iter__(self):
        return iter(self.module_info_data.values())

    def update(self, changed_modules: List[Module], compiled_topics: List[Any]) -> None:
        """
        Update ModuleBroker with new ModuleInfo objects from updated modules and their related chat conversations
        """
        for module in changed_modules:
            # if module is excluded, remove it from the broker, and don't update it
            if module.excluded:
                self._remove_module(module.uuid)
                continue

            new_mod_info = ModuleInfo(module, compiled_topics)
            mod_uuid = module.uuid
            self.module_info_data[mod_uuid] = new_mod_info

            # add additional info (i.e. tags) from any related chat conversations
            self._update_by_content_indices(module, new_mod_info, compiled_topics)

        # remove any lingering & non-existing native modules and then add all the currently existing ones
        self._remove_native_modules()
        self._update_native_modules_id_list()
        self._update_native_modules()

    # TODO: remove this function and all the places it is called once all the legacy modules have been upgraded - Juan 7.15.22
    def update_by_native_related_conversations(self, changed_conversations: List[Document], compiled_topics: List[Any]) -> None:
        """
        Update ModuleBroker objects with related chat conversations from native modules (i.e. no .chatModule files) only
        """
        for conversation in changed_conversations:
            # Grab just the first portion of the conversation ID since most have this format: ModuleID_SubGenre_OptionalIndex
            convo_id = conversation.get_prefix_from_conversation_id().upper()

            if convo_id in self._legacy_module_ids:
                mod_info = self.get_info_by_module_id(convo_id)
                self._update_by_conversation(conversation, mod_info, compiled_topics)

        self._post_update_dm_conversation()
    
    def update_by_external_module_info(self, external_module_info=None) -> None:
        """
        Update ModuleBroker objects with additional module information from external sources
        """
        if external_module_info is not None:
            for mod_info in self.module_info:
                _mod_id = mod_info.module_id
                # if we have external data of the current module info, append it
                if _mod_id in external_module_info.content_info_map:
                    # append data from any of these found attributes: module name, module description, content rules, category type, duration
                    mod_info.module_name = external_module_info.content_info_map[_mod_id].name
                    mod_info.detail = external_module_info.content_info_map[_mod_id].description
                    mod_info.rules = external_module_info.content_info_map[_mod_id].content_rules
                    mod_info.category = external_module_info.content_info_map[_mod_id].category
                    mod_info.duration = external_module_info.content_info_map[_mod_id].duration
                    if(len(external_module_info.content_info_map[_mod_id].properties) > 0):
                        for p in external_module_info.content_info_map[_mod_id].properties:
                            if p not in mod_info.info["properties"]:
                                mod_info.info["properties"].append(p)

                    # append data from any of these found bool attributes: is it schedulable, is it requestable, is it recommendable (module & ids)
                    mod_info.schedulable = external_module_info.content_info_map[_mod_id].schedule
                    mod_info.requestable = external_module_info.content_info_map[_mod_id].request
                    mod_info.recommendable = external_module_info.content_info_map[_mod_id].recommend_module
                    mod_info.recommendable_cid = external_module_info.content_info_map[_mod_id].recommend_content_id

                    # append any found content ids that don't already exist in the current module info
                    for content_id in external_module_info.content_info_map[_mod_id].content_ids:
                        if mod_info.get_content_info_by_id(content_id) is None:
                            mod_info.add_content_info_by_id(content_id)

                    # append any found content id descriptions if their respective content id exists in the current module info
                    for content_info in mod_info.content_infos:
                        _content_id = content_info.content_id
                        if _content_id in external_module_info.content_info_map[_mod_id].content_ids:
                            content_info.content_id_detail = external_module_info.content_info_map[_mod_id].get_content_id_description(_content_id)
                            content_info.content_id_properties = external_module_info.content_info_map[_mod_id].get_content_id_properties(_content_id)
    def _update_by_content_indices(self, module: Module, module_info: ModuleInfo, compiled_topics: List[Any]) -> None:
        """
        Update ModuleBroker object with its related chat conversations
        """
        for cid in module.chat_content_indices:
            self._update_by_conversation(cid.chat_object, module_info, compiled_topics)

    def _update_by_conversation(self, chat_conversation: Document, module_info: ModuleInfo, compiled_topics: List[Any]) -> None:
        """
        Update a specified ModuleBroker object (if it exists) with a specified chat conversation
        """
        if module_info in self.module_info and not chat_conversation.excluded:
            module_info.add_module_info(chat_conversation, compiled_topics)
            self.module_info_data[module_info.uuid] = module_info

    def _update_native_modules_id_list(self) -> None:
        """
        Updates the legacy modules list by retrieving every unique module ID found in
        .chatConversations without an associated .chatModule (i.e. native modules)
        """
        self._legacy_module_ids = []
        independent_convos = chat2cs.get_independent_conversation_files()
        for convo in independent_convos:
            convo_id = convo.get_prefix_from_conversation_id().upper()
            if convo_id not in self._legacy_module_ids:
                self._legacy_module_ids.append(convo_id)

    def _post_update_dm_conversation(self) -> None:
        """
        Updates Daily Mission's ModuleInfo object with any and all ModuleInfo objects
        that are classified as being a submodule of Daily Mission
        """
        dm_mod_info = self.get_info_by_module_id("DM")
        if dm_mod_info is None:
            logging.error("Module Broker could not find Daily Mission ModuleInfo object; skipping post DM update.")
            return

        # pairs every mission set's number with its highest indexed mission's number
        highest_mission_idx: Dict[int, int] = {}
        # pairs every mission set's number with its highest indexed mission's ModuleInfo object
        highest_mission_to_obj_map: Dict[int, Any] = {}

        # Traverse through Daily Mission's content IDs and store every found mission set with its 
        # highest found mission index and that mission's ModuleInfo object in the dicts above
        for content_info in dm_mod_info.content_infos:
            cid_info = content_info.content_id.split("_")
            mission_set = int(cid_info[0])
            mission_idx = int(cid_info[1])

            if mission_set not in highest_mission_idx or mission_idx > highest_mission_idx[mission_set]:
                highest_mission_idx[mission_set] = mission_idx
                highest_mission_to_obj_map[mission_set] = content_info

        for sub_id in self.DM_SUB_MODULE_ID:
            sub_mod_info = self.get_info_by_module_id(sub_id)
            
            # For official mission reports, append a "report" & "reply" mission (if they exist) to every mission set
            if sub_id == "OMR" and sub_mod_info is not None:
                report_content_info = sub_mod_info.get_content_info_by_id("Report")
                reply_content_info = sub_mod_info.get_content_info_by_id("Reply")
                if report_content_info is not None and reply_content_info is not None:
                    for mission_set in highest_mission_idx:
                        highest_mission_obj = highest_mission_to_obj_map[mission_set]
                        new_set_id = highest_mission_obj.content_set_id

                        # The Report mission should always be appeneded to the end of its mission set with its own index number
                        report_idx = highest_mission_idx[mission_set] + 1
                        new_report_content_info = deepcopy(report_content_info)
                        new_report_content_info.content_id = str(mission_set) + "_" + str(report_idx) + "_Report"
                        new_report_content_info.content_set_id = new_set_id
                        new_report_position = dm_mod_info.content_infos.index(highest_mission_obj) + 1
                        dm_mod_info.content_infos.insert(new_report_position, new_report_content_info)

                        # The Reply mission should always be appeneded after the report mission with its own index number
                        reply_idx = highest_mission_idx[mission_set] + 2
                        new_reply_content_info = deepcopy(reply_content_info)
                        new_reply_content_info.content_id = str(mission_set) + "_" + str(reply_idx) + "_Reply"

                        # IMPORTANT NOTE: Content ID should have been 5_10_Reply by its index, but was accidentally
                        # coded as _9_ in content data and can't be changed for tracking reasons
                        if new_reply_content_info.content_id == "5_10_Reply":
                            new_reply_content_info.content_id = "5_9_Reply"
                
                        new_reply_content_info.content_set_id = new_set_id
                        new_reply_position = dm_mod_info.content_infos.index(highest_mission_obj) + 2
                        dm_mod_info.content_infos.insert(new_reply_position, new_reply_content_info)

                # Now append the submodule's module sel/content tags and fallback contexts
                _sub_mod_sel_tags = sub_mod_info.sel_tags
                _sel_tags_set = set(_sub_mod_sel_tags)
                if _sel_tags_set:
                    for _sel_tag in _sel_tags_set:
                        if _sel_tag not in dm_mod_info.sel_tags:
                            dm_mod_info.sel_tags.append(_sel_tag)
                    dm_mod_info.info["goal_levels"] = dm_mod_info.sel_tags
                del _sel_tags_set

                _sub_mod_content_tags = sub_mod_info.content_tags
                _content_tags_set = set(_sub_mod_content_tags)
                if _content_tags_set:
                    for _content_tag in _content_tags_set:
                        if _content_tag not in dm_mod_info.content_tags:
                            dm_mod_info.content_tags.append(_content_tag)
                    dm_mod_info.info["content_tags"] = [t.tag_uuid for t in dm_mod_info.content_tags]
                del _content_tags_set

                dm_mod_info.fallback_contexts.extend(sub_mod_info.fallback_contexts)

            # Lastly, delete the ModuleInfo since all its data should now be in Daily Mission's ModuleInfo
            self.module_info_data.pop(sub_mod_info.uuid, None)

    def _remove_native_modules(self) -> None:
        """
        Removes all module info Objs belonging to our native modules
        """
        for module_id in self._legacy_module_ids:
            mod_info = self.get_info_by_module_id(module_id)
            if mod_info is not None:
                self._remove_module(mod_info.uuid)

    def _remove_module(self, module_uuid) -> None:
        """
        Given a Module's UUID, remove it from the ModuleBroker if it exists
        """
        removed = self.module_info_data.pop(module_uuid, None)
        # TODO: add logging of removed data

    # TODO: remove this function and all the places it is called once all the legacy modules have been upgraded - Juan 7.15.22
    def _update_native_modules(self) -> None:
        """
        Update ModuleBroker with native chatscript modules
        """
        for mod_id in self._legacy_module_ids:
            new_native_mod_info = NativeModuleInfo(mod_id)
            self.module_info_data[new_native_mod_info.uuid] = new_native_mod_info

    def export_to_json(self) -> None:
        """
        Converts Module Broker object to a JSON object
        """
        class DictEncoder(json.JSONEncoder):
            def default(self, o):
                return o.__dict__
        # json_str: str = ""
        # for mod_info in self.module_info_data.values():
        #     json_str += 

        if not os.path.isdir(self.JSON_DICT):
            os.mkdir(self.JSON_DICT)

        with open(self.JSON_FILE, "w") as json_out:
            json_str: str = json.dumps(
                { "modules": self.module_info_no_underscore_keys },
                cls=DictEncoder,
                indent=2
                )
            json_out.write(json_str)

    def export_fallback_context_to_json(self) -> None:
        """
        Converts just fallback context objects in Module Broker object to a JSON object
        """
        class DictEncoder(json.JSONEncoder):
            def default(self, o):
                return o.__dict__

        if not os.path.isdir(self.JSON_DICT):
            os.mkdir(self.JSON_DICT)

        all_fallback_contexts = []
        for module_info in self.module_info_data.values():
            if module_info.fallback_contexts:
                # Using this dict to format the inner outputs of this json file accordingly
                # Also only include attributes if they have an actual value assigned
                fallback_context = {}
                if module_info.module_id:
                    fallback_context["id"] = module_info.module_id
                if module_info.module_context:
                    fallback_context["context"] = {}
                    fallback_context["context"]["text"] = module_info.module_context

                fallback_context["node_fallbacks"] = []

                for fc in module_info.fallback_contexts:
                    # Using this dict to format the inner outputs of this json file accordingly
                    # Also only include attributes if they have an actual value assigned
                    node_context = {}
                    if fc.topic_name:
                        node_context["id"] = fc.topic_name
                    if fc.fallback_type:
                        node_context["opt"] = fc.fallback_type
                    if fc.fallback_text:
                        node_context["context"] = {}
                        node_context["context"]["text"] = fc.fallback_text
                    fallback_context["node_fallbacks"].append(node_context)
                all_fallback_contexts.append(fallback_context)

        # Format the outer output of this json file accordingly
        fallback_context_dict = {}
        if all_fallback_contexts:
            fallback_context_dict["modules"] = all_fallback_contexts

        with open(self.JSON_CONTEXT_FILE, "w") as json_out:
            json_str: str = json.dumps(
                fallback_context_dict,
                cls=DictEncoder,
                indent=2
            )
            json_out.write(json_str)

    ####---- ModuleInfo object getter functions ----####
    def get_info_by_uuid(self, uuid: str) -> ModuleInfo:
        """
        Given a .chatModule's UUID, return ModuleInfo for that file
        """
        if uuid not in self.module_info_data:
            return None
        return self.module_info_data[uuid]
    
    def get_info_by_module_id(self, module_id: str) -> ModuleInfo:
        """
        Given a Module ID, return the Module Info associated with it
        """
        for info in self.module_info:
            if module_id == info.module_id:
                return info

        # return None if module not found
        return None
    
    def get_info_by_module_ids(self, module_ids: List[str]) -> List[ModuleInfo]:
        """
        Given a list of Module IDs, return a List of their Module Info
        """
        module_infos: List[ModuleInfo] = []
        
        for info in self.module_info:
            if info.module_id in module_ids:
                module_infos.append(info)
        
        return module_infos
