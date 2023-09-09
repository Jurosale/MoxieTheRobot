#ifndef BO_RB_FB_HANDLERS_H_
#define BO_RB_FB_HANDLERS_H_

#include <robotbrain2/content_modules/ContentFunctions.h>
#include <robotbrain2/content_modules/ContentModule.h>
#include <robotbrain2/content_modules/MPChat.h>

namespace embodied
{
namespace robotbrain
{

using FallbackHandlerBase = content::mixins::WithMissionControl<FallbackHandler>;

class SilentFallbackHandler : public FallbackHandlerBase
{
public:
    using FallbackHandlerBase::FallbackHandlerBase;
    virtual bool HandleFallback() override;
    virtual bool HandlesThisVolley(Volley& volley, 
                                   RobotState state, 
                                   const std::string& module_id, 
                                   const serialized::NodeFallback& node) override;
    virtual const char* Name() const override;
};

class EventFallbackHandler : public FallbackHandlerBase
{
public: 
    using FallbackHandlerBase::FallbackHandlerBase;
    virtual bool HandleFallback() override;
    virtual bool HandlesThisVolley(Volley& volley, 
                                   RobotState state, 
                                   const std::string& module_id, 
                                   const serialized::NodeFallback& node) override;
    virtual const char* Name() const override;
};

using CtxFallbackHandlerBase = content::mixins::WithData<FallbackHandlerBase>;
class FallbackHandlerWithContext : public CtxFallbackHandlerBase
{ 
public:
    using CtxFallbackHandlerBase::CtxFallbackHandlerBase;
    void UpdateRemoteContext(Volley& volley,
                             const std::string& module_id,
                             const std::string& content_id,
                             const std::string& topic_id);
};

class DefaultFallbackHandler : public FallbackHandlerWithContext
{
public:
    using FallbackHandlerWithContext::FallbackHandlerWithContext;
    virtual bool HandleFallback() override;
    
    virtual void KeepCounter() override;
    virtual void ResetCounter() override;
    virtual void RestoreCounter() override;

    virtual void OnChatVolleyStarted(Volley& volley,
                                     const std::string& module,
                                     const std::string& content_id,
                                     const std::string& topic_id) override;
    virtual void OnChatVolleyFinished(Volley& volley) override;
    virtual void OnChatVolleyAborted(Volley& volley) override;

    virtual bool HandlesThisVolley(Volley& volley, 
                                   RobotState state, 
                                   const std::string& module_id, 
                                   const serialized::NodeFallback& node) override;
    virtual const char* Name() const override;
    virtual int FallbackCounter() const override;
    virtual std::string SpeechInput() const override;

private:
    const int MOVE_ON_THRESHOLD = 3;
    const int CHAT_THRESHOLD = 2; 

    int counter_ = 0;
    bool handled_this_volley_ = false;
    bool reset_counter_ = false;
    bool skip_increment_ = false;
    bool skip_remote_ = false;

    enum class FallbackHandlerState
    {
        INITIAL_VOLLEY,
        AFTER_INITIAL_VOLLEY,
        SECOND_VOLLEY,
    };
    FallbackHandlerState state_;
    FallbackHandlerState starting_state_;

    bool CheckSignal();
    bool DoLocalFallback();
    bool DoClarification();
    bool DoConfirmation();
    bool DoMoveOn();
    bool DoReprompt();

    bool ShouldReset(const Volley& volley);
    bool ShouldIncrement(const Volley& volley);

    bool DoInitialVolley();
    bool DoSecondVolley();
    bool HandleInOneVolley();

    std::string module_;
    std::string topic_;
    std::string fallback_rule_;
    std::string speech_input_;
};

/// currently only for MOXIMUSPRIME
class ConversationFallbackHandler : public FallbackHandlerWithContext
{
public:
    using FallbackHandlerWithContext::FallbackHandlerWithContext;
    virtual void OnChatVolleyStarted(Volley& volley,
                                 const std::string& module,
                                 const std::string& content_id,
                                 const std::string& topic_id) override;
    virtual bool HandleFallback() override;
    virtual bool HandlesThisVolley(Volley& volley, 
                               RobotState state, 
                               const std::string& module_id, 
                               const serialized::NodeFallback& node) override;
    virtual const char* Name() const override;
};

class SocialXFallbackHandler : public FallbackHandlerBase
{
public:
    using FallbackHandlerBase::FallbackHandlerBase;
    virtual bool HandleFallback() override;
    virtual bool HandlesThisVolley(Volley& volley, 
                                   RobotState state, 
                                   const std::string& module_id, 
                                   const serialized::NodeFallback& node) override;
    virtual const char* Name() const override;
private:
    bool DoLocalFallback();
};

}
}

#endif