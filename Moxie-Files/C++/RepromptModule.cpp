// README: This file defines behaviors for when/how Moxie should reprompt and
// whether or not it needs to perform additional visual/sound effect actions

#include <robotbrain2/system/RepromptModule.h>

#define TAG "RepromptModule"
#include <bo-core/Logging.h>
#include <bo-core/TextUtilities.h>
#include <robotbrain2/utils/MarkupUtil.h>
#include <robotbrain2/utils/ChatScriptUtil.h>

namespace embodied
{
namespace robotbrain
{
    // This list contains all the chat modules that are considered tangents
    static const std::vector<std::string> TANGENT_CHAT_MODULES = { "gt", "bo", "wakeup" };
    // This list contains all the interupting events that could reasonably interrupt screen/sound markup
    static const std::vector<std::string> INTERRUPTING_EVENTS = { "eb-mpu-picked-up-interrupt" };
    // This list contains all the ChatScript topics we can reasonably expect to be the base topic
    static const std::vector<std::string> BASE_TOPICS = { "bo_heel_cool" };
    static const std::string stateChangeModName = "statechangetangentmodule";
    static const std::string stateChangeTopicName = stateChangeModName + "_topicname";
    static const int maxRobotBrainReprompts = 3;

    // Adds the requested reprompt (and its topic location) to the list of robotbrain reprompts
    // Also removes old or outdated reprompts until we are within our limit of reprompts
    void RepromptModule::SetReprompt(std::string reprompt_text, std::string chatscript_topic)
    {
        auto chatscript_module = ChatScriptUtil::GetModuleID(chatscript_topic);

        // Delete any existing reprompts that share the same module to ensure we only store one reprompt per module at most
        ClearReprompt(chatscript_module);

        LOG_INFO << "In topic: " << chatscript_topic << ", Adding new RB reprompt: " << reprompt_text;
        robotbrain_reprompts_.push_back(std::make_tuple(chatscript_module, chatscript_topic, reprompt_text));

        // Keep deleting the oldest reprompts until we are within the desired limit of reprompts
        while (robotbrain_reprompts_.size() > maxRobotBrainReprompts)
        {
            auto it = robotbrain_reprompts_.begin();
            LOG_INFO << "In topic: " << std::get<1>(*it) << ", Removing old RB reprompt: " << std::get<2>(*it);
            robotbrain_reprompts_.pop_front();
        }
    }

    // Removes any robotbrain reprompt located in the specified cs module
    void RepromptModule::ClearReprompt(std::string chatscript_module)
    {
        for (auto it = robotbrain_reprompts_.begin(); it != robotbrain_reprompts_.end(); ++it)
        {
            auto current_module = std::get<0>(*it);
            if(current_module == chatscript_module)
            {
                LOG_INFO << "In topic: " << std::get<1>(*it) << ", Clearing RB reprompt: " << std::get<2>(*it);
                robotbrain_reprompts_.erase(it);
            }
        }
    }

    void RepromptModule::ClearAllReprompts()
    {
        LOG_INFO << "Clearing all RB reprompts.";
        robotbrain_reprompts_.clear();    
    }

    void RepromptModule::SetLastPrompt(const std::string& prompt_text, const std::string& topic, const std::string& engine)
    {
        last_response_output_ = prompt_text;
        last_response_topic_ = topic;
        last_response_engine_ = engine;
        LOG_DEBUG << "Set last prompt output: " << last_response_output_;
        LOG_DEBUG << "Set last topic: " << last_response_topic_;
        LOG_DEBUG << "Set last engine: " << last_response_engine_;
    }

    void RepromptModule::ClearLastPrompt()
    {
        last_response_output_ = "";
        last_response_engine_ = "";
        last_response_topic_ = "";
        LOG_DEBUG << "Reset cached prompt";
    }

    std::string RepromptModule::GetLastPromptOutput()
    {
        return last_response_output_;
    }

    std::string RepromptModule::GetLastPromptTopic()
    {
        return last_response_topic_;
    }

    std::string RepromptModule::GetLastPromptEngine()
    {
        return last_response_engine_;
    }

    // This toggle will allow us to keep track of the head markup slot at all times
    // Since there are currently only 2 markup slots, if the current markup slot is
    // at 0, then slot 1 becomes the new head slot and vice versa
    void RepromptModule::ToggleSlot()
    {
        markup_slot_ = (markup_slot_ == MarkupSlot::SLOT0) ? MarkupSlot::SLOT1 : MarkupSlot::SLOT0;
    }

