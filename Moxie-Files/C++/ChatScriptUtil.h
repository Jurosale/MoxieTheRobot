#ifndef CHATSCRIPT_UTIL_H_
#define CHATSCRIPT_UTIL_H_

#include <string>

namespace embodied
{
namespace robotbrain
{
struct ChatScriptUtil
{
	/**
	 * @brief Retrieves the current chatscript topic location given a list of traversed topics and the current chatscript module
	 * More specifically, grabs the last chat topic in the list with the same module ID as the given chat module (if one exists)
	 * to both better simulate chatscript's topic location logic and better handle old, system and nostay chat topic edge cases
	 * @param chat_module - module ID text of the desired chatscript module
	 * @param chat_topics - text of all the desired chatscript topics
	 * @param trim_lead_tilde - if true, removes any leading tilde from final result; else does nothing
	 * @return resulting string (may be empty)
	 */
	static std::string GetChatTopic(const std::string& chat_module, const std::string& chat_topics, bool trim_lead_tilde = false);

	/**
	 * @brief Trims leading/trailing whitespaces and removes leading tilde if desired
	 * @param chat_name - text name of the chatscript object
	 * @param trim_lead_tilde - if true, removes any leading tilde from final result; else does nothing
	 * @return resulting string
	 */
	static std::string FormatChatName(const std::string& chat_name, bool trim_lead_tilde = false);

	/**
	 * @brief Retrieves the module ID from the given chatscript topic
	 * @param chat_topic - text name of the chatscript topic
	 * @param trim_lead_tilde - if true, removes any leading tilde from final result; else does nothing
	 * @return resulting string
	 */
	static std::string GetModuleID(const std::string& chat_topic, bool trim_lead_tilde = false);
};
}
}

#endif // CHATSCRIPT_UTIL_H_