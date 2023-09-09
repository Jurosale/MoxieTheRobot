#ifndef BO_RB_FALLBACK_MODULE_H_
#define BO_RB_FALLBACK_MODULE_H_
/**
 * 
 * MPChat flow
===========

Chatscript-> handles input, calls ^eb_fallback_handler()
- for silent, event - return silence (for these - contexts and allow_multiple should be empty?)
- for default - return " " and FALLBACK type -> set a flag for the next eb-remote-speak volley

- RemoteEngine compares FALLBACK vs REMOTE_DELAY (accepts REMOTE_DELAY) 
    - add flag to remote engine to know that it needs to feed the event back in
- On response if (flag && remote_response == FALLBACK (!FAQ)): feed the eb-remote-speak into chatscript as well
    - handled by MPChat.cpp (^eb_handle_fallback_event())
        - generates a response from local events or other places
        - on any of the specific fallbacks (or perplexity > 0.5), response type is set to FALLBACK, FallbackType - set to specific or `LOCAL_FALLBACK`
        - in engagement module, also compare on FALLBACK_TYPE
        - this is where the counting happens based on output type
**/

#include <robotbrain2/QueuedModule.h>
#include <robotbrain2/content_modules/ContentFunctions.h>

namespace embodied
{
namespace robotbrain
{

/** 
 * @class FallbackHandler
 *
 * @brief Abstract base class for handling fallbacks
 */
class FallbackHandler
{
public:
    /// default destructor
    virtual ~FallbackHandler() = default;

    virtual bool HandlesThisVolley(Volley& volley,
                                   RobotState state, 
                                   const std::string& module_id,
                                   const serialized::NodeFallback& node_fallback) = 0;


    /**
     * try to handle a fallback.
     * 
     * @return true when the fallback is handled
     */
    virtual bool HandleFallback() = 0;
    virtual void KeepCounter();
    virtual void ResetCounter();
    virtual void RestoreCounter();

    virtual int FallbackCounter() const;
    virtual std::string SpeechInput() const;

    virtual void OnChatVolleyStarted(Volley& volley,
                                     const std::string& module_id,
                                     const std::string& content_id,
                                     const std::string& topic_id);
    virtual void OnChatVolleyFinished(Volley& volley);
    virtual void OnChatVolleyAborted(Volley& volley);

    virtual const char* Name() const = 0;

    
    
    /** @brief factory method for creating the fallback handlers
     *
     * Creates the fallback handlers in order
     */
    static void CreateFallbackHandlers(std::list<std::shared_ptr<FallbackHandler>>& handlers,
                                       MissionControl& mission_control,
                                       BrainData& data);
};

/**
 * @class MPChat 
 *
 * @brief Handles MP chat and remote fallbacks
 *
 * This class is responsible for handling contexts
 * inside chat and throughout content. 
 */
class MPChatModule : public QueuedModule
{
public:
    MPChatModule(BrainData& data,
                 MissionControl& mission_control);
    /** 
     * using the module and topic stored in the data, send the appropriate local context
     * 
     * if the module is MOXIMUSPRIME (we're inside MPChat Module), then send the conversation
     * context
     */
    virtual void OnChatVolleyStarted(Volley& volley) override;
    /**
     * 
     */
    virtual void OnRemoteVolleyAccepted(Volley& volley) override;
    /** 
     * 
     */
    virtual std::shared_ptr<ModuleRewindInfo> OnChatVolleyFinished(Volley& volley) override;
    /**
     * 
     */
    virtual void OnRewindVolley(std::shared_ptr<ModuleRewindInfo> rewind_info) override;
    /**
     * 
     */
    virtual void OnChatVolleyAborted(Volley& volley) override;

    virtual std::list<ExtensionFunction> ExtensionFunctions() override
    {
        return {
            ExtensionFunction("eb_handle_fallback", "handles fallbacks", &MPChatModule::HandleFallback, this),
            ExtensionFunction("eb_fallback_keep_counter", "keeps the current fallback counter", &MPChatModule::KeepCounter, this),
            ExtensionFunction("eb_fallback_reset_counter", "resets the current fallback counter", &MPChatModule::ResetCounter, this),
            ExtensionFunction("eb_fallback_reset_all_counters", "resets all fallback counters", &MPChatModule::ResetAllCounters, this),
            ExtensionFunction("eb_fallback_restore_counter", "restore the current fallback counter to the move on threshold", &MPChatModule::RestoreCounter, this),
            ExtensionFunction("eb_fallback_speech_input", "retrieves the last user speech that triggered any of the fallback handlers", &MPChatModule::GetSpeechInput, this)
        };
    }

    /**
     *  used to reset on session start
     */
    virtual void OnRobotStateChanged(RobotState current_state, RobotState previous_state) override;

private:
    /**
     * @brief determines what type of fallback action
     */ 
    FunctionResult HandleFallback(std::string& ret);
    /**
     * @brief keeps the current counter
     */
    FunctionResult KeepCounter(std::string& ret);
    /**
     * @brief resets the current counter
     */
    FunctionResult ResetCounter(std::string& ret);
    /**
     * @brief sets the current counter to the move on threshold after returning from the confirmation conversation.
     */
    FunctionResult RestoreCounter(std::string& ret);
    /**
     * @brief returns the current counter
     */
    FunctionResult GetCounter(std::string& ret);
    /**
     * @brief returns the last speech input that triggered the default fallback handler
     */
    FunctionResult GetSpeechInput(std::string& ret);
    /**
     * @brief resets all handler counters
     */
    FunctionResult ResetAllCounters(std::string& ret);

    /**
     * whether to use new fallback handler or not
     */
    bool UseNewFallbackHandler() const;
    /*
     * Format topic string correclty from chat_topic.
     */
    std::string FormatTopic(std::string& chat_topic, const std::string& chat_module, const std::string& all_chat_topics);

    /// store the mission control
    MissionControl& mission_control_;
    /// abstract the fallback handler
    std::list<std::shared_ptr<FallbackHandler> > fallback_handlers_;
    std::shared_ptr<FallbackHandler> current_fallback_handler_;

    std::string prev_chat_topic_;
    std::string prev_chat_module_;
    std::string prev_content_id_;

    serialized::NodeFallback current_node_;

};
               
}
}
#endif // BO_RB_FALLBACK_MODULE_H_