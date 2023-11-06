#ifndef EB_REPROMPT_MODULE_H
#define EB_REPROMPT_MODULE_H

#include <robotbrain2/ExtensionFunction.h>
#include <robotbrain2/Module.h>
#include <robotbrain2/engagement/ConcurrentInputModule.h> // we need to access cs interrupted var
#include <robotbrain2/messages/System.h>
#include <robotbrain2/io/Input.h>
#include <robotbrain2/io/Output.h>
#include <robotbrain2/io/Volley.h>
#include <robotbrain2/data/LineDB.h>
#include <embodied/robotbrain/ChatResponse.pb.h> // we need access to the output type

namespace embodied
{
namespace robotbrain
{

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
    std::string last_response_engine_ = "";
    // store last prompt response
    std::string last_response_output_ = "";
    // store last prompt topic
    std::string last_response_topic_ = "";
    // store the ending module of the previous volley
    std::string prev_module_ = "";
    // store the current CS topic name
    std::string stored_topic_ = "";
    // store the desired prepend text for the current volley
    std::string prepend_reprompt_text_ = "";
    // flag to keep track of whether or not to perform interruption handling
    bool skip_interrupt_handler_ = false;
    // flag to keep track of whether or not to update the last prompt
    bool keep_last_prompt_ = false;
    // flag to keep track of whether or not save markup was called this volley
    bool save_markup_called_ = false;
    // flag to keep track of whether or not restore markup was called this volley
    bool restore_markup_called_ = false;
    // flag to keep track of whether or not ChatScript wants robotbrain to override its current volley's output
    bool do_reprompt_override_ = false;
    // flag to send an eb-reprompt event
    bool do_reprompt_event_ = false;
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
    // function to cache latest prompt output
    void SetLastPrompt(const std::string& prompt_text, const std::string& topic, const std::string& engine);
    // function to reset cached output
    void ClearLastPrompt();
    // function to return cached output
    std::string GetLastPromptOutput();
    // function to return cached topic
    std::string GetLastPromptTopic();
    // function to return cached engine
    std::string GetLastPromptEngine();
    // function to jump back and forth between our markup slots
    void ToggleSlot();

    // ChatScript Function to prepend rb Reprompt Text in current cs topic (if one exists)
    FunctionResult PrependCurrentReprompt(std::string& ret, std::string new_text);
    // ChatScript Function that overrides volley output with (any contextually relevant) rb Reprompt text.
    FunctionResult DoRepromptOverride(std::string& ret);
    // ChatScript Function that sends the last cached prompt output; sends eb-reprompt if unable to send output.
    // Can take in optional argument so it only sends output with the desired engine type 
    FunctionResult SendReprompt(std::string& ret, std::string engine_request="");
    // ChatScript Function that sends a request to save the current markup state
    FunctionResult SaveMarkupState(std::string& ret);
    // ChatScript Function that restores the last saved markup state
    FunctionResult RestoreMarkupState(std::string& ret);

public:
    using Module::Module;
    typedef std::shared_ptr<RepromptModule> ptr;
    // reset flags on chat volley start
    virtual void OnChatVolleyStarted(Volley& volley) override;
    // store the remote output as the last prompt
    virtual void OnRemoteVolleyAccepted(Volley& volley) override;
    // store local output as the last prompt and handles reprompts/interruptions
    virtual std::shared_ptr<ModuleRewindInfo> OnChatVolleyFinished(Volley& volley) override;
    // returns eb-reprompt when requested by SendReprompt()
    virtual std::shared_ptr<Input> InputReady() override;
    // ChatScript extension functions
    virtual std::list<ExtensionFunction> ExtensionFunctions() override
    {
        return {
            ExtensionFunction("eb_prepend_current_reprompt", "prepends the desired text to the current robotbrain reprompt (if one exists)", &RepromptModule::PrependCurrentReprompt, this),
            ExtensionFunction("eb_override_with_reprompt", "overrides volley output with (any contextually relevant) robotbrain reprompt", &RepromptModule::DoRepromptOverride, this),
            ExtensionFunction("eb_do_reprompt", "send last cached output or eb-reprompt if empty", &RepromptModule::SendReprompt, this),
            ExtensionFunction("eb_do_save_markup", "send request to save current markup state", &RepromptModule::SaveMarkupState, this),
            ExtensionFunction("eb_do_restore_markup", "restore the last saved markup state", &RepromptModule::RestoreMarkupState, this)
        };
    }

};

}
}
#endif
