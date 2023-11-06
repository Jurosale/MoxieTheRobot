// README: Simple Utilities file to help retrieve a topic name
// given a list of ChatScript topics

#include <string>

#include <bo-core/TextUtilities.h>
#include <robotbrain2/utils/ChatScriptUtil.h>

namespace embodied
{
namespace robotbrain
{

std::string ChatScriptUtil::GetChatTopic(const std::string& chat_module, const std::string& chat_topics, bool trim_lead_tilde)
{
	std::string curr_topic;

	if (chat_module.empty() || chat_topics.empty())
		return curr_topic;

	auto formatted_chat_module = tolower(FormatChatName(chat_module, true));

	auto topics_list = split(chat_topics, ',');
	for (auto chat_topic: topics_list)
	{
		chat_topic = chat_topic.substr(0, chat_topic.find('.'));
		auto formatted_topic_module_id = tolower(GetModuleID(chat_topic, true));

		if(formatted_topic_module_id == formatted_chat_module)
			curr_topic = FormatChatName(chat_topic, trim_lead_tilde);
	}

	return curr_topic;
}

std::string ChatScriptUtil::FormatChatName(const std::string& chat_name, bool trim_lead_tilde)
{
	if (chat_name.empty())
		return chat_name;

	auto formatted_name = chat_name;
	trim(formatted_name);
	if (trim_lead_tilde && StringStartsWith(formatted_name, "~"))
		formatted_name.erase(0, 1);
	return formatted_name;
}

std::string ChatScriptUtil::GetModuleID(const std::string& chat_topic, bool trim_lead_tilde)
{
	return FormatChatName(chat_topic.substr(0, chat_topic.find('_')), trim_lead_tilde);
}

}
}
