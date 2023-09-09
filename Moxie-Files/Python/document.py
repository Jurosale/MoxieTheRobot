# README: This file was written by another teammate and is the base file for "module.py"

from typing import Any, Dict, List, Union
from jinja2 import Environment, FileSystemLoader
from graphviz import Digraph
import tempfile
import logging
import json
import os

from .boards.board import Board
from .boards.board_utils import BoardUtils
from .boards.excluded_board import ExcludedBoard
from .objects.elements.node import Node
from .objects.elements.flexible.flexible import Flexible
from .objects.elements.open_q.open_q import OpenQ
from .objects.elements.utility.exits.exit import ExitNode
from .objects.elements.templates.template_node import TemplateNode
from .objects.connections.connection import Connection
from .objects.connections.move_on_connection import MoveOnConnection
from .objects.object import Object
from .utils import compiler_cache
from .. import globals
from .. import native
from ..renderer.filters import DEFINED_FILTERS
from .logs import log


class Document(Object):
    _EXCLUDE_BOARD_KEY = "excludeDocument"

    _BOARDS_KEY = "boards"
    _ID_KEY = "conversationID"
    _NAME_KEY = "name"
    _VERSION_KEY = "version"
    _INDEX_KEY = "indices"
    _INFO_KEY = "docInfo"
    _NOTES_KEY = "notes"
    _DOC_STATUS_KEY = "documentStatus"
    _DOC_STATUS_IN_DEVELOPMENT = "inDevelopment"
    _DOC_STATUS_FINALIZED = "finalized"

    # Set up mapping of board json-key to python-class so we can simply extend this list to handle a growing list of
    # differing elements/template nodes
    _ELEMENTS_CLS_DICT = {
        "elements": Node,
        "flexibleElements": Flexible,
        "openQuestionElements": OpenQ,
        "moveOnOrExitElements": ExitNode,
        "templateElements": TemplateNode
    }

    _CONNECTION_CLS_DICT = {
        "connections": Connection,
        "moveOnConnections": MoveOnConnection
    }

    # Remove once explicit exit nodes are implemented in chat2cs2 and all .cc files converted
    _SPECIAL_LEGACY_INFO_KEY_EXIT = "onExit"
    _CONVERTED_FOR_EXPLICIT_EXIT = "ConvertedToExplicitExits"
    _DEFAULT_DOCUMENT_EXIT: str = "^exit_controller()"
    TEMPORARY_LEGACY_EXIT: str  # TODO: rename to lowercase and remove "temp" part of it
    TEMPORARY_LEGACY_EXIT_JINJA_KEY: str = "temporary_exit_code"

    name: str
    info: dict
    indices: str  # Used board's info dict keys
    conversation_id: str
    module_id: str  # Set only if part of the kwargs, we don't need it otherwise
    version: int
    # Base name
    filename: str
    # Full path
    filepath: str
    boards: List[Board] = []
    excluded_boards: List[ExcludedBoard] = []
    out_file_paths: List[str] = []

    uses_explicit_exits: bool = False
    temporary_exit_code: str  # TODO: rename to document_exit at some point, including jinja files
    
    # we should default to finalized for older documents I think just in case they were created
    # before I added this new json. This would likely be better suited to be a enum but I'm not
    # familiar with enums in python and don't have any time to learn so I leave it to you future
    # chat2cs dev..
    document_status: str = _DOC_STATUS_FINALIZED

    def __init__(self):
        super().__init__()
        self.name = ""
        self.info = {}
        self.indices = ""
        self.conversation_id = ""
        self.version = 0
        self.filename = ""
        self.filepath = ""
        self.boards = []
        self.excluded_boards = []
        self.temporary_exit_code = ""
        self.out_file_paths = []

    @property
    def excluded(self):
        """
        Property on document OBJECT if excluded or not
        """
        return False

    @staticmethod
    def is_excluded(file_path: str) -> bool:
        """
        Static method to check if a FILEPATH (str) should be excluded
        """
        file_data: dict = {}
        with open(file_path, "r") as f:
            file_data = json.loads(f.read())
        if Document._EXCLUDE_BOARD_KEY in file_data.keys():
            return file_data[Document._EXCLUDE_BOARD_KEY]
        else:
            return False

    @classmethod
    def from_file(cls, file_path: str, shallow: bool = False, garden_path: bool = False, **kwargs):
        """
        Creates an object representing the conversation and its connections across all boards from an EmPath file.

        Args:
            file_path: EmPath file
            shallow: if True, only compiles moduleInfo (useful for quick entry pattern tests, etc.)

        Returns:
            Document object
        """
        with open(file_path, "r") as f:
            file_data: dict = json.loads(f.read())
        if file_path not in compiler_cache.get_instance().files:
            compiler_cache.get_instance().files.add(file_path)
        else:
            compiler_cache.get_instance().files.get(file_path).update()
        return cls.from_json(file_data, file_path, shallow=shallow, garden_path=garden_path, **kwargs)

    @classmethod
    def from_json(cls, file_data: dict, filename: str = None, shallow: bool = False, garden_path: bool = False, **kwargs):
        """
        Creates an object representing the conversation and its connections across all boards from an EmPath file data.

        Args:
            file_data: json dictionary from an EmPath file
            filename: path or name of the document
            shallow: if True, only compiles moduleInfo (useful for quick entry pattern tests, etc.)

        Keyword Args:
            class_obj: the class object to operate on, when dependencies are required

        Returns:
            Document object
        """
        # Setup new document
        logging.debug("Setup new document")

        empath_doc = kwargs.get("class_obj", cls())
        empath_doc.module_id = kwargs.get("module_id", "")

        empath_doc.filename = os.path.basename(filename)
        empath_doc.filepath = filename
        empath_doc.name = file_data[cls._NAME_KEY]
        empath_doc.version = file_data[cls._VERSION_KEY]
        empath_doc.indices = file_data[cls._INDEX_KEY]

        if cls._DOC_STATUS_KEY in file_data:
            empath_doc.document_status = file_data[cls._DOC_STATUS_KEY]

        empath_doc.conversation_id = file_data[cls._ID_KEY]
        if empath_doc.conversation_id == "":
            if empath_doc.module_id == "":
                raise Exception(f"Document should have a conversation_id or module_id - file://{empath_doc.filepath} "
                                f"{log.context(empath_doc, 'module_id')}")
            empath_doc.conversation_id = empath_doc.module_id
        for info_dict in file_data[cls._INFO_KEY]:
            key = info_dict["key"]
            empath_doc.info[key] = info_dict["value"]

            if key == cls._SPECIAL_LEGACY_INFO_KEY_EXIT:
                # This value is likely going to stay even with Flexible2.0, so we can specify how this document exits
                empath_doc.TEMPORARY_LEGACY_EXIT = empath_doc.info[key]
                empath_doc.temporary_exit_code = empath_doc.info[key]
            elif key == cls._CONVERTED_FOR_EXPLICIT_EXIT:
                empath_doc.uses_explicit_exits = empath_doc.info[key] == "Yes"

        if not shallow:
            if not hasattr(empath_doc, "TEMPORARY_LEGACY_EXIT") or empath_doc.TEMPORARY_LEGACY_EXIT == "":
                # logging.warning(f"Document's '{cls._SPECIAL_LEGACY_INFO_KEY_EXIT}' field not set: file://{filename}")
                empath_doc.TEMPORARY_LEGACY_EXIT = ""
                empath_doc.temporary_exit_code = ""

            # Initialize document boards, elements, connections
            logging.debug("Initialize document boards, elements, connections")
            board_data = file_data[cls._BOARDS_KEY]
            for board_uuid in board_data.keys():
                logging.debug(f"board: {board_uuid}")
                json_data = board_data[board_uuid]

                if BoardUtils.is_board_excluded(json_data):
                    logging.debug(f"Creating excluded board '{board_uuid}', since marked as 'excluded'")
                    excluded_board = ExcludedBoard.from_json(parent_document=empath_doc,
                                                             uuid=board_uuid,
                                                             json_data=json_data)
                    logging.debug("Add all excluded element UUIDs")
                    for element_type_key in cls._ELEMENTS_CLS_DICT.keys():
                        if element_type_key in board_data[board_uuid].keys():
                            element_uuids: List[str] = board_data[board_uuid][element_type_key]
                            excluded_board.element_uuids.extend(element_uuids)

                    logging.debug("Add all excluded connection UUIDs")
                    for connection_type in cls._CONNECTION_CLS_DICT.keys():
                        if connection_type in board_data[board_uuid].keys():
                            connection_uuids: List[str] = board_data[board_uuid][connection_type]
                            excluded_board.connection_uuids.extend(connection_uuids)

                    empath_doc.excluded_boards.append(excluded_board)
                    continue

                board_class = BoardUtils.get_board_class_from_json(json_data)
                _board = board_class.from_json(parent_document=empath_doc,
                                               uuid=board_uuid,
                                               json_data=json_data)

                # Generically handle different element/template-node types, including name initialization
                logging.debug("Generically handle different element/template-node types")
                for element_type_key in cls._ELEMENTS_CLS_DICT.keys():
                    element_type_data = file_data.get(element_type_key, [])
                    if element_type_key in board_data[board_uuid].keys():
                        for element_uuid in board_data[board_uuid][element_type_key]:
                            logging.debug(f"    * {element_type_key}: {element_uuid}")
                            elem_class_name = cls._ELEMENTS_CLS_DICT[element_type_key]
                            elem = elem_class_name()
                            elem.uuid = element_uuid
                            elem.board = _board

                            # Make sure to set name now, for other operations may try to generate topic names fairly early
                            if elem.uuid not in element_type_data:
                                raise Exception(f"Element uuid '{elem.uuid}' should be found in the document's top-level "
                                                f"json keys")
                            
                            element_json = element_type_data[elem.uuid]
                            elem.set_node_name(element_json)

                            _board.elements.append(elem)

                # Generically handle different connection types
                # NOTE: This will miss moveOn connections since they are not serialized at the "board" level
                # We will add those connections to the board in the outer scope (next section)
                logging.debug("Generically handle different connection types")
                for connection_type in cls._CONNECTION_CLS_DICT.keys():
                    if connection_type not in board_data[board_uuid].keys():
                        continue

                    for conn_uuid in board_data[board_uuid][connection_type]:
                        logging.debug(f"    - {connection_type}: {conn_uuid}")
                        conn = cls._CONNECTION_CLS_DICT[connection_type]()
                        conn.uuid = conn_uuid
                        conn.board = _board
                        _board.connections.append(conn)

                empath_doc.boards.append(_board)

            # Setup connections data and relationships
            logging.debug("Set up connections data and relationships")
            for connection_type in cls._CONNECTION_CLS_DICT.keys():
                if connection_type not in file_data.keys():
                    continue

                connection_class = cls._CONNECTION_CLS_DICT[connection_type]

                # Loop through every board to find the connection from UUID
                connections_data = file_data[connection_type]
                for connection_uuid in connections_data:
                    # Skip connections in excluded boards
                    is_excluded = False
                    for excluded_board in empath_doc.excluded_boards:
                        if connection_uuid in excluded_board.connection_uuids:
                            is_excluded = True
                            break
                    if is_excluded:
                        continue

                    data = connections_data[connection_uuid]
                    conn_found = False

                    # Move on connections are not serialized at the board level from the EmPath document
                    # However, logically it should still belong to the originating node's board
                    if connection_class is MoveOnConnection:
                        logging.debug(f"    Setting moveOn topic connections to source node's board")
                        conn_found = True
                        conn = connection_class()
                        conn.uuid = connection_uuid
                        conn.fill_from_json(data, document=empath_doc)
                    else:
                        # Regular connections
                        for _board in empath_doc.boards:
                            conn = _board.get_connection(connection_uuid)
                            if conn is not None:
                                conn.fill_from_json(data)
                                conn_found = True
                                break

                    if not conn_found:
                        conn_obj = Object()
                        conn_obj.uuid = connection_uuid
                        raise Exception(f"Connection {log.context(conn_obj)} (type: {connection_type}) "
                                        f"was not found on any boards (including excluded boards)")

            # Setup node data for every node-class
            logging.debug(f"Set up node data for every node-class")
            excluded_e_uuids = set(e for b in empath_doc.excluded_boards for e in b.element_uuids)
            for elem_class_name in cls._ELEMENTS_CLS_DICT.keys():
                logging.debug(f"    Node class: {elem_class_name}")
                # node_class = cls._ELEMENTS_CLS_DICT[node_class_name]

                if elem_class_name not in file_data:
                    logging.debug(f"        File does not contain this element class, skipped: {elem_class_name}")
                    continue

                elements_data = file_data[elem_class_name]
                for element_uuid in elements_data:
                    # Skip elements in excluded boards
                    if element_uuid in excluded_e_uuids:
                        continue

                    # Find element in board
                    elem = None
                    for _board in empath_doc.boards:
                        elem = _board.get_element(element_uuid)
                        if elem is not None:
                            break

                    if elem is None:
                        raise Exception(f"Element '{element_uuid}' not found in any boards (including excluded boards), "
                                        f"some data is lost")
                    else:
                        logging.debug(f"    Found element '{elem.name}' {log.context(elem)} in board "
                                      f"'{elem.board.name}'")
                        data = elements_data[element_uuid]
                        elem.fill_from_json(data, document=empath_doc)

            empath_doc.boards.sort(key=(lambda a: a.order))
            for _board in empath_doc.boards:
                if _board.has_intro():
                    if not _board.validate_node_names():
                        raise Exception(f"Node names exception {log.context(_board)}. See above for error.")

                    _board.validate_connections()
                    _board.analyze_topic_clusters()
                    _board.validate_exits()

                if garden_path == True and _board.garden_path_nodes:
                    _board.generate_garden_path_script()

        return empath_doc

    def is_board_excluded(self, uuid: str) -> bool:
        for board in self.excluded_boards:
            if board.uuid == uuid:
                return True
        return False

    def is_board_name_excluded(self, name: str) -> bool:
        for board in self.excluded_boards:
            if board.name == name:
                return True
        return False

    def is_connection_excluded(self, uuid: str) -> bool:
        for board in self.excluded_boards:
            if uuid in board.connection_uuids:
                return True
        return False

    def is_element_excluded(self, uuid: str) -> bool:
        for board in self.excluded_boards:
            if uuid in board.element_uuids:
                return True
        return False

    def is_module(self):
        return False

    # currently only two states.. 'inDevelopment' and 'finalized'
    def is_status_finalized(self) -> bool:
        return self.document_status == Document._DOC_STATUS_FINALIZED

    def get_prefix_from_conversation_id(self) -> str:
        return self.conversation_id.split('_')[0]

    def get_board_by_name(self, name: str, include_excluded_boards: bool = False) -> Union[Board, None]:
        result = None
        for b in self.boards:
            if b.name == name:
                result = b
                break

        if include_excluded_boards:
            for b in self.excluded_boards:
                if b.name == name:
                    result = b
                    break
        return result

    def get_board(self, uuid: str) -> Union[Board, None]:
        """
        Gets the board by UUID. None if not found

        Args:
            uuid: identifier for the board

        Returns:
            The board if found, otherwise None
        """
        result = None
        for b in self.boards:
            if b.uuid == uuid:
                result = b
                break
        return result

    def get_node(self, board_uuid: str, node_uuid: str):
        result = None
        board = self.get_board(board_uuid)
        if board is not None:
            for element in board.elements:
                if element.uuid == node_uuid:
                    result = element
                    break
        return result

    def get_dependent_chat_template_info_uuids(self) -> List[str]:
        """
        Returns any chat template info uuids we use.
        """
        template_info_uuids = []
        for board in self.boards:
            for node in board.elements:
                if not issubclass(node.__class__, TemplateNode):
                    continue
                if not node.subtype_data.template_uuid in template_info_uuids:
                    template_info_uuids.append(node.subtype_data.template_uuid)
        return template_info_uuids

    def render(self, **kwargs) -> str:
        """
        Recursively renders all boards and elements in this document. Returns output string.
        """
        output = ""
        jinja_environment = Environment(loader=FileSystemLoader(
            globals.JINJA_TEMPLATE_DIR), extensions=['jinja2.ext.do'])
        # jinja_environment.filters.update(DEFINED_FILTERS)
        for k,v in DEFINED_FILTERS.items():
            jinja_environment.globals[k] = v
        for _board in self.boards:
            # This is how design stop a board from building
            if not _board.has_intro():
                log.warn_legacy(f"Skipped board due to lack of Intro node {log.context(_board)}",
                                log.LegacyType.IMPLICIT_EXCLUDE_BOARD)
                continue

            output += _board.render(jinja_environment=jinja_environment,
                                    legacy_document_exit=self.TEMPORARY_LEGACY_EXIT, **kwargs)

        self.validate(output)

        return output

    def render_and_write(self, out_file: str, **kwargs) -> str:
        out_str = self.render()
        directory = os.path.dirname(out_file)
        if not os.path.exists(directory):
            os.makedirs(directory)

        if out_str != "":
            with open(out_file, "w") as f:
                f.write(out_str)

            if not self.validate(out_str):
                raise Exception(f"Some errors where found when rendering document: {self.filename}. See above for more specific details on the error(s). "
                                f"File written to: file://{out_file}")

            if out_file not in self.out_file_paths:
                self.out_file_paths.append(out_file)

        return out_file

    def validate(self, rendered_text: str) -> bool:
        results_valid = True

        # Gather gambit topics
        lines = []
        for line in rendered_text.split("\n"):
            line = line[:line.find("#")]
            lines.append(line)

        gambit_topics_found = native.get_gambit_topics_from_text(rendered_text)
        topics_available: List[str] = []
        topics_available.extend(globals.KNOWN_EXTERNAL_TOPICS)  # Topics external to EmPath are sometimes gambitted to
        for line in lines:
            if "topic:" in line:
                topic_name = line[line.find("~") + 1:]
                topic_name = topic_name[:topic_name.find(" ")]
                if topic_name not in topics_available:
                    topics_available.append(topic_name)

        missing_topics: List[str] = []
        for gambit_topic in gambit_topics_found:
            if gambit_topic not in topics_available:
                missing_topics.append(gambit_topic)

        if len(missing_topics) > 0:
            logging.error(f"Some gambit topics cannot be found in {len(gambit_topics_found)} gambit topics, "
                          f"{len(topics_available)} available topics {log.context(self.boards[0])}")
            i = 0
            while i < len(missing_topics):
                logging.error(f"    - Cannot find topic {missing_topics[i].__repr__()} for gambit {i + 1}/{len(topics_available)} "
                              f"available topics {log.context(self.boards[0])}")
                results_valid = False
                i += 1

            if len(gambit_topics_found) > len(topics_available):
                results_valid = False
                logging.error(f"    - Gambits have more topic variations than topics {log.context(self.boards[0])}")

        return results_valid

    def graph_viz(self) -> Digraph:
        """
        Renders the document into a graph and opens the resulting TEMP image for human preview

        All node names have board names attached to avoid false cross-board connections on commonly named elements
        """
        def has_code(element: Node) -> bool:
            return isinstance(element, Node) and \
                   hasattr(element, "code") and \
                   element.code is not None and \
                   element.code != ""
        
        def get_nice_name(element: Node) -> str:
            """
            Formats the element's display name to be unique for graphing
            """
            name = f"{element.name}\n({element.board.name})\n{element.uuid[-4:]}"

            if has_code(element):
                # name += f"\ncode={element.code}"
                name += f"\nuses code field"

            return name

        def get_node_data(element: Node) -> str:
            return str({"prompt": element.text if hasattr(element, "text") else "<empty>"})

        def get_connection_data(c: Connection) -> str:
            return str({"pattern": c.pattern if hasattr(c, "pattern") else "<empty>"})

        def add_topic_node(element: Node, graph):
            if has_code(element):
                graph.node(get_nice_name(element), shape="Msquare", fillcolor="yellow", style="filled", comment=get_node_data(element))
            else:
                graph.node(get_nice_name(element), shape="Msquare", comment=get_node_data(element))

        def add_response_node(element: Node, graph):
            if has_code(element):
                graph.node(get_nice_name(element), shape="box", fillcolor="yellow", style="filled", comment=get_node_data(element))
            else:
                graph.node(get_nice_name(element), shape="box", comment=get_node_data(element))

        def add_rejoinder_node(element: Node, graph):
            graph.node(get_nice_name(element), shape="doubleoctagon", comment=get_node_data(element))

        def add_board_intro_node(element: Node, graph):
            if has_code(element):
                graph.node(get_nice_name(element), shape="Msquare", color="green", fillcolor="yellow", style="filled",
                           comment=get_node_data(element))
            else:
                graph.node(get_nice_name(element), shape="Msquare", color="green", fillcolor="green", style="filled",
                           comment=get_node_data(element))

        def add_board_exit_node(element: Node, graph):
            graph.node(get_nice_name(element), shape="Msquare", color="orange", fillcolor="orange", style="filled", comment="opinions")

        def add_info(info_str: str, graph):
            graph.node(name=f"document_info_{info_str}", label=info_str, shape="note")

        dot = Digraph(comment=self.name)

        doc_string = "DocInfo:"
        doc_string += f"\lName: {self.name}"
        for key in self.info:
            doc_string += f"\l{key}: {self.info[key]}"
        add_info(doc_string, dot)

        for _board in self.boards:
            # "cluster" is a keyword for graphviz to group things together
            with dot.subgraph(name=f"cluster_{_board.name}") as subgraph:
                board_string = "BoardInfo:"
                board_string += f"\lName: {_board.name}"
                for key in _board.info:
                    board_string += f"\l{key}: {_board.info[key]}"
                add_info(board_string, subgraph)
                board_exits = _board.get_exit_nodes()

                # Non-topic-clustered elements
                for e in _board.topic_non_cluster_nodes:
                    if e.is_intro:
                        add_board_intro_node(e, subgraph)
                    elif e in board_exits:
                        add_board_exit_node(e, subgraph)
                    else:
                        add_topic_node(e, subgraph)

                # Topic-cluster elements (add topic, responses, rejoins)
                # NOTE: Visually we are not going to worry deeper graph nesting YET... but
                # CS conversion will function fine with this approach. Consider the following nested case:
                #     done 3: [
                #         responses:
                #             what is this,
                #             final idk,
                #         rejoinders:
                #     ]
                #     what is this: [
                #         responses:
                #             What does your drawing.. Handler,
                #         rejoinders:
                #     ]
                for topic_key in _board.topic_clusters.clusters.keys():
                    with subgraph.subgraph(name=f"cluster_{topic_key.name}") as sg:
                        if topic_key.is_intro:
                            add_board_intro_node(topic_key, sg)
                        else:
                            add_topic_node(topic_key, sg)

                        for response in _board.topic_clusters.clusters[topic_key].get_responses():
                            add_response_node(response.node, sg)
                        for rejoinder in _board.topic_clusters.clusters[topic_key].get_rejoinders():
                            add_rejoinder_node(rejoinder.node, sg)

                # Connections
                for c in _board.connections:
                    if issubclass(MoveOnConnection, c.__class__):
                        if len(c.name) > 25:
                            split_len = round(len(c.name)/2)
                            label = f"move name: '{c.name[:split_len]}\n{c.name[split_len:]}'"
                        else:
                            label = f"move name: '{c.name}'"
                    else:
                        label = ""
                        if c.name != "":
                            label = f"name: '{c.name[:20]}'"
                        if c.pattern is not None:
                            if label != "":
                                label += "\n"
                            label += f"pattern: '{c.pattern[:20]}'"

                    if c.source is not None and c.destination is not None:
                        subgraph.edge(get_nice_name(c.source), get_nice_name(c.destination), label=label, comment=get_connection_data(c))
                    else:
                        logging.warning(f"Source or destination on a connection is None {log.context(c)}")

        # logging.info(dot.source)
        t = tempfile.NamedTemporaryFile(mode="w")
        t.close()
        logging.info(t.name)
        dot.render(t.name, view=True)
        return dot
