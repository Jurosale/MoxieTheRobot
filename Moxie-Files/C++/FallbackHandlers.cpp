// README: Co-developed with another teammate. Works in conjuction
// with "MPChat" files to determine behavior from off-topic user
// input (i.e. "fallbacks")

#define TAG "FallbackHandlers"
#include <bo-core/Logging.h>
#include <bo-core/DeviceSettings.h>

#include <robotbrain2/RemoteEngine.h>
#include <robotbrain2/content_modules/FallbackHandlers.h>
#include <robotbrain2/data/LineDB.h>

namespace embodied
{
namespace robotbrain
{

using RBSpeak = EventInput<RemoteActions::RBSpeak>;

void FallbackHandler::KeepCounter() {}
void FallbackHandler::ResetCounter() {}
void FallbackHandler::RestoreCounter() {}
void FallbackHandler::OnChatVolleyStarted(Volley& volley,
                                         const std::string& module_id,
                                         const std::string& content_id,
                                         const std::string& topic_id)  {} //, const serialized::NodeFallback& node) {}
void FallbackHandler::OnChatVolleyFinished(Volley& volley) {} //, const serialized::NodeFallback& node) {}
void FallbackHandler::OnChatVolleyAborted(Volley& volley) {} //, const serialized::NodeFallback& node) {}
int FallbackHandler::FallbackCounter() const { return 0; }
std::string FallbackHandler::SpeechInput() const { return ""; }

/** @brief method for creating the fallback handlers 
 *
 * Important! These are in order... the event should be above silent, and default should be last
 */
void FallbackHandler::CreateFallbackHandlers(std::list<std::shared_ptr<FallbackHandler>>& handlers,
                                             MissionControl& mission_control,
                                             BrainData& data)
{
    handlers.clear();
    handlers.push_back(std::make_shared<EventFallbackHandler>(mission_control));
    handlers.push_back(std::make_shared<SilentFallbackHandler>(mission_control));
    handlers.push_back(std::make_shared<ConversationFallbackHandler>(data, mission_control));
    handlers.push_back(std::make_shared<SocialXFallbackHandler>(mission_control));
    handlers.push_back(std::make_shared<DefaultFallbackHandler>(data, mission_control));
}


bool SilentFallbackHandler::HandlesThisVolley(Volley& volley, 
                                              RobotState state,
                                              const std::string& module_id,
                                              const serialized::NodeFallback& node)
{
    return state.IsInterruptible() || node.opt() == serialized::NodeFallback_FallbackOptions_SILENT;
}

bool SilentFallbackHandler::HandleFallback()
{
    std::string unused;
    mission_control_.SetVariable("$$State_noPrelude", true);
    mission_control_.CallFunction("^keepRejoinder", unused);
    mission_control_.CallFunction("^noRepeat", unused);
    mission_control_.SetOutputType(OutputType::EMPTY);
    mission_control_.CallFunction("^fallbacks_keepCounter", unused);
    return true;
}

const char* SilentFallbackHandler::Name() const { return "SILENT"; }

#undef TAG
#define TAG "EventFallbackHandler"

bool EventFallbackHandler::HandlesThisVolley(Volley& volley, 
                                              RobotState state,
                                              const std::string& module_id,
                                              const serialized::NodeFallback& node)
{
    // so if RBSpeak is an interrupting event... it won't come back as RBSpeak
    return volley.Input()->IsEvent() && !volley.IsInputType<RBSpeak>();
}

bool EventFallbackHandler::HandleFallback() 
{
    std::string unused;
    mission_control_.CallFunction("^keepRejoinder", unused);
    mission_control_.CallFunction("^fallbacks_keepCounter", unused);
    return true;
}

const char* EventFallbackHandler::Name() const { return "EVENT"; }

bool ContextIsEmpty(const Context& context)
{
    return context.id().empty() && context.text().empty();
}



void FallbackHandlerWithContext::UpdateRemoteContext(Volley& volley,
                                                     const std::string& module_id,
                                                     const std::string& content_id,
                                                     const std::string& topic_id)
{
    auto& remote_request = volley.RemoteRequest();
    Context* remote_conversation_context = remote_request.mutable_conversation_context();
    if (!ContextIsEmpty(*remote_conversation_context))
        return;

    auto module  = data_.Content().GetModuleInfo(module_id);
    const auto& mcontext = module.GetModuleFallbackContext();
    const auto& content  = module.GetContentIdFallbackContext(content_id);
    const auto& node     = module.GetNodeFallback(topic_id);
    const auto& dfault   = data_.Content().GetDefaultFallbackContext();

    remote_request.set_allow_multiple(true);
    if (!ContextIsEmpty(node.context()))
        remote_conversation_context->CopyFrom(node.context());
    else if (!ContextIsEmpty(content))
        remote_conversation_context->CopyFrom(content);
    else if (!ContextIsEmpty(mcontext))
        remote_conversation_context->CopyFrom(mcontext);
    else
        remote_conversation_context->CopyFrom(dfault);
    if (ContextIsEmpty(*remote_conversation_context))
    {
        LOG_WARNING << "No context set for node: " << topic_id << " in " << module_id << " remote chat fallbacks will be disabled";
    }
}

#undef TAG 
#define TAG "DefaultFallbackHandler"

bool DefaultFallbackHandler::HandlesThisVolley(Volley& volley,
                                               RobotState state,
                                               const std::string& module_id,
                                               const serialized::NodeFallback& node)
{
    // checks if the current node wants to utilize a remote response or not
    if(node.opt() == serialized::NodeFallback_FallbackOptions_FALLBACKS_NO_REMOTE)
        skip_remote_ = true;
    else
        skip_remote_ = false;

    LOG_INFO << "skipping remote response: " << (skip_remote_?"true":"false");
    return true; // this is the default
}

void DefaultFallbackHandler::ResetCounter()   
{ 
    LOG_INFO << "RESETTING THE COUNTER FROM OUTSIDE FB HANDLER";
    counter_ = 0; reset_counter_ = true; 
}
void DefaultFallbackHandler::KeepCounter()    { handled_this_volley_ = true; }
void DefaultFallbackHandler::RestoreCounter() { counter_ = MOVE_ON_THRESHOLD; }

bool DefaultFallbackHandler::DoInitialVolley()
{
    LOG_INFO << "inside the initial fallback volley";
    handled_this_volley_ = true;
    state_ = FallbackHandlerState::AFTER_INITIAL_VOLLEY;
    LOG_INFO << "getting the fallback rule";
    fallback_rule_.clear();
    mission_control_.GetVariable("$$fallback_rule", fallback_rule_);
    if (fallback_rule_.empty())
    {
        LOG_INFO << "fallback_rule doesn't exist for topic: " << topic_;
    }
    else
    {
        LOG_INFO << "fallback_rule for topic: " << topic_ << " is: " << fallback_rule_;
    }

    return false;
}

bool DefaultFallbackHandler::DoSecondVolley()
{
    LOG_INFO << "inside the second fallback volley. counter_ is " << counter_;
    mission_control_.SetFallbackType(FALLBACK_UNKNOWN);
    mission_control_.AddOutput(LineDB::DB().GetTextExhaustive(LineDB::ANIM_IDLE));
    if(CheckSignal())
    {
        LOG_INFO << "fallback handled by a signal";
        return true;  
    } 
    // use a local fallback no more than once if we specifically don't want to utilize a remote response
    else if ((!skip_remote_ || counter_ == 0) && DoLocalFallback())
    {
        LOG_INFO << "used the local fallback rule";
        mission_control_.SetFallbackType(FALLBACK_LOCAL_RULE);
        return true;
    } 
    else if (counter_ == 0)
    {
        LOG_INFO << "using the standard local fallback";
        mission_control_.SetFallbackType(FALLBACK_LOCAL_FALLBACK);
        return false; // let the outer HandleFallback do the work
    } 
    else if (counter_ % MOVE_ON_THRESHOLD == 0) 
    {
        if (DoMoveOn())
        {
            LOG_INFO << "using the move on";
            mission_control_.SetFallbackType(FALLBACK_MOVE_ON);
            skip_increment_ = true;
            return true;
        }
        else 
        {
            LOG_INFO << "move on failed, using the standard local fallback";
            return false;
        }
    }
    else if (counter_ % CHAT_THRESHOLD == 0)
    {
        if (DoConfirmation())
        {
            LOG_INFO << "using the confirmation rule";
            mission_control_.SetFallbackType(FALLBACK_CONFIRMATION);
            return true;    
        }
        else
        {
            return false;
        }
    }
    else if (DoClarification())
    {
        LOG_INFO << "using the clarification rule";
        mission_control_.SetFallbackType(CLARIFICATION);
        return true;  
    } 
    else if (DoReprompt())
    {
        LOG_INFO << "doing a reprompt";
        mission_control_.SetFallbackType(REPROMPT);
        return true;
    }
    LOG_INFO << "everything failed, using the standard local fallback";
    return false;
}

bool DefaultFallbackHandler::HandleInOneVolley()
{
    LOG_INFO << "performing both default fallbacks in 1 volley instead of 2";
    if(DoInitialVolley())
        return true;

    //correct initial volley flag/state changes
    handled_this_volley_ = false;
    state_ = FallbackHandlerState::SECOND_VOLLEY;

    // emulate function calls for eb-remote-act-speak CS rule since we skip it in this instance
    std::string unused;
    mission_control_.CallFunction("^keepRejoinder", unused);
    mission_control_.CallFunction("^fallbacks_keepCounter", unused);

    if(DoSecondVolley())
        return true;

    return false;
}

bool DefaultFallbackHandler::HandleFallback()
{
    std::string unused;
    mission_control_.SetOutputType(OutputType::FALLBACK);
    mission_control_.SetVariable("$$State_noPrelude", true);

    // if we don't need to create a remote response, handle default fallback in 1 volley
    if (skip_remote_)
    {
        if (HandleInOneVolley())
        {
            mission_control_.SetFallbackType(FALLBACK_NO_REMOTE);
            return true;
        }
    }
    // else handle it in 2 volleys to buy enough time to create a remote response
    else
    {
        if (state_ == FallbackHandlerState::INITIAL_VOLLEY && DoInitialVolley()) return true;
        else if (state_ == FallbackHandlerState::SECOND_VOLLEY && DoSecondVolley()) return true;
    }

    LOG_INFO << "Other handlers did not return a fallback, using the local fallback";
    // we made it here, so add the line and everything else
    // assign the fallback type based on whether or not a remote response was desired
    if (skip_remote_)
        mission_control_.SetFallbackType(FALLBACK_NO_REMOTE);
    else
        mission_control_.SetFallbackType(FALLBACK_LOCAL_FALLBACK);
    mission_control_.AddOutput(LineDB::DB().GetTextExhaustive(LineDB::FALLBACKS_REPEAT));
    mission_control_.CallFunction("^fallbacks_keepCounter", unused);
    return true;
}

bool DefaultFallbackHandler::DoLocalFallback()
{
    std::string fallback_rule;
    bool handled = false;
    if (!fallback_rule_.empty())
    {
        LOG_INFO << "using the local fallback rule: " << fallback_rule_;
        handled = mission_control_.ReuseRule(fallback_rule_);
        if (!handled) { LOG_INFO << "Reuse failed, not using " << fallback_rule_; }
        else { LOG_INFO << "successfully used fallback rule "  << fallback_rule_; }
    }
    return handled;
}

bool DefaultFallbackHandler::DoClarification() 
{
    // ^sendSignal("signal-clarification")
    // skipping setting the output type - i'm not sure it's really needed
    // ^doClarification
    if (mission_control_.SendSignal("signal-clarification"))
    {
        // how do we get the child to re-engage if they're hitting the fallback handler?
        // why is this set? may for remote response overrides
        std::string unused;
        return true;
    }
    return false;

}

bool DefaultFallbackHandler::DoReprompt() 
{
    std::string unused;
    return mission_control_.CallFunction("^markup_restore", unused) && mission_control_.CallFunction("^doReprompt", unused);
}

bool DefaultFallbackHandler::DoConfirmation()
{
    std::string unused;
    const static std::string GAMBIT_TANGENT_NAME = "~FALLBACK_SXC_fallbackOpenConvo_Intro";
    return mission_control_.CallFunction("^gambitTangent", unused, {GAMBIT_TANGENT_NAME});
}

bool DefaultFallbackHandler::DoMoveOn()
{
    std::string unused;
    return mission_control_.CallFunction("^doMoveOn", unused);
}

/// checks to see if the "$$signal" has been set, if so - return true. 
/// equivalent of `^end(CALL)` in chatscript
bool DefaultFallbackHandler::CheckSignal()
{
    std::string signal;
    if (mission_control_.GetVariable("$$signal", signal))
    {
        if (signal == "true")
        {
            LOG_DEBUG << "$$signal set, ending the call";
            return true;
        }
    }
    else
    {
        LOG_DEBUG << "could not get $$signal, does this make sense?";
    }
    return false;
}

bool DefaultFallbackHandler::ShouldIncrement(const Volley& volley)
{
    if (!volley.Output() || skip_increment_)
        return false;
    auto output_type = (*volley.Output())->output_type();   
    // if (volley.IsInputType<RBSpeak>() && (*volley.Output())->source() == REMOTE_RESPONSE)
    // {
    //     output_type = volley.RemoteResponse().response_action().output_type();  
    // }
    LOG_INFO << "output type is: " << OutputType_Name(output_type);
    bool ret = output_type == OutputType::FALLBACK || 
               output_type == OutputType::CONTEXTUAL_FALLBACK;
    return ret;
}

bool DefaultFallbackHandler::ShouldReset(const Volley& volley)
{
    if (!volley.Output())
        return false;
    auto output_type = (*volley.Output())->output_type();   
    if (handled_this_volley_) return false;
    if (reset_counter_) return true;

    return output_type != OutputType::EVENT_INPUT && 
           output_type != OutputType::GLOBAL_COMMAND && 
           output_type != OutputType::GLOBAL_RESPONSE; 
}

void DefaultFallbackHandler::OnChatVolleyStarted(Volley& volley,
                                                 const std::string& module,
                                                 const std::string& content_id,
                                                 const std::string& topic_id)
{
    module_ = module;
    topic_  = topic_id;

    handled_this_volley_ = false;
    reset_counter_ = false;
    skip_increment_ = false;
    starting_state_ = state_;

    if (state_ == FallbackHandlerState::SECOND_VOLLEY && !volley.IsInputType<RBSpeak>())
    {
        LOG_WARNING << "second volley encountered with an input that isn't RBSpeak. Resetting fallback handler";
        state_ = FallbackHandlerState::INITIAL_VOLLEY;
    }

    if (state_ == FallbackHandlerState::INITIAL_VOLLEY)
    {
        if (!skip_remote_)
        {
            LOG_INFO << "starting an initial fallback; setting up remote response";
            UpdateRemoteContext(volley, module, content_id, topic_id);
            // set the no gpt bias so it doesn't ask questions
            (*volley.RemoteRequest().mutable_settings()->mutable_props())[core::SettingSchema::NO_GPT_BIAS] = core::DeviceSettings::Instance()->TRUE_LITERAL;
            // set the language model to gpt-turbo
            (*volley.RemoteRequest().mutable_settings()->mutable_props())[core::SettingSchema::CHAT_GPT3_MODEL] = core::DeviceSettings::Instance()->getStringS(core::SettingSchema::FALLBACKS_GPT_MODEL);
        }
    }
    else
    {
        LOG_INFO << "setting up the second volley";
        auto event = volley.AsInputType<RBSpeak>();
        if (!event)
        {
            LOG_ERROR << "somewhere between the first check and this one... the type changed?";   
            state_ = FallbackHandlerState::INITIAL_VOLLEY;
        }
        else
        {
            LOG_INFO << "promoting the internal event to something better";
            event->PromoteInternalEvent();
        }
    }
}

void DefaultFallbackHandler::OnChatVolleyFinished(Volley& volley)
{
    LOG_INFO << "volley: " << volley.Input()->InputString();
    if (!volley.Output())
    {
        LOG_WARNING << "no output found in the volley!";
        return;
    }

    if (state_ == FallbackHandlerState::INITIAL_VOLLEY)
    {
        if (ShouldReset(volley))
        {
            LOG_INFO << "resetting the fallback counter";
            counter_ = 0;
        }
        else
        {
            LOG_INFO << "did not use the fallback handler, but not resetting the fallback counter";
        }
    }
    else if (state_ == FallbackHandlerState::AFTER_INITIAL_VOLLEY)
    {
        LOG_INFO << "handled the fallback initial volley, setting up for the subsequent volley";
        // this is set inside the initial_volley fallback handler
        state_ = FallbackHandlerState::SECOND_VOLLEY;
        // store user speech input incase we want to give cs access to it for local fallback purposes
        speech_input_ = volley.Input()->InputString();
    } 
    else if (state_ == FallbackHandlerState::SECOND_VOLLEY)
    {
        // if the state_ is the second volley, update the counter and set the state back to initial volley
        LOG_INFO << "handled the fallback second volley, incrementing counter and resetting the state";
 /**       if (!(*volley.Output())->response().empty())
        {
            // adding something to clear the thinking animation
            (*volley.Output())->mutable_response()->insert(0, LineDB::DB().GetText(LineDB::ANIM_IDLE));
        }
 **/
        if (ShouldIncrement(volley))
        {
            LOG_INFO << "incrementing the fallback counter";
            ++counter_;
        }
        else
        {
            LOG_INFO << "not incrementing the counter";
        }
        state_ = FallbackHandlerState::INITIAL_VOLLEY;
        speech_input_ = "";
    }
}

void DefaultFallbackHandler::OnChatVolleyAborted(Volley& volley)
{
    LOG_INFO << "volley was aborted; reverting back to starting fallback handler state";
    state_ = starting_state_;
}

const char* DefaultFallbackHandler::Name() const { return "DEFAULT"; }
int DefaultFallbackHandler::FallbackCounter() const { return counter_; }
std::string DefaultFallbackHandler::SpeechInput() const { return speech_input_; }

bool ConversationFallbackHandler::HandlesThisVolley(Volley& volley, 
                                                    RobotState state, 
                                                    const std::string& module_id, 
                                                    const serialized::NodeFallback& node)
{
    return module_id == "MOXIMUSPRIME" || node.opt() == serialized::NodeFallback_FallbackOptions_CONVERSATION;
}

void ConversationFallbackHandler::OnChatVolleyStarted(Volley& volley,
                                     const std::string& module,
                                     const std::string& content_id,
                                     const std::string& topic_id)
{
    auto& remote_request = volley.RemoteRequest();
    LOG_INFO << "Conversation Handler in effect!  Request allow_multiple this volley.";
    remote_request.set_allow_multiple(true);
}

bool ConversationFallbackHandler::HandleFallback()
{
    // always use a remote response if it's available
    mission_control_.SetOutputType(OutputType::FALLBACK);
    mission_control_.SetFallbackType(FALLBACK_USE_REMOTE);
    mission_control_.AddOutput(LineDB::DB().GetTextExhaustive(LineDB::FALLBACKS_REPEAT));
    return true;
}

const char* ConversationFallbackHandler::Name() const { return "CONVERSATION"; }

const char* SocialXFallbackHandler::Name() const { return "SOCIALX"; }
bool SocialXFallbackHandler::HandlesThisVolley(Volley& volley, 
                                                    RobotState state, 
                                                    const std::string& module_id, 
                                                    const serialized::NodeFallback& node)
{
    return volley.SocialXEnabled() || node.opt() == serialized::NodeFallback_FallbackOptions_LOCAL_ONLY;
}


bool SocialXFallbackHandler::DoLocalFallback()
{
    std::string fallback_rule;
    mission_control_.GetVariable("$$fallback_rule", fallback_rule);
    bool handled = false;
    if (!fallback_rule.empty())
    {
        LOG_INFO << "using the local fallback rule: " << fallback_rule;
        handled = mission_control_.ReuseRule(fallback_rule);
        if (!handled) { LOG_INFO << "Reuse failed, not using " << fallback_rule; }
        else { LOG_INFO << "successfully used fallback rule "  << fallback_rule; }
    }
    return handled;
}

bool SocialXFallbackHandler::HandleFallback()
{
    return DoLocalFallback();
}

}
}
