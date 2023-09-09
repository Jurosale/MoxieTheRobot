# README: contains helper functions for "topic_cache.py"

import logging
import os
from functools import partial
import pathlib
import pickle
import tqdm

from ..... import CACHE_SUB_DIR
from .... import globals

DOCS_ATTRIBUTE_NAME = "_docs"
INSTRUCTIONS_ATTRIBUTE_NAME = "_instructions"
VERSION_ATTRIBUTE_NAME = "_version"


def downgrade_v2_to_v1():
	"""
	Given a version 2 build, downgrade it to version 1 build by removing these attributes:
	An official version number and downgrade instructions
	"""
	# TODO: implement this specific downgrade
	raise NotImplementedError(f"No downgrade instructions available for version '{_topic_cache_file.version}'.")


def upgrade_v1_to_v2(_topic_cache_obj, _doc_data_files, _doc_topic_files, _additional_args=None):
	"""
	Given a version 1 build, upgrade it to version 2 build by adding these new attributes:
	An official version number and downgrade instructions

	**IMPORTANT NOTE: _topic_cache_obj must be a TopicCache object that we take in and return!**

	Args:
		_topic_cache_obj: the current TopicCache object
	    _doc_data_files: current number of loaded data files
	    _doc_topic_files: current number of loaded topic files
	    _additional_args: optional arguments needed for this specific upgrade
	"""
	_v2_instructions = [
		{ "version": 2, "func": downgrade_v2_to_v1, "extra_args": None },
		{ "version": 2, "func": load_v2, "extra_args": None }
	]

	setattr(_topic_cache_obj, VERSION_ATTRIBUTE_NAME, 2)
	setattr(_topic_cache_obj, INSTRUCTIONS_ATTRIBUTE_NAME, _v2_instructions)

	logging.info(f"Upgraded from v1 to v2. Updated '{VERSION_ATTRIBUTE_NAME}' attribute with value '{_topic_cache_obj.version}'. "
				 f"New '{INSTRUCTIONS_ATTRIBUTE_NAME}' attribute added with value '{_topic_cache_obj.instructions}'. "
				 f"Total data files loaded '{_doc_data_files}'. Total topic files loaded '{_doc_topic_files}'.")
	
	return _doc_data_files, _doc_topic_files


def load_v1(_topic_cache_obj, _topic_cache_file, _doc_data_files, _doc_topic_files):
	"""
	Given the single TopicCache file found in version 1 builds,
	Retrieves all its topic content found inside and store them inside TopicCache._docs

	**IMPORTANT NOTE: _topic_cache_obj must be a TopicCache object that we take in and return!**

	Args:
		_topic_cache_obj: the current TopicCache object
		_topic_cache_file: the current TopicCache file
	    _doc_data_files: current number of loaded data files
	    _doc_topic_files: current number of loaded topic files
	"""
	# We only need the list of docs here; _topic_cache_file also only contains a single entry                        
	for doc_key, doc_list in _topic_cache_file.items():
	    # Now add every topic and its topic object found in the list of docs inside TopicCache._docs
	    for doc_sub_cache in tqdm.tqdm(doc_list, ncols=100, desc=f"Loading new '{DOCS_ATTRIBUTE_NAME}' in topic sub caches", disable=globals.DISABLE_PROGRESS_BARS):
	        for doc_topic_name, doc_topic_object in doc_sub_cache.topics.items():
	            _topic_cache_obj.add(doc_topic_name, doc_sub_cache.board, doc_topic_object)
	            _doc_topic_files += 1

	# since add() (located a few lines above) already checks for board uniqueness and groups docs by boards,
	# data files will equal the number of total docs we added inside TopicCache._docs
	_doc_data_files = len(_topic_cache_obj._docs)

	return _doc_data_files, _doc_topic_files


def load_v2(_topic_cache_obj, _topic_cache_file, _doc_data_files, _doc_topic_files):
	"""
	Given the TopicCache_V2 directory found in version 2 builds, 
	Retrieves all its data & topics files and store them inside TopicCache._docs

	**IMPORTANT NOTE: _topic_cache_obj must be a TopicCache object that we take in and return!**

	Args:
		_topic_cache_obj: the current TopicCache object
		_topic_cache_file: the current TopicCache file
	    _doc_data_files: current number of loaded data files
	    _doc_topic_files: current number of loaded topic files
	"""
	# Grabs all the "data" sub directory files in topic cache only
	_topic_cache_dir_path = _topic_cache_obj.topic_cache_dir_path()
	p = pathlib.Path(_topic_cache_dir_path).glob('*/*')
	all_doc_subcaches = [x for x in p if x.is_file() and not x.name.startswith(".") and x.name.endswith("_data")]

	for doc_sub_cache in tqdm.tqdm(all_doc_subcaches, ncols=100, desc=f"Loading all '{DOCS_ATTRIBUTE_NAME}' in topic sub caches version '{_topic_cache_obj.version}'",
								   disable=globals.DISABLE_PROGRESS_BARS):
	    # First retrieve and load the info found inside each "data" file
	    data = bytearray()
	    with open(doc_sub_cache, "rb") as f:
	        for byte in iter(partial(f.read, 1024), b''):
	            data += bytearray(byte)
	        doc_sub_cache = pickle.loads(data)
	    _doc_data_files += 1

	    # Now we retreive and load each of the individual topic files containing single entry dicts
	    # The "topic_cache_dir_path()" of a TopicCache object combined with .doc_dir_path()" of a data file
	    # Returns the exact filepath of the folder containing its topics
	    doc_path_name = os.path.join(_topic_cache_dir_path, doc_sub_cache.doc_dir_path())
	    for topic_file in os.listdir(doc_path_name):
	        doc_topic_path = os.path.join(doc_path_name, topic_file)
	        topic_data = bytearray()
	        with open(doc_topic_path, "rb") as f:
	            for byte in iter(partial(f.read, 1024), b''):
	                topic_data += bytearray(byte)
	            topic_file = pickle.loads(topic_data)
	        _doc_topic_files += 1

	        # Append this retrieved topic file info into its respective "data" file object
	        for topic_name in topic_file.keys():
	            topic_obj = topic_file[topic_name]
	            doc_sub_cache.topics[topic_name] = topic_obj

	    _topic_cache_obj._docs.append(doc_sub_cache)

	return _doc_data_files, _doc_topic_files