    // Reset all reprompt module flags
    void RepromptModule::OnChatVolleyStarted(Volley& volley)
    {
        skip_interrupt_handler_ = false;
        keep_last_prompt_ = false;
        save_markup_called_ = false;
        restore_markup_called_ = false;
        do_reprompt_override_ = false;
        do_reprompt_event_ = false;
        prepend_reprompt_text_ = "";
        LOG_INFO << "Resetting Reprompt Module flags and variables";
    }

    void RepromptModule::OnRemoteVolleyAccepted(Volley& volley)
    {
        // Retrieve last response and topic to perform needed checks and operations
        auto last_response_ = GetLastPromptOutput();
        auto last_topic_ = GetLastPromptTopic();

        // Get remote input and output
        std::string remote_response_ = volley.Output()->Response().response();
        std::string remote_input_ = volley.Input()->InputString();
        // NOTE: the following if/else statement intentionally ignores speechless
        // output that does not advance the conversation state (i.e. active thinking)
        if(remote_input_ == "eb-remote-act-stream")
        {
            // If "eb-remote-act-stream" specifically triggered this remote volley, then
            // it's a part of the previous remote output and should therefore append this
            // remote response to that output
            LOG_INFO << "Appending this additional output: " << remote_response_;
            last_response_ += remote_response_;
            SetLastPrompt(last_response_, stored_topic_, ChatEngines::remote());
        }
        else if(!Markup::IsMarkupOnly(remote_response_))
        {
            // Cache remote response only if it contains speech
            SetLastPrompt(remote_response_, stored_topic_, ChatEngines::remote());
        }
        else if(stored_topic_ != last_topic_)
        {
            // Clear cache if we've jumped to a new topic with a speechless response
            ClearLastPrompt();
        }
        else
        {
            LOG_INFO << "Did not update prompt";
        }
    }

