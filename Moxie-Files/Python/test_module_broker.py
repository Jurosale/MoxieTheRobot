# README: Co-developed with a teammate to implement various unit tests for "module_broker.py"

import os
from typing import Dict, List
import shutil
import unittest

from .... import SHEETS_DIR, CONVERSATIONS_DIR
from ... import chat2cs
from ..modules.module_broker import ModuleBroker
from ..utils import unit_test_utils
from ..utils import compiler_cache
from ..objects.tags.content_tag import ContentTag
from ..objects.tags.sel_tag import SelTag


class TestModuleBroker(unittest.TestCase):
    # Tests to validate ModuleBroker is working properly
    # 1. create ModuleBroker properly inits list of ModuleInfo objs
    # 2. ModuleBroker created and cached durning chat2cs
    # 3. ModuleBroker properly Updated during chat2cs
    # 4. ModuleBroker reference in .chatSystem files preserved after pickle
    _DIR = os.path.dirname(__file__)
    _TEST_FILES_DIR: str = os.path.join(_DIR, "test_module_broker/")
    _UPDATE_FILES_DIR: str = os.path.join(_TEST_FILES_DIR, "update_files/")
    _SUPPORT_FILES_DIR: str = os.path.join(_DIR, "module_broker_support_files/")
    _INDEX_FILE_NAME: str = "MODBROKER1_index.csv"
    _CONVERSATION_FILE_NAME: str = "test_chat_conversation_1.chatConversation"
    _MODULE_WITH_INDEX_FILE_NAME: str = "test_module_1.chatModule"
    _UNITTEST_DIR_NAME: str = "UNITTEST_MODULE_BROKER_"

    # TODO: look into adding more unit test support functions to better test "related files" functionality - Juan 7.20.22
    _TEMP_INDEX_FILE_PATH: str = os.path.join(SHEETS_DIR, _UNITTEST_DIR_NAME + _INDEX_FILE_NAME.split(".")[0], _INDEX_FILE_NAME)
    _TEMP_CONVERSATION_FILE_PATH: str = os.path.join(CONVERSATIONS_DIR, _UNITTEST_DIR_NAME + _MODULE_WITH_INDEX_FILE_NAME.split(".")[0], _CONVERSATION_FILE_NAME)

    # module UUIDs
    _MOD_1_UUID: str = "237BA5E3-416B-4102-9CB0-EFA8486F3E4D"
    _MOD_2_UUID: str = "7A738882-63E1-4404-87F8-686B26F13669"
    _MOD_3_UUID: str = "891A45AC-AFE0-4A3E-BB5C-73E5E86480BD"

    # Set Up test env
    @classmethod
    def setUpClass(cls) -> None:
        # Backup generated files
        cls._COMPILER_BACKUP_PATH = compiler_cache.backup(remove=True)
        cls.BACKUP_SRC, cls.BACKUP_DST = chat2cs.backup_generated_files()

    @classmethod
    def tearDownClass(cls) -> None:
        # remove all added files from cache
        compiler_cache.get_instance().clear()
        # Restore generated files
        compiler_cache.restore(cls._COMPILER_BACKUP_PATH, remove=True)
        chat2cs.restore_generated_files(cls.BACKUP_DST, cls.BACKUP_SRC)
        # remove copied files
        unit_test_utils.remove_test_files(cls._TEST_FILES_DIR, cls._UNITTEST_DIR_NAME)
    
    # set up for each test
    def setUp(self) -> None:
        # Add the testing index sheet & .chatConversation files
        # NOTE 1: The testing index sheet & .chatConversation file need to have their filepaths
        # hardcoded to specific locations instead of generating generic locations
        # NOTE 2: This ensures the index sheet is officially created inside our SHEETS directory
        # while the .chatConversation file shares its directory with its "related" .chatModule file
        os.mkdir(os.path.dirname(self._TEMP_INDEX_FILE_PATH))
        shutil.copyfile(os.path.join(self._SUPPORT_FILES_DIR, self._INDEX_FILE_NAME), self._TEMP_INDEX_FILE_PATH)
        os.mkdir(os.path.dirname(self._TEMP_CONVERSATION_FILE_PATH))
        shutil.copyfile(os.path.join(self._SUPPORT_FILES_DIR, self._CONVERSATION_FILE_NAME), self._TEMP_CONVERSATION_FILE_PATH)

        unit_test_utils.copy_test_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME, recursive=False)

    def tearDown(self) -> None:
        # Remove the testing index sheet & .chatConversation files as well as the testing index sheet's directory
        # NOTE 1: The temp conversation directory will get deleted in the remove_test_files() call below since...
        # NOTE 2: A .chatConversation file MUST be in the same (or sub) directory as its "related" .chatModule file
        os.remove(self._TEMP_INDEX_FILE_PATH)
        os.rmdir(os.path.dirname(self._TEMP_INDEX_FILE_PATH))
        os.remove(self._TEMP_CONVERSATION_FILE_PATH)

        # remove all added files from cache
        compiler_cache.get_instance().clear()
        # remove copied files
        unit_test_utils.remove_test_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)

    # tests
    def test_broker_init(self):
        """
        Test that validates ModuleBroker object is properly constructed as part of chat2cs
        """
        # compile files with chat2cs
        compiled_modules, compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)

        self.assertTrue(len(compiled_convos) < 1, msg="Did not expect to compile Chat Conversation")

        # get module broker
        module_broker: ModuleBroker = compiler_cache.get_instance().compiled_systems.broker

        # validate module_broker.module_info_data uuid is mapped correctly
        for uuid, module_info in module_broker.module_info_data.items():
            self.assertEqual(uuid, module_info.uuid, msg=f"UUID ({uuid}) does not match mapped .chatModule UUID ({module_info.uuid})")
        
        # validate data properly copied to ModuleBroker
        for module in compiled_modules:
            # get Module Info obj for given module
            module_info = module_broker.get_info_by_uuid(module.uuid)
            # ensure the object is in the Module Broker
            self.assertFalse(module_info == None)
            # validate the data has been copied correctly
            self.assertEqual(module.uuid, module_info.uuid, msg=f"Module UUID ({module.uuid}) does not match ModuleInfo UUID ({module_info.uuid})")
            self.assertEqual(module.module_id, module_info.module_id, msg=f"Module ID ({module.module_id}) does not match ModuleInfo Module ID ({module_info.module_id})")
    
    def test_broker_update(self):
        """
        Test ModuleBroker update() function properly updates an existing Module Broker obj
        """

        # init expected test outcomes
        initial_module_name: Dict[str, str] = {
            "237BA5E3-416B-4102-9CB0-EFA8486F3E4D" : "Unit Test Module Broker 1",
            "7A738882-63E1-4404-87F8-686B26F13669" : "Unit Test Module Broker 2",
            "891A45AC-AFE0-4A3E-BB5C-73E5E86480BD" : "Unit Test module broker 3"
        }
        # init expected test outcomes
        update_module_name: Dict[str, str] = {
            "237BA5E3-416B-4102-9CB0-EFA8486F3E4D" : "Unit Test Module Broker 1",
            "7A738882-63E1-4404-87F8-686B26F13669" : "this is an update! to the second Unit Test Module File!",
            "891A45AC-AFE0-4A3E-BB5C-73E5E86480BD" : "Update Unit 3 test!"
        }

        # compile files with chat2cs
        compiled_modules, compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(compiled_convos) < 1, msg="Did not expect to compile Chat Conversation")
        # Riely Allen 4/28/22: create own Module Broker tests both 
        # 1) can create module broker from list of files
        # 2) ensures Update Broker actually updates the object, not create a new one
        # create module broker from Module Documents
        compiled_topics = compiler_cache.get_instance().topics.items
        module_broker: ModuleBroker = ModuleBroker(compiled_modules, compiled_topics)
        # validate initial module names
        for uuid, expected_name in initial_module_name.items():
            # ensure module obj found for uuid
            mod_info = module_broker.get_info_by_uuid(uuid)
            self.assertFalse(mod_info is None, msg=f"Can't find Module Info for UUID ({uuid})")
            # validate module name is expected
            self.assertEqual(mod_info.module_name, expected_name, msg=f"Initial Module Name ({mod_info.module_name}) does not match Expected Name ({expected_name})")
        
        # update module files
        unit_test_utils.copy_test_files(self._UPDATE_FILES_DIR, self._UNITTEST_DIR_NAME, recursive=False)

        # remove all added cache topics from the previous compile_chat_files() call before calling it again
        # NOTE: this feels hacky and is the direct result of the TODO message on line 29
        compiler_cache.get_instance().topics.clear()

        # compile new test files
        # compile files with chat2cs
        new_compiled_modules, new_compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        new_compiled_topics = compiler_cache.get_instance().topics.items
        self.assertTrue(len(new_compiled_convos) < 1, msg="Did not expect to compile New Chat Conversation")

        # update Module Broker
        module_broker.update(new_compiled_modules, new_compiled_topics)

        # validate updated module names are in ModuleInfo
        for uuid, expected_name in update_module_name.items():
            # ensure module obj found for uuid
            mod_info = module_broker.get_info_by_uuid(uuid)
            self.assertFalse(mod_info is None, msg=f"Can't find Module Info for UUID ({uuid})")
            # validate module name is expected
            self.assertEqual(mod_info.module_name, expected_name, msg=f"Updated Module Name ({mod_info.module_name}) does not match Expected Name ({expected_name})")

    def test_broker_reference(self):
        """
        Tests ModuleBroker reference in Chat System Documents is preserved after getting written and loaded from the cache
        """

        # Riely 4/29/22 TODO: Update this test with actual SystemDocument obj when its ready

        new_compiled_modules, new_compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(new_compiled_convos) < 1, msg="Did not expect to compile New Chat Conversation")

        initial_chat_systems = compiler_cache.get_instance().compiled_systems.items
        initial_module_broker = compiler_cache.get_instance().compiled_systems.broker

        # validate inital pre-cache reference
        for chat_system in initial_chat_systems:
            self.assertEqual(id(chat_system.module_broker), id(initial_module_broker))

        # update module files
        unit_test_utils.copy_test_files(self._UPDATE_FILES_DIR, self._UNITTEST_DIR_NAME, recursive=False)
        # update cache
        new_compiled_modules, new_compiled_convos = unit_test_utils.compile_chat_files(self._UPDATE_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(new_compiled_convos) < 1, msg="Did not expect to compile New Chat Conversation")

        compiler_cache.get_instance().write()

        # delete global instance of cache
        # Riely 4/29/22: this feels...super jank
        if compiler_cache._INSTANCE is not None:
            del compiler_cache._INSTANCE
        compiler_cache._INSTANCE = None

        # get updated cache from disk
        update_chat_systems = compiler_cache.get_instance(from_cache=True).compiled_systems.items
        update_module_broker = compiler_cache.get_instance(from_cache=True).compiled_systems.broker

        # validate its a new object from the compiler cache
        self.assertNotEqual(id(initial_module_broker), id(update_module_broker), msg=f"Did not Expect Inital Module Broker to have same obj ID as Updated Cache")

        # ensure updated system cache
        for updated_chat_system in update_chat_systems:
            self.assertEqual(id(updated_chat_system.module_broker), id(update_module_broker))
    
    def test_broker_in_chat2cs(self):
        """
        validate ModuleBroker works properly in Chat2cs
        """

        # init expected test outcomes
        initial_module_name: Dict[str, str] = {
            "237BA5E3-416B-4102-9CB0-EFA8486F3E4D" : "Unit Test Module Broker 1",
            "7A738882-63E1-4404-87F8-686B26F13669" : "Unit Test Module Broker 2",
            "891A45AC-AFE0-4A3E-BB5C-73E5E86480BD" : "Unit Test module broker 3"
        }
        # init expected test outcomes
        update_module_name: Dict[str, str] = {
            "237BA5E3-416B-4102-9CB0-EFA8486F3E4D" : "Unit Test Module Broker 1",
            "7A738882-63E1-4404-87F8-686B26F13669" : "this is an update! to the second Unit Test Module File!",
            "891A45AC-AFE0-4A3E-BB5C-73E5E86480BD" : "Update Unit 3 test!"
        }

        # validate no module broker in cache at the start of the test
        null_module_broker = compiler_cache.get_instance().compiled_systems.broker
        self.assertIsNone(null_module_broker, msg="Empty Compiler Cache should not return a ModuleBroker obj")

        # compile module files
        new_compiled_modules, new_compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(new_compiled_convos) < 1, msg="Did not expect to compile inital Chat Conversation")

        # validate no module broker in cache at the start of the test
        inital_module_broker = compiler_cache.get_instance().compiled_systems.broker

        # validate initial module names
        for uuid, expected_name in initial_module_name.items():
            # ensure module obj found for uuid
            mod_info = inital_module_broker.get_info_by_uuid(uuid)
            self.assertFalse(mod_info is None, msg=f"Can't find Module Info for UUID ({uuid})")
            # validate module name is expected
            self.assertEqual(mod_info.module_name, expected_name, msg=f"Initial Module Name ({mod_info.module_name}) does not match Expected Name ({expected_name})")

        # update module files
        unit_test_utils.copy_test_files(self._UPDATE_FILES_DIR, self._UNITTEST_DIR_NAME, recursive=False)

        # remove all added topic files from cache before compiling chat files again
        # NOTE: this feels hacky and is the direct result of the TODO message on line 29
        compiler_cache.get_instance().topics.clear()

        # compile new test files
        # compile files with chat2cs
        new_compiled_modules, new_compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(new_compiled_convos) < 1, msg="Did not expect to compile New Chat Conversation")

        # get updated broker from cache
        updated_cached_broker = compiler_cache.get_instance().compiled_systems.broker

        # validate that the same ModuleBroker is getting updated when using compile_modules
        self.assertEqual(
            id(inital_module_broker),
            id(updated_cached_broker),
            msg="Expected Module Broker obj to be identical after compiling updated modules"
            )

        # validate updated module names are in ModuleInfo
        for uuid, expected_name in update_module_name.items():
            # ensure module obj found for uuid
            mod_info = updated_cached_broker.get_info_by_uuid(uuid)
            self.assertFalse(mod_info is None, msg=f"Can't find Module Info for UUID ({uuid})")
            # validate module name is expected
            self.assertEqual(mod_info.module_name, expected_name, msg=f"Updated Module Name ({mod_info.module_name}) does not match Expected Name ({expected_name})")
        
        # validate module broker is constructed if no broker in cache
        # clear cache
        compiler_cache.get_instance().clear()
        # re-copy test files
        unit_test_utils.copy_test_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME, recursive=False)
        # ensure no module broker in cache
        new_null_module_broker = compiler_cache.get_instance().compiled_systems.broker
        self.assertIsNone(new_null_module_broker, msg="Empty Compiler Cache should not return a ModuleBroker obj")
        # remove all added topic files from cache before compiling chat files again
        # NOTE: this feels hacky and is the direct result of the TODO message on line 29
        compiler_cache.get_instance().topics.clear()
        # re-compile chat files
        unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        # get the new ModuleBroker from the cache
        new_module_broker: ModuleBroker = compiler_cache.get_instance().compiled_systems.broker
        # validate new module broker is created
        self.assertIsNotNone(new_module_broker, msg="New Module Broker obj should not be None")
        # validate the new module broker is properly constructed
        for uuid, expected_name in initial_module_name.items():
            # ensure module obj found for uuid
            mod_info = new_module_broker.get_info_by_uuid(uuid)
            self.assertFalse(mod_info is None, msg=f"Can't find Module Info for UUID ({uuid})")
            # validate module name is expected
            self.assertEqual(mod_info.module_name, expected_name, msg=f"Initial Module Name ({mod_info.module_name}) does not match Expected Name ({expected_name})")
        # validate this is a different module broker than earlier
        self.assertNotEqual(
            id(new_module_broker),
            id(updated_cached_broker),
            msg="Module Broker should be re-built fresh after clearing the Module Cache"
        )

        # validate module broker is re-built if its version is out of date
        # validate module broker is currently up to date
        self.assertTrue(new_module_broker.object_up_to_date, msg="Current Module Broker obj should have been up to date")
        # set the broker's version to something out of date
        # Riely 5/2/22: version will newver be less than 1, so this will always work
        new_module_broker._object_version = -1
        # validate version is now out of date
        self.assertFalse(new_module_broker.object_up_to_date, msg="Module Object Version should be out of date after being set explicitly so")
        # remove all added topic files from cache before compiling chat files again
        # NOTE: this feels hacky and is the direct result of the TODO message on line 29
        compiler_cache.get_instance().topics.clear()
        # re-compile module files to ensure up to date ModuleBroker constructed
        unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        # get a new ModuleBroker
        up_to_date_broker: ModuleBroker = compiler_cache.get_instance().compiled_systems.broker
        # validate this new broker is up to date
        self.assertTrue(up_to_date_broker.object_up_to_date, msg=f"Up to Date Broker is NOT up to date. current version ({up_to_date_broker.version}), expected version ({up_to_date_broker.LATEST_VERSION})")
        # validate this is a new broker obj
        self.assertNotEqual(
            id(up_to_date_broker),
            id(new_module_broker),
            msg="Expected a New Module Broker obj to repair out of date object"
        )

    def test_entry_patterns(self):
        """
        validate that module entries and their patterns work properly
        """

        expected_patterns_1 = [
            "(default entry)",
            "(content entry)",
            "(custom entry)"
        ]
        expected_patterns_2 = [
            "(required 2)"
        ]
        expected_patterns_3 = []

        expected_default_entries = 1
        expected_content_id_entries = 1

        # compile files with chat2cs
        compiled_modules, compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(compiled_convos) < 1, msg="Did not expect to compile Chat Conversation")

        # get module broker
        module_broker: ModuleBroker = compiler_cache.get_instance().compiled_systems.broker

        # validate entry lines in proper Info objects
        mod_info1 = module_broker.get_info_by_uuid(self._MOD_1_UUID)
        mod_info2 = module_broker.get_info_by_uuid(self._MOD_2_UUID)
        mod_info3 = module_broker.get_info_by_uuid(self._MOD_3_UUID)

        self.assertEqual(
            len(mod_info1.default_entries),
            expected_default_entries,
            msg=f"Test Module 1 should have exactly 1 Default Entry, not {len(mod_info1.default_entries)}"
        )
        self.assertEqual(
            len(mod_info1.content_id_entries),
            expected_content_id_entries,
            msg=f"Test Module 1 should have exactly 1 Content ID Entry, not {len(mod_info1.content_id_entries)}"
        )

        self.assertEqual(
            len(mod_info1.global_entries),
            len(expected_patterns_1),
            msg=f"Test Module 1 should have exactly 3 Entry Patterns, not {len(mod_info1.global_entries)}"
        )
        self.assertEqual(
            len(mod_info2.global_entries),
            len(expected_patterns_2),
            msg=f"Test Module 2 should have exactly 1 Entry Pattern, not {len(mod_info2.global_entries)}"
        )
        self.assertEqual(
            len(mod_info3.global_entries),
            len(expected_patterns_3),
            msg=f"Test Module 3 should not have ANY Entry Patterns, but instead found {len(mod_info3.global_entries)}"
        )

        # validate patterns are expected
        # test 1
        for expected1 in expected_patterns_1:
            pattern_in_module1: bool = False
            # look for the pattern in all entry points
            for entry in mod_info1.global_entries:
                if entry.pattern == expected1:
                    pattern_in_module1 = True
            # validate the pattern is in it
            self.assertTrue(pattern_in_module1, msg=f"Expected Pattern '{expected1}' not found in Module 1 Entries")

        # test 2
        for expected2 in expected_patterns_2:
            pattern_in_module2: bool = False
            # look for the pattern in all entry points
            for entry in mod_info2.global_entries:
                if entry.pattern == expected2:
                    pattern_in_module2 = True
            # validate the pattern is in it
            self.assertTrue(pattern_in_module2, msg=f"Expected Pattern '{expected2}' not found in Module 2 Entries")

    def test_mod_info_tags(self):
        """
        validate all the SEL & Content Tags in a module (and their related conversation files) are properly extracted into the ModuleInfo object
        """
        expected_sel_tags = [
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "F71135BA-2F41-4745-B861-10842034B2DD",
                "BEC43B59-FE09-4C5D-B151-F9927329D155"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "CA1A58EC-DAA7-45E8-BE54-C9D0DDAA615D",
                "EEA77A5B-3CB7-4D09-A194-E05EF1FDFD98"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "7448EF41-3B53-4B4A-A729-FBA889884A89",
                "EEA77A5B-3CB7-4D09-A194-E05EF1FDFD98"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "CA1A58EC-DAA7-45E8-BE54-C9D0DDAA615D",
                "F0578F69-1B66-4D91-BCCB-6C535094E2AF"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "7448EF41-3B53-4B4A-A729-FBA889884A89",
                "F0578F69-1B66-4D91-BCCB-6C535094E2AF"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "BD96D681-B6F7-45C6-8892-B32DEA36C0EE",
                "F51438F3-9B2B-4B4A-B21B-726744E6AC4A"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "1C4DB0FC-8207-4EB1-8FAA-829205D826D6",
                "F51438F3-9B2B-4B4A-B21B-726744E6AC4A"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "7448EF41-3B53-4B4A-A729-FBA889884A89",
                "F51438F3-9B2B-4B4A-B21B-726744E6AC4A"
            ),
            SelTag(
                "59620927-8540-4423-9480-4C650B139DEE",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "F51438F3-9B2B-4B4A-B21B-726744E6AC4A"
            ),
            SelTag(
                "sel",
                "tag",
                "1A1BAEEB-2B81-41CA-8A87-A41D6158CB47"
            ),
            SelTag(
                "30773773-734E-447E-A9CE-EED98AA755EA",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "D29FD90D-9D97-444A-B2FD-45763FD5B2CC"
            ),
            SelTag(
                "97491439-3616-4560-8A24-4BF385661120",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "D29FD90D-9D97-444A-B2FD-45763FD5B2CC"
            ),
            SelTag(
                "30773773-734E-447E-A9CE-EED98AA755EA",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "16464B46-02BD-459A-A86B-E69C362AAA37"
            ),
            SelTag(
                "97491439-3616-4560-8A24-4BF385661120",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "16464B46-02BD-459A-A86B-E69C362AAA37"
            ),
            SelTag(
                "30773773-734E-447E-A9CE-EED98AA755EA",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "60F8E32E-A03C-4938-9DD6-66F1E5466273"
            ),
            SelTag(
                "97491439-3616-4560-8A24-4BF385661120",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "60F8E32E-A03C-4938-9DD6-66F1E5466273"
            ),
            SelTag(
                "30773773-734E-447E-A9CE-EED98AA755EA",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "110704EA-324A-4AB5-A55C-29AEF41D9E8E"
            ),
            SelTag(
                "97491439-3616-4560-8A24-4BF385661120",
                "50C0DCB7-F551-4DE0-8641-7518E20CD159",
                "110704EA-324A-4AB5-A55C-29AEF41D9E8E"
            )
        ]

        expected_content_tags = [
            ContentTag(
                "content tag",
                "1A1BAEEB-2B81-41CA-8A87-A41D6158CB47"
            ),
            ContentTag(
                "85A2368D-CB62-4F34-A1A2-F8734467C3B7",
                "D29FD90D-9D97-444A-B2FD-45763FD5B2CC"
            ),
            ContentTag(
                "5688BCE5-2A9D-49AB-A24A-B3004723D314",
                "D29FD90D-9D97-444A-B2FD-45763FD5B2CC"
            ),
            ContentTag(
                "0795E59C-E82C-4CED-86E7-1B8564DAE425",
                "D29FD90D-9D97-444A-B2FD-45763FD5B2CC"
            ),
            ContentTag(
                "85A2368D-CB62-4F34-A1A2-F8734467C3B7",
                "16464B46-02BD-459A-A86B-E69C362AAA37"
            ),
            ContentTag(
                "5688BCE5-2A9D-49AB-A24A-B3004723D314",
                "16464B46-02BD-459A-A86B-E69C362AAA37"
            ),
            ContentTag(
                "0795E59C-E82C-4CED-86E7-1B8564DAE425",
                "16464B46-02BD-459A-A86B-E69C362AAA37"
            )
        ]

        # compile files with chat2cs
        compiled_modules, compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(compiled_convos) < 1, msg="Did not expect to compile Chat Conversation")

        # validate no module broker in cache at the start of the test
        module_broker: ModuleBroker = compiler_cache.get_instance().compiled_systems.broker

        # get the test module's Info
        module_info = module_broker.get_info_by_uuid(self._MOD_1_UUID)

        # validate expected sel & content tags are in the module
        self.assertEqual(
            len(module_info.sel_tags),
            len(expected_sel_tags),
            msg=f"The number SelTags in Module Info should be the same as the number of sel tags in all elements in all boards.  Expected: ({len(expected_sel_tags)}), recieved({len(module_info.sel_tags)})"
        )
        self.assertEqual(
            len(module_info.content_tags),
            len(expected_content_tags),
            msg=f"The number ContentTags in Module Info should be the same as the number of content tags in all elements in all boards.  Expected: ({len(expected_content_tags)}), recieved({len(module_info.content_tags)})"
        )

        # validate the sel & content tags were properly extracted
        for expected_sel_tag in expected_sel_tags:
            # search for expected tag inside ModuleInfo
            sel_tag_found = False
            if expected_sel_tag in module_info.sel_tags:
                sel_tag_found = True
            self.assertTrue(sel_tag_found, msg=f"Expected SelTag {expected_sel_tag.__dict__} not found in ModuleInfo.sel_tags")

        for expected_content_tag in expected_content_tags:
            # search for expected tag inside ModuleInfo
            content_tag_found = False
            if expected_content_tag in module_info.content_tags:
                content_tag_found = True
            self.assertTrue(content_tag_found, msg=f"Expected ContentTag {expected_content_tag.__dict__} not found in ModuleInfo.content_tags")

    def test_mod_info_fallback_context(self):
        """
        validate all the fallback contexts in a module (and their related conversation files) are properly extracted into the ModuleInfo object
        """
        expected_fallback_contexts = [
            # TODO: uncomment or remove this once CONVERSATION fallback types have been finialized - Juan 3.22.23
            # {
            #     '_topic_name': 'MODBROKER1_Board_1_Polar_Node',
            #     '_fallback_type': 'CONVERSATION',
            #     '_fallback_text': 'local test context.'
            # },
            {
                '_topic_name': 'MODBROKER1_Start_Intro',
                '_fallback_type': 'DEFAULT',
                '_fallback_text': 'more local context.'
            }
        ]

        expected_module_context = "global test context."

        # compile files with chat2cs
        compiled_modules, compiled_convos = unit_test_utils.compile_chat_files(self._TEST_FILES_DIR, self._UNITTEST_DIR_NAME)
        self.assertTrue(len(compiled_convos) < 1, msg="Did not expect to compile Chat Conversation")

        # validate no module broker in cache at the start of the test
        module_broker: ModuleBroker = compiler_cache.get_instance().compiled_systems.broker

        # get the test module's Info
        module_info = module_broker.get_info_by_uuid(self._MOD_1_UUID)

        # validate expected fallback contexts are in the module
        self.assertEqual(
            module_info.module_context,
            expected_module_context,
            msg=f"Expected module context to be: '{expected_module_context}', recieved: '{module_info.module_context}'"
        )
        self.assertEqual(
            len(module_info.fallback_contexts),
            len(expected_fallback_contexts),
            msg=f"The number of fallback contexts in Module Info should be the same as the number of fallback contexts in all elements in all boards.  Expected: ({len(expected_fallback_contexts)}), recieved({len(module_info.fallback_contexts)})"
        )

        for expected_fallback_context in expected_fallback_contexts:
            # search for expected fallback context inside ModuleInfo
            fallback_context_found = False
            for fallback_context in module_info.fallback_contexts:
                # If all the value-pairs in the expected fallback context are found
                # in one of the ModuleInfo's fallback contexts, then we've found it 
                if all((getattr(fallback_context, k, "") == v for k, v in expected_fallback_context.items())):
                    fallback_context_found = True
                    break
            self.assertTrue(fallback_context_found, msg=f"Expected Fallback Context {expected_fallback_context} not found in ModuleInfo.fallback_contexts")
