# README: takes in ChatScript topics and loads/stores them in caches for faster compilations

from typing import Any, Dict, List, Tuple, Union

import copy
import logging
import os
from functools import partial
import pathlib
import pickle
import shutil
import tqdm

from ..... import CACHE_SUB_DIR
from .... import globals
from ...logs import log
from . import corruption
from . import topic_cache_utils
from .cache_base import CacheBase

SAFE_SPECIAL_CHARACTER = "_"
SPECIAL_CHARACTER_LIST = [" ", "/"]
DOC_FILE_SUFFIX_NAME = "_data"
TOPIC_CACHE_DIRECTORY_SUFFIX_NAME = "_V"


class TopicCache(CacheBase):
    class Document:
        filename: str
        board = None
        topics: Dict[str, Any]

        def __init__(self, topic_name: str, board, topic_obj):
            self.filename = board.parent.filepath
            self.board = board
            self.topics = {topic_name: topic_obj}

        @property
        def topic_names(self) -> List[str]:
            results = []
            for key in self.topics:
                topic = self.topics[key]
                if topic is not None:
                    results.append(topic.topic_name)
            return results

        @property
        def filepath(self) -> str:
            return self.filename

        def doc_dir_path(self) -> str:
            """
            Grabs the document's directory path and returns it (meant to be a subdirectory of the topic cache's directory).
            Also appends the document's board name to the end of the basename (as an index)
            """
            path = self.filename

            # Grab the name of the chat module file and remove the ".chatModule" suffix
            file_name = os.path.basename(path)
            file_name = file_name[:file_name.rfind(".")]

            # Now grab the filepath of the chat module folder and remove everything up to the "CONVERSATIONS" directory
            # Also remove problematic specical characters in this top-level directory name
            # Grabs last element instead of 2nd element incase filepath has no "CONVERSATIONS" directory 
            directory_name = os.path.dirname(path).split("/CONVERSATIONS/", 1)[-1]
            for character in SPECIAL_CHARACTER_LIST:
                directory_name = directory_name.replace(character, SAFE_SPECIAL_CHARACTER)

            # Remove problematic special characters in the board's name
            board_name = self.board.name
            for character in SPECIAL_CHARACTER_LIST:
                board_name = board_name.replace(character, SAFE_SPECIAL_CHARACTER)

            # Return this new directory path
            doc_dir_path = os.path.join(directory_name, file_name)
            return f"{doc_dir_path}_{board_name}"

        def shallow_copy(self) -> "Document":
            """
            Creates a shallow copy of the doc object containing only its filename and board object
            The topic dict is emptied out in the shallow copy only
            """
            shallow_doc = copy.copy(self)
            shallow_doc.topics = {}
            return shallow_doc

    _docs = List[Document]
    _instructions = List[Dict]

    def __contains__(self, topic: str) -> bool:
        for doc in self._docs:
            topic_names_set = set(doc.topics.keys())
            if topic in topic_names_set:
                return True
        return False

    def __getitem__(self, item) -> Document:
        """
        Returns a document object

        Args:
            item: If a string, assumes the topic string. Otherwise assumes as board object
        """
        is_topic_name = type(item) == str

        if is_topic_name:
            for doc in self._docs:
                if item in doc.topics.keys():
                    return doc

            raise Exception(f"'{self.__class__.__name__}' object does not contain item '{item}' ({type(item)})")
        else:
            for doc in self._docs:
                if doc.board == item:
                    return doc

            # Error if not found
            if item is not None:
                raise Exception(f"'{self.__class__.__name__}' object does not contain item '{item.name}' "
                                f"({item.parent.filepath})")
            else:
                raise Exception(f"'{self.__class__.__name__}' object does not contain item '{item}' ({type(item)})")

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def __init__(self):
        """
        On initialization of new TopicCache object, assign these static values to it
        """
        super().__init__()
        self._version = 2
        self._instructions = [
            { "version": 2, "func": topic_cache_utils.downgrade_v2_to_v1, "extra_args": None },
            { "version": 2, "func": topic_cache_utils.load_v2, "extra_args": None }
        ]

    @property
    def items(self) -> list:
        self._docs.sort(key=lambda x: x.filepath)
        return self._docs

    @property
    def version(self) -> int:
        return self._version

    @property
    def instructions(self) -> list:
        return self._instructions

    def add(self, topic_name: str, board_obj, topic_obj, **kwargs):
        """
        Add topics one by one to account for transient compiled topics list on a rolling basis

        Args:
            topic_name: the generated topic name
            board_obj: the topic's board object
            topic_obj: the topic class object
        """
        # Check if this new doc has an existing board...
        board_obj_in_cache = None
        for doc_obj in self._docs:
            if board_obj.parent.filepath == doc_obj.filepath and board_obj.name == doc_obj.board.name:
                board_obj_in_cache = doc_obj
                break

        # ...And if so, update it's topic contents
        if board_obj_in_cache is not None:
            if topic_name in board_obj_in_cache.topics:
                raise Exception(f"Board '{board_obj.name}' already contains a topic named '{topic_name}' in file://{board_obj.parent.filepath} {log.context(board_obj)}")
            board_obj_in_cache.topics[topic_name] = topic_obj
            logging.debug(f"Updated with '{topic_name}' to board '{board_obj.name}'. Total {topic_cache_utils.DOCS_ATTRIBUTE_NAME} '{len(self._docs)}'.")
        # Else create a new doc object
        else:
            doc = self.Document(topic_name=topic_name, board=board_obj, topic_obj=topic_obj)
            self._docs.append(doc)
            logging.debug(f"Added '{topic_name}' with new board '{board_obj.name}' to the doc list. Total {topic_cache_utils.DOCS_ATTRIBUTE_NAME} '{len(self._docs)}'.")

    def clear(self, **kwargs):
        self._docs = []

    def get_by_file(self, abs_path: str) -> list:
        results = []
        for doc in self._docs:
            if doc.filepath == abs_path:
                results.append(doc)

        return results

    def topic_cache_dir_path(self) -> str:
        """
        Grabs the topic cache's directory path and returns it as a subdirectory of "sub_caches".
        Also appends the topic Cache's version number to the end of the basename (as an index)
        """
        topic_cache_dir_name = self.__class__.__name__
        if hasattr(self, topic_cache_utils.VERSION_ATTRIBUTE_NAME):
            topic_cache_dir_name += TOPIC_CACHE_DIRECTORY_SUFFIX_NAME + str(self.version)
        
        topic_cache_dir_path = os.path.join(CACHE_SUB_DIR, topic_cache_dir_name)
        return topic_cache_dir_path

    def shallow_copy(self) -> "TopicCache":
        """
        Creates a shallow copy of the TopicCache object containing only its build version and downgrade instructions
        The list of docs is emptied out in the shallow copy only
        """
        shallow_topicCache = copy.copy(self)
        shallow_topicCache._docs = {}
        return shallow_topicCache

    def write(self):
        # Don't overwrite if not yet loaded
        if self.needs_loading_from_file:
            return

        # Store the newest build version of TopicCache inside the TopicCache file
        # Using a shallow copy of TopicCache to only store instructions and build version
        # Shallow copy ensures we don't store duplicated doc list content
        topic_cache_dir_path = self.topic_cache_dir_path()
        topic_cache_filepath = os.path.join(CACHE_SUB_DIR, self.__class__.__name__)
        with open(topic_cache_filepath, "wb") as f:
            pickle.dump(self.shallow_copy(), f, pickle.DEFAULT_PROTOCOL)

        # Delete any and all existing TopicCache directory
        cache_files = pathlib.Path(CACHE_SUB_DIR).glob('*')
        for cache_file in cache_files:
            if os.path.isdir(cache_file) and self.__class__.__name__ in os.path.basename(cache_file):
                logging.info(f"Removing directory '{cache_file}'.")
                shutil.rmtree(cache_file)

        # Keep track of how many files we're writing
        # This should match the number of files we loaded right before this
        doc_data_files = 0
        doc_topic_files = 0
        for doc in tqdm.tqdm(self._docs, ncols=100, desc=f"Writing all '{topic_cache_utils.DOCS_ATTRIBUTE_NAME}' in topic sub caches version '{self.version}'",
                             disable=globals.DISABLE_PROGRESS_BARS):
            # Create the {doc_dir_path}_{board_name} directory if we haven't already
            doc_dir_path = os.path.join(topic_cache_dir_path, doc.doc_dir_path())
            if not os.path.isdir(doc_dir_path):
                os.makedirs(doc_dir_path)

            # Iterate through every topic name and its topic object found in these docs (i.e. empath boards)
            for topic_name in doc.topics.keys():
                topic_obj = doc.topics[topic_name]
                topic_content = {topic_name: topic_obj}

                # Write the single entry topic dict of each topic located inside this doc
                # But only if that topic's file doesn't already exist in this sub directory
                doc_topic_path = os.path.join(doc_dir_path, topic_name)
                if not os.path.exists(doc_topic_path):
                    with open(doc_topic_path, "wb") as f:
                        pickle.dump(topic_content, f, pickle.DEFAULT_PROTOCOL)
                    doc_topic_files += 1

            # Lastly, create the {doc_dir_path}_{board_name}_data file
            # Using a shallow copy to store filepath and board information in the "data" directory
            # Shallow copy ensures we don't store duplicated topics content
            doc_dir_path_dirname = os.path.dirname(doc_dir_path)
            doc_dir_path_basename = os.path.basename(doc_dir_path) + DOC_FILE_SUFFIX_NAME
            doc_path_name = os.path.join(doc_dir_path_dirname, doc_dir_path_basename)
            if os.path.exists(doc_path_name):
                corruption.set_corrupted(True, message=f"This data file '{doc_path_name}' already exists in the topic cache.")
                raise Exception(f"Cache file write error. Halting process to prevent overwrite of this data file: '{doc_path_name}'. "
                                f"Please re-run last command (twice if another error pops up shortly after re-running command) {log.context(doc.board)}")
            with open(doc_path_name, "wb") as f:
                pickle.dump(doc.shallow_copy(), f, pickle.DEFAULT_PROTOCOL)
            doc_data_files += 1

        logging.info(f"Total {topic_cache_utils.DOCS_ATTRIBUTE_NAME} '{len(self._docs)}'. Total number of data files written '{doc_data_files}'. "
                     f"Total number of topic files written '{doc_topic_files}'.")

    def _load(self):
        def load_topic_cache_file() -> Union[TopicCache, None]:
            """
            Retrieves, loads and returns the info found inside the single "TopicCache" file
            This file should be found in all current build versions
            """
            _topic_cache_filepath = os.path.join(CACHE_SUB_DIR, self.__class__.__name__)

            if not os.path.exists(_topic_cache_filepath):
                return None

            _topic_cache_file = None
            data = bytearray()
            with open(_topic_cache_filepath, "rb") as f:
                print(f"Grabbing all info inside the '{self.__class__.__name__}' file. This may take a few minutes.")
                for byte in iter(partial(f.read, 1024), b''):
                    data += bytearray(byte)
                _topic_cache_file = pickle.loads(data)

            return _topic_cache_file

        def _downgrade_instructions():
            """
            Given a list of chronologically ordered instructions inside the instructions attribute,
            Call each instruction (a downgrade function which takes in the topicCache object and other optional args)
            To downgrade the object's build version until it matches the desired version and return this new build
            """
            # TODO: implement downgrade functionality
            raise NotImplementedError(f"No downgrade instructions available for version '{_topic_cache_file.version}'.")

        def _upgrade_instructions(_topic_cache_file, _doc_data_files, _doc_topic_files, _target_version) -> TopicCache:
            """
            Given the current TopicCache build version, call the needed operations
            To continuously upgrade the TopicCache until its build version is up to date
            This list of operations will grow as we implement more build versions

            Args:
                _topic_cache_file: the current TopicCache file containing the TopicCache object (or dict for v1 builds)
                _doc_data_files: current number of loaded data files
                _doc_topic_files: current number of loaded topic files
                _target_version: the desired build version number
            """
            # Set the version build to whatever version the TopicCache file is
            logging.info(f"'{self.__class__.__name__}' is on an old version. Need to upgrade to version '{_target_version}'.")
            if not hasattr(_topic_cache_file, topic_cache_utils.VERSION_ATTRIBUTE_NAME):
                setattr(self, topic_cache_utils.VERSION_ATTRIBUTE_NAME, 1)
            else:
                setattr(self, topic_cache_utils.VERSION_ATTRIBUTE_NAME, _topic_cache_file.version)

            # Upgrade until we reach the desired build version (i.e. the current one)
            while self.version != _target_version:
                if self.version == 1:
                    _doc_data_files, _doc_topic_files = topic_cache_utils.upgrade_v1_to_v2(self, _doc_data_files, _doc_topic_files)
                else:
                    raise NotImplementedError(f"No upgrade instructions available for version '{self.version}'.")

            return _doc_data_files, _doc_topic_files

        if not corruption.is_corrupted():

            self._docs = []

            # Keep track of how many files we're loading
            # This should match the number of files we end up writing right after this
            doc_data_files = 0
            doc_topic_files = 0

            try:
                # Ensure topic cache directory and/or file exists and compiled correctly before starting
                topic_cache_file = load_topic_cache_file()
                if topic_cache_file is None:
                    corruption.set_corrupted(True, message="TopicCache file doesn't exist")
                    raise Exception(f"Cache file read error. Halting process because '{self.__class__.__name__}' file doesn't exist. "
                                    f"Please re-run last command (twice if another error pops up shortly after re-running command)")

                # If the loaded object's build version is old or doesn't exist (i.e. it's really old),
                # Load up the doc list and then continuously upgrade until we reach the current build version
                if not hasattr(topic_cache_file, topic_cache_utils.VERSION_ATTRIBUTE_NAME) or topic_cache_file.version < self.version:
                    if not hasattr(topic_cache_file, topic_cache_utils.VERSION_ATTRIBUTE_NAME) or topic_cache_file.version == 1:
                        doc_data_files, doc_topic_files = topic_cache_utils.load_v1(self, topic_cache_file, doc_data_files, doc_topic_files)
                    else:
                        raise NotImplementedError(f"No loading process available for version '{topic_cache_file.version}'.")
                    doc_data_files, doc_topic_files = _upgrade_instructions(topic_cache_file, doc_data_files, doc_topic_files, self.version)

                # If the loaded object's build version is newer than the current build (i.e. a "futuristic" build),
                # Load up the doc list and continuously downgrade until we reach the current build version
                elif topic_cache_file.version > self.version:
                    _downgrade_instructions()

                # If the loaded object's build version is up to date, just load up the doc list
                else:
                    doc_data_files, doc_topic_files = topic_cache_utils.load_v2(self, topic_cache_file, doc_data_files, doc_topic_files)

            except:
                corruption.set_corrupted(True, message=f"Read error detected for TopicCache")
                raise Exception(f"Cache file read error, halting loading process in '{self.__class__.__name__}'. "
                                f"Please re-run last command (twice if another error pops up shortly after re-running command)")

            logging.info(f"Total {topic_cache_utils.DOCS_ATTRIBUTE_NAME} '{len(self._docs)}'. Total number of data files loaded '{doc_data_files}'. "
                  f"Total number of topic files loaded '{doc_topic_files}'.")

        else:
            print(f"Something in '{self.__class__.__name__}' is corrupted, skipping loading process.")

        self._needs_loading_from_file = False