    std::shared_ptr<ModuleRewindInfo> RepromptModule::OnChatVolleyFinished(Volley& volley)
    {
        // Retrieve last response and topic to perform needed checks and operations
        auto last_response_ = GetLastPromptOutput();
        auto last_topic_ = GetLastPromptTopic();

        // Skip interruption handling only if CS requested a "send reprompt" call to
        // avoid awkward interactions between dialogue override & sent reprompt event 
        if(skip_interrupt_handler_)
        {
            do_reprompt_override_ = false; // reprompt overriding is part of interruption handling
            LOG_INFO << "skipping interruption handling";
        }
        else
        {
            // Check whether or not the current volley is interrupting the previous volley
            // and if so, set RB reprompt to the interrupted volley's entire output
            std::string volley_interrupted;
            if (volley.Input()->IsEvent())
            {
                // If it's an event input, check if it's one of the accepted interrupting events
                auto volley_input = volley.Input()->InputString();
                if(std::find(INTERRUPTING_EVENTS.begin(), INTERRUPTING_EVENTS.end(), volley_input) != INTERRUPTING_EVENTS.end())
                    volley_interrupted = "true";
            }
            else
            {
                // If it's a speech input, it's interrupting if it contains the interruption variable
                volley.Input()->GetVariable(INPUT_INTERRUPTING_VARIABLE, volley_interrupted);
            }

            if (volley_interrupted == "true" && !last_response_.empty() && !last_topic_.empty())
            {
                LOG_INFO << "The last volley was interrupted before completing; storing it's output as a reprompt.";
                SetReprompt(last_response_, last_topic_);
            }
        }

        // Perform some checks on the current module and then store it
        auto curr_module = tolower(ChatScriptUtil::FormatChatName(volley.Output()->Response().chat_module(), true));

        // If chatscript sent a save markup request, it's because the volley entered a "state change" tangent
        if(save_markup_called_)
        {
            curr_module = stateChangeModName;
            stored_topic_ = stateChangeTopicName;
            keep_last_prompt_ = true;
            LOG_INFO << "Entering state change.";
        }

        // Store (ordered) traversed chat topics as a list and retrieve the current topic
        auto chat_topics = volley.Output()->Response().chat_topic();
        auto new_topic = ChatScriptUtil::GetChatTopic(curr_module, chat_topics, true);
        if (!new_topic.empty())
            stored_topic_ = tolower(new_topic);

        // If we end up traveling back to a base Chatscript topic, then we're starting a whole new convo and
        // we can clear all the currently stored robotbrain reprompts since we don't need them anymore.
        if(std::find(BASE_TOPICS.begin(), BASE_TOPICS.end(), stored_topic_) != BASE_TOPICS.end())
        {
            LOG_INFO << "Found CS traversing through this base topic: " << stored_topic_;
            ClearAllReprompts();
        }

        // If Chatscript requested a reprompt override and there is a robotbrain reprompt found in the current
        // topic (i.e. is contextually relevant), swap out the current volley's output with the found reprompt.
        // Regardless of outcome, delete any robotbrain reprompts located in the same module afterwards.
        if(do_reprompt_override_ && !stored_topic_.empty() && !robotbrain_reprompts_.empty())
        {
            LOG_INFO << "Searching for stored RB reprompt in topic: " << stored_topic_;

            for (auto it = robotbrain_reprompts_.begin(); it != robotbrain_reprompts_.end(); ++it)
            {
                if(std::get<1>(*it) == stored_topic_)
                {
                    auto new_reprompt = std::get<2>(*it);
                    if (!prepend_reprompt_text_.empty()){
                        LOG_INFO << "Prepending additional output to found RB reprompt";
                        new_reprompt = prepend_reprompt_text_ + " " + new_reprompt;
                    }
                    LOG_INFO << "Found and overriding volley output with this RB reprompt: " << new_reprompt;
                    volley.Output()->Response().set_response(new_reprompt);
                    keep_last_prompt_ = true;
                    break;
                }
            }

            if (!curr_module.empty())
                ClearReprompt(curr_module);
        }

        // Store the current response for potential reprompting purposes before continuing to save/restore procedures
        std::string local_response_ = volley.Output()->Response().response();

        // If we called restore markup on a one-volley tangent or reprompt, update the
        // restore markup to a tangent restore markup call & append a tangent save markup call
        if(restore_markup_called_ && prev_module_ == curr_module)
        {
            // To ensure we correctly enact a tangent restore markup call, we need to first undo the slot toggle from the earlier
            // restore call so that we can swap out the restore call of that markup slot with our tangent call instead.
            // This also means that the head slot remains the same this volley since we did not officially call a markup slot
            ToggleSlot();

            // NOTE: "local_response_" must both hold the correct restore markup AND NOT contain
            // any save markup to ensure the reprompting overriding system above works correctly
            ReplaceAll(local_response_, restore_markup_prefix_ + std::to_string((int)markup_slot_) + markup_suffix_, restore_markup_prefix_ + markup_suffix_);
            
            // Since we want to save the markup state at the start of the volley, we'll append this save markup call to the start of ChatScript's output
            auto new_response = save_markup_prefix_ + markup_suffix_;
            new_response += local_response_;
            // Now set volley output with this new response which contains both save & restore tangent markup calls
            volley.Output()->Response().set_response(new_response);
            LOG_INFO << "This is a one-volley tangent or re-prompt; prepending a tangent save markup call and swapping previous restore call for a tangent restore markup call.";
        }

        // Else if we've changed chat modules...
        else if(prev_module_ != curr_module)
        {
            if (prev_module_.empty())
            {
                LOG_INFO << "Initial volley.";
            }
            else if (restore_markup_called_)
            {
                LOG_INFO << "Restore markup already requested this volley; not prepending save markup call since it's IMPLIED a module is being popped (not pushed).";
            }
            else if (prev_module_ == stateChangeModName)
            {
                LOG_INFO << "Exiting state change; no need to prepend a save markup call.";
            }
            else if(std::find(TANGENT_CHAT_MODULES.begin(), TANGENT_CHAT_MODULES.end(), curr_module) != TANGENT_CHAT_MODULES.end())
            {
                LOG_INFO << "No need to prepend a save markup call since volley finished in this tangent module: " << curr_module;
            }
            else
            {
                // Anytime we make a call to save a new markup state, we need to update our slots first and then save it in the new head slot
                // This way, the head markup slot should contain the content of the exiting module for a future potential restore markup call
                ToggleSlot();

                // Since we want to save the markup state at the start of the volley, we'll append this save markup call to the start of ChatScript's output
                auto new_response = save_markup_prefix_ + std::to_string((int)markup_slot_) + markup_suffix_;
                new_response += local_response_;
                // Now set volley output with this new response which only contains a save markup call
                volley.Output()->Response().set_response(new_response);
                LOG_INFO << "Jumping to a new module; prepending save markup call at slot " << std::to_string((int)markup_slot_);
            }
            prev_module_ = curr_module;
        }

        // No need to update last prompt if CS successfully overrides reprompt or plays last prompt
        // since end result would either be the same or append unneeded speech
        if (!keep_last_prompt_)
        {
            // NOTE: the following if/else statement intentionally ignores speechless
            // output that does not advance the conversation state (i.e. active thinking)

            // Cache local response only if it contains speech
            // Otherwise clear cache if we've jumped to a new topic
            if(!Markup::IsMarkupOnly(local_response_))
                SetLastPrompt(local_response_, stored_topic_, ChatEngines::chatscript());
            else if (stored_topic_ != last_topic_)
                ClearLastPrompt();
            else
                LOG_INFO << "Did not update prompt";
        }

        return nullptr;
    }

    std::shared_ptr<Input> RepromptModule::InputReady()
    {
        if (do_reprompt_event_)
        {
            auto event = new EBRepromptEvent();
            event->SetVariable("$eb_reprompt_source", "repromptModule");
            return std::shared_ptr<Input>(event);
        }
        return nullptr;
    }

    FunctionResult RepromptModule::PrependCurrentReprompt(std::string& ret, std::string new_text)
    {
        LOG_INFO << "CS has requested to prepend addtional text to a stored RB reprompt.";
        prepend_reprompt_text_ = new_text;

        return NOPROBLEM_BIT;

    }

    FunctionResult RepromptModule::DoRepromptOverride(std::string& ret)
    {
        LOG_INFO << "CS has requested overriding volley output with a stored RB reprompt.";
        do_reprompt_override_ = true;

        return NOPROBLEM_BIT;
        
    }

    // Sends the last cached output or eb-reprompt if cache is empty
    FunctionResult RepromptModule::SendReprompt(std::string& ret, std::string engine_request)
    {
        auto last_prompt = GetLastPromptOutput();
        auto last_engine = GetLastPromptEngine();
        keep_last_prompt_ = true;
        skip_interrupt_handler_ = true;
        if(last_prompt == "" ||
            (tolower(engine_request) == "remote" && last_engine != ChatEngines::remote()) ||
            (tolower(engine_request) == "chatscript" && last_engine != ChatEngines::chatscript()))
        {
            LOG_INFO << "Sending eb-reprompt request";
            do_reprompt_event_ = true;
            // This is here in case no one else produces output from CS side
            ret = LineDB::DB().GetText(LineDB::ANIM_CURIOUS);
        }
        else
        {
            LOG_INFO << "Sending prompt output: " << last_prompt;
            ret = last_prompt;
        }

        return NOPROBLEM_BIT;
        
    }

    // Lets robot brain know that CS wants to make a save markup call
    FunctionResult RepromptModule::SaveMarkupState(std::string& ret)
    {
        if(!save_markup_called_)
        {
            save_markup_called_ = true;
            LOG_INFO << "Sending save markup request.";
        }
        else
            LOG_INFO << "Save markup was already called this volley. Ignoring save markup request.";

        return NOPROBLEM_BIT;
        
    }

    // Returns the current head restore markup call to append to ChatScript's output
    FunctionResult RepromptModule::RestoreMarkupState(std::string& ret)
    {
        if(!restore_markup_called_)
        {
            restore_markup_called_ = true;

            // Anytime we make a call to restore a markup state, we need to restore the head slot
            ret = restore_markup_prefix_ + std::to_string((int)markup_slot_) + markup_suffix_;
            LOG_INFO << "Appending restore markup call at slot " << std::to_string((int)markup_slot_);

            // Since we officially used up this slot, we need to convert the other slot to become the new head slot. This way,
            // the head markup slot should contain the content of the last exited module for a future potential restore markup call
            ToggleSlot();
        }
        else
            LOG_INFO << "Restore markup was already called this volley. Ignoring restore markup request.";

        return NOPROBLEM_BIT;
        
    }

}
}
