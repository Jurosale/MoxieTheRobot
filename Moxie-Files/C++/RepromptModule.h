#ifndef EB_REPROMPT_MODULE_H
#define EB_REPROMPT_MODULE_H

#include <robotbrain2/ExtensionFunction.h>
#include <robotbrain2/Module.h>
#include <robotbrain2/engagement/ConcurrentInputModule.h> // we need to access cs interrupted var
#include <robotbrain2/messages/System.h>
#include <robotbrain2/io/Input.h>
#include <robotbrain2/io/Output.h>
#include <robotbrain2/io/Volley.h>
#include <embodied/robotbrain/ChatResponse.pb.h> // we need access to the output type

namespace embodied
{
namespace robotbrain
{

// Define Events
struct RepromptEvents
{
    struct ChatScript {};
};

/**
 * EBReprompt EventTypes
 */
struct EBReprompt {};
template<>
struct EventTraits<EBReprompt>
{
	static const char* event_string() { return "eb-reprompt"; }
	static const char* description() { return "fires when an auto reprompt timer finishes"; }
	static const bool  is_user_event() { return true; }
};

/**
 * an eb-reprompt EventInput
 */
typedef EventInput<EBReprompt> EBRepromptEvent;

// define possible engines
struct ChatEngines
{
    static const std::string chatscript() {return "chatscript";}
    static const std::string remote() {return "remote";}
};

class RepromptModule : public Module
{
    // store which engine produced last prompt response
    // maybe we don't need this yet?
    std::string last_response_engine_ = "";
    // store Remote Reprompt Text
    // Riely Allen 9/24/21: for now, this is just the last thing the Remote Engine said
    std::string remote_reprompt_text_ = "";
    // store the ending module of the previous volley
    std::string prev_module_ = "";
    // store the current topic name
    std::string stored_topic_ = "";
    // store the current volley's output
    std::string stored_response_ = "";
    // store the desired prepend text for the current volley
    std::string prepend_reprompt_text_ = "";
    // flag to keep track of whether or not save markup was called this volley
    bool save_markup_called_ = false;
    // flag to keep track of whether or not restore markup was called this volley
    bool restore_markup_called_ = false;
    // flag to keep track of whether or not ChatScript wants robotbrain to override its current volley's output
    bool do_reprompt_override_ = false;
    // keeps track of currently active rb reprompts
    std::list<std::tuple<std::string, std::string, std::string>> robotbrain_reprompts_;
    // markup strings
    const std::string save_markup_prefix_ = "<mark name=\"cmd:playback-save,data:{+stateToSAVE+:+MarkupState";
    const std::string restore_markup_prefix_ = "<mark name=\"cmd:playback-restore,data:{+stateToRESTORE+:+MarkupState";
    const std::string markup_suffix_ = "+}\"/>";
    
    // keeps track of which markup call slot we are currently on
    enum MarkupSlot
    {
        SLOT0 = 0,
        SLOT1 = 1
    };

    MarkupSlot markup_slot_ = MarkupSlot::SLOT0;

    // function to store rb Reprompt Text in a specified cs topic
    void SetReprompt(std::string reprompt_text, std::string chatscript_topic);
    // function to reset rb Reprompt Text by cs module ID
    void ClearReprompt(std::string chatscript_module);
    // function that resets all rb Reprompt texts.
    void ClearAllReprompts();
    // function to store Remote Reprompt Text
    void SetRemoteReprompt(const std::string& reprompt_text, const std::string& engine);
    // function to reset Remote Reprompt Text
    void ClearRemoteReprompt();
    // function to jump back and forth between our markup slots
    void ToggleSlot();

    // ChatScript Function to prepend rb Reprompt Text in current cs topic (if one exists)
    FunctionResult PrependCurrentReprompt(std::string& ret, std::string new_text);
    // ChatScript Function that overrides volley output with (any contextually relevant) rb Reprompt text.
    FunctionResult DoRepromptOverride(std::string& ret);
    // ChatScript Function returns Reprompt text.  if returns empty str, then ChatScript needs to reprompt
    FunctionResult GetRepromptText(std::string& ret);
    // ChatScript Function that sends a request to save the current markup state
    FunctionResult SaveMarkupState(std::string& ret);
    // ChatScript Function that restores the last saved markup state
    FunctionResult RestoreMarkupState(std::string& ret);

    // send a reprompt event into ChatScript?
    // check on volley finished the engine that produced output.
    // if response is NORMAL, set it as reprompt (for both engines)

public:
    using Module::Module;
    typedef std::shared_ptr<RepromptModule> ptr;
    // reset flags on chat volley start
    virtual void OnChatVolleyStarted(Volley& volley) override;
    // store the remote output for remote reprompts
    virtual void OnRemoteVolleyAccepted(Volley& volley) override;
    // clear remote output if chat volley finished
    virtual std::shared_ptr<ModuleRewindInfo> OnChatVolleyFinished(Volley& volley) override;
    // ChatScript extension functions
    virtual std::list<ExtensionFunction> ExtensionFunctions() override
    {
        return {
            ExtensionFunction("eb_prepend_current_reprompt", "prepends the desired text to the current robotbrain reprompt (if one exists)", &RepromptModule::PrependCurrentReprompt, this),
            ExtensionFunction("eb_override_with_reprompt", "overrides volley output with (any contextually relevant) robotbrain reprompt", &RepromptModule::DoRepromptOverride, this),
            ExtensionFunction("eb_do_reprompt", "get the reprompt output text", &RepromptModule::GetRepromptText, this),
            ExtensionFunction("eb_do_save_markup", "send request to save current markup state", &RepromptModule::SaveMarkupState, this),
            ExtensionFunction("eb_do_restore_markup", "restore the last saved markup state", &RepromptModule::RestoreMarkupState, this)
        };
    }

};

}
}
#endif