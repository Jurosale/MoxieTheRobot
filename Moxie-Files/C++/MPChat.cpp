// README: Co-developed with another teammate. Works in conjuction
// with "FallbackHandlers" files to determine behavior from
// off-topic user input (i.e. "fallbacks")

#define TAG "MPChat"
#include <bo-core/Logging.h>

#include <bo-core/DeviceSettings.h>

#include <robotbrain2/RemoteEngine.h>
#include <robotbrain2/content_modules/FallbackHandlers.h>
#include <robotbrain2/content_modules/MPChat.h>
#include <robotbrain2/data/LineDB.h>
#include <robotbrain2/utils/ChatScriptUtil.h>

#include <bo-core/TextUtilities.h>

#include <google/protobuf/util/json_util.h>

namespace embodied
{
namespace robotbrain
{

#define RC_USE_DEFAULT_CONTEXT core::DeviceSettings::Instance()->getBoolS(core::SettingSchema::USE_DEFAULT_FALLBACK_CONTEXT)

MPChatModule::MPChatModule(BrainData& data,
                           MissionControl& mission_control)
    : QueuedModule(data),
      mission_control_(mission_control)
{
    FallbackHandler::CreateFallbackHandlers(fallback_handlers_, mission_control, data);
}

FunctionResult MPChatModule::HandleFallback(std::string& ret)
{
    LOG_INFO << "inside the fallback handler";
    if (!UseNewFallbackHandler()) // short circuit the fallback handler
    {
        LOG_INFO << "using the old fallback handler";
        ret.clear();
        return NOPROBLEM_BIT;
    }
    else if (!current_fallback_handler_)
    {
        LOG_ERROR << "no fallback handler set, using the old-school chatscript one";
        ret.clear();
        return NOPROBLEM_BIT;
    }

    LOG_INFO << "using the new fallback handler";
    LOG_INFO << "using fallback handler: " << current_fallback_handler_->Name();
    if (!current_fallback_handler_->HandleFallback())
    {
        LOG_WARNING << "fallback handler: " << current_fallback_handler_->Name() << " did not handle the volley";
        std::string unused;
        mission_control_.SetOutputType(OutputType::FALLBACK); 
        mission_control_.AddOutput(LineDB::DB().GetTextExhaustive(LineDB::FALLBACKS_REPEAT));
        mission_control_.CallFunction("^fallbacks_keepCounter", unused);
    }
    ret = "handled"; // just so CS stops processing fallbacks see $_handled in bo-control.top
    return NOPROBLEM_BIT;
}

FunctionResult MPChatModule::KeepCounter(std::string& ret)
{
    if (!current_fallback_handler_) return FAILRULE_BIT;
    LOG_INFO << "keeping the counter because cs requested it";
    current_fallback_handler_->KeepCounter();
    return NOPROBLEM_BIT;
}

FunctionResult MPChatModule::ResetCounter(std::string& ret)
{
    if (!current_fallback_handler_) return FAILRULE_BIT;
    LOG_INFO << "resetting the counter because cs requested it";
    current_fallback_handler_->ResetCounter();
    return NOPROBLEM_BIT;
}

FunctionResult MPChatModule::RestoreCounter(std::string& ret)
{
    if (!current_fallback_handler_) return FAILRULE_BIT;
    LOG_INFO << "restoring the counter because cs requested it";
    current_fallback_handler_->RestoreCounter();
    return NOPROBLEM_BIT;
}

FunctionResult MPChatModule::GetCounter(std::string& ret)
{
    if (!current_fallback_handler_) return FAILRULE_BIT;
    ret = std::to_string(current_fallback_handler_->FallbackCounter());
    return NOPROBLEM_BIT;
}

FunctionResult MPChatModule::GetSpeechInput(std::string& ret)
{
    if (!current_fallback_handler_) return FAILRULE_BIT;
    ret = current_fallback_handler_->SpeechInput();
    return NOPROBLEM_BIT;
}

FunctionResult MPChatModule::ResetAllCounters(std::string& ret)
{
    LOG_INFO << "resetting all handler counters because cs requested it";
    for (auto& handler : fallback_handlers_)
    {
        handler->ResetCounter();
    }
    return NOPROBLEM_BIT;
}

void MPChatModule::OnChatVolleyStarted(Volley& volley) 
{
    // reset to default every volley
    if (!UseNewFallbackHandler())
        return;
    
    if (!volley.Input())
    {
        LOG_ERROR << "empty input in volley, aborting MPChat OnChatVolleyStarted";
        return;
    }

    current_fallback_handler_ = nullptr;

    BrainContent& brain_content = GetBrainData().Content();
    const auto& node_fallback = brain_content.GetModuleInfo(prev_chat_module_).GetNodeFallback(prev_chat_topic_);
    for (auto& handler : fallback_handlers_)
    {
        if (handler->HandlesThisVolley(volley, CurrentRobotState(), prev_chat_module_, node_fallback))
        {
            current_fallback_handler_ = handler;
            break;
        }
    }

    if (current_fallback_handler_ == nullptr)
    {
        LOG_WARNING << "none of the fallback handlers will handle this volley?";
        return;
    }

    current_fallback_handler_->OnChatVolleyStarted(volley, prev_chat_module_, prev_content_id_, prev_chat_topic_);
}

void MPChatModule::OnRemoteVolleyAccepted(Volley& volley) 
{

    // update the module, topic and content id
    prev_chat_module_ = volley.Output()->Response().chat_module();
    auto prev_chat_topics = volley.Output()->Response().chat_topic();
    prev_chat_topic_ = FormatTopic(prev_chat_topic_, prev_chat_module_, prev_chat_topics);
    prev_content_id_ = volley.Output()->Response().chat_content_id();

    // call on chat volley finished
    current_fallback_handler_->OnChatVolleyFinished(volley);
}

void MPChatModule::OnRobotStateChanged(RobotState current, RobotState previous)
{
    if (current != RobotEngineState::Sleep && previous == RobotEngineState::Sleep)
    {   
        // moxie woke up
        LOG_INFO << "resetting because moxie woke up";
        for (auto& fbh : fallback_handlers_)
            fbh->ResetCounter();
    }
}

std::string MPChatModule::FormatTopic(std::string& chat_topic, const std::string& chat_module, const std::string& all_chat_topics)
{
    std::string ret;
    if (chat_module.empty())
    {
        LOG_ERROR << "Received empty CS module ID; cannot determine the last CS topic.";
    }
    else
    {
        auto last_chat_topic = ChatScriptUtil::GetChatTopic(chat_module, all_chat_topics, true);
        if(!last_chat_topic.empty())
        {
            ret = last_chat_topic;
            LOG_INFO << "last CS topic: " << last_chat_topic;
        }
        else
        {
            ret = chat_topic;
            LOG_INFO << "CS must be in the same topic it was before: " << chat_topic;
        }
    }
    return ret;
}

std::shared_ptr<ModuleRewindInfo> MPChatModule::OnChatVolleyFinished(Volley& volley) { OnRemoteVolleyAccepted(volley); return nullptr; }

void MPChatModule::OnChatVolleyAborted(Volley& volley) 
{
    if (current_fallback_handler_)
        current_fallback_handler_->OnChatVolleyAborted(volley);
}

void MPChatModule::OnRewindVolley(std::shared_ptr<ModuleRewindInfo> rewind_info) {}
bool MPChatModule::UseNewFallbackHandler() const { return core::DeviceSettings::Instance()->getBoolS(core::SettingSchema::ENABLE_MPCHAT_EVERYWHERE); }

}
}
