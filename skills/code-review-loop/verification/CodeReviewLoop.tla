--------------------------- MODULE CodeReviewLoop ---------------------------
EXTENDS Naturals, TLC

(***************************************************************************
WHY
  The review protocol has two concurrent actors and six file-backed signals in
  one fixed abstract coordination namespace.
  TLC explores whether compliant action interleavings preserve snapshot,
  publication, decision, cleanup, and shutdown guarantees.

WHAT
  This module models arbitrary stale-file startup cleanup, an externally
  launched passive reviewer, mandatory implementor context on every request,
  reviewer findings or NO_FINDINGS, atomic channel publication, another
  planned implementation phase, shutdown through the implementor protocol
  endpoint, and one budgeted lock loss. Whether the implementor or its caller
  owns the shutdown decision is control policy outside this file-state model.

  The six top-level variables use records for file, content, request, and
  fault state. Every action specifies each top-level next state, so TLC rejects
  incomplete successors. Concrete paths and the reviewer's static-only
  inspection behavior are outside the state-machine abstraction. The Python
  role scripts implement waits as silent one-second polls. A poll that only
  observes unchanged state is a stuttering step and is not represented
  separately; missing-lock recovery maps to RetryMissingRequest, and a ready
  result enables the corresponding actor transition.

HOW TO RUN
  From this directory:

      ./run-tlc.sh
      ./check-state-space.sh
      ./check-early-unlock.sh
      ./check-temp-file-unlock.sh
      ./check-cleanup-order.sh

  The runner requires Java 11+ and tla2tools.jar. Override discovery with:

      JAVA_BIN=/path/to/java \
      TLA2TOOLS_JAR=/path/to/tla2tools.jar \
      TLA2TOOLS_SHA256=expected-digest \
      ./run-tlc.sh

  TLC must finish with "Model checking completed. No error has been found."
  Run statistics and tool provenance are recorded in the adjacent README.

EnableLockLoss permits at most one environmental deletion of a current review
lock, before acquisition or while a reviewer is active but has not decided.
EnableEarlyUnlock and EnableTempFileEarlyUnlock add invalid reviewer unlocks.
EnableEarlyCompletionPublication publishes completion before cleanup finishes.
***************************************************************************)

CONSTANTS
    EnableLockLoss,
    EnableEarlyUnlock,
    EnableTempFileEarlyUnlock,
    EnableEarlyCompletionPublication

ImplStates == {
    "starting",
    "editing",
    "readyToMessage",
    "writingMessage",
    "messagePublished",
    "acknowledging",
    "ready",
    "waiting",
    "handling",
    "cleaning",
    "awaitingShutdownAck",
    "done"
}

ReviewerStates == {
    "offline",
    "pollingFresh",
    "pollingParticipated",
    "reviewing",
    "publishingFeedback",
    "releasing",
    "done"
}

FileStates == [
    reviewLock : BOOLEAN,
    reviewerToImplementorTmp : BOOLEAN,
    reviewerToImplementorTxt : BOOLEAN,
    implementorToReviewerTmp : BOOLEAN,
    implementorToReviewerTxt : BOOLEAN,
    roundComplete : BOOLEAN
]

ContentStates == [
    code : BOOLEAN,
    submittedCode : BOOLEAN,
    reviewedCode : BOOLEAN,
    reviewerMessage : BOOLEAN,
    implementorMessage : BOOLEAN,
    submittedImplementorMessage : BOOLEAN
]

FeedbackKinds == {"none", "findings", "noFindings"}
ReviewerFeedbackKinds == {"findings", "noFindings"}

RequestStates == [
    active : BOOLEAN,
    decisionCount : 0..1,
    submittedImplementorMessagePresent : BOOLEAN,
    feedbackKind : FeedbackKinds
]

FaultStates == [lockLossAvailable : BOOLEAN]

VARIABLES
    impl,
    reviewer,
    files,
    content,
    request,
    faults

vars == <<
    impl,
    reviewer,
    files,
    content,
    request,
    faults
>>

FilesExceptCompletionAbsent ==
    /\ ~files.reviewLock
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ ~files.implementorToReviewerTmp
    /\ ~files.implementorToReviewerTxt

AllFilesAbsent ==
    /\ FilesExceptCompletionAbsent
    /\ ~files.roundComplete

ReviewerActive ==
    reviewer \in {"reviewing", "publishingFeedback", "releasing"}

ReviewerPolling ==
    reviewer \in {"pollingFresh", "pollingParticipated"}

ProtocolStarted == impl # "starting"

Init ==
    /\ impl = "starting"
    /\ reviewer = "offline"
    /\ files \in FileStates
    /\ content = [
        code |-> FALSE,
        submittedCode |-> FALSE,
        reviewedCode |-> FALSE,
        reviewerMessage |-> FALSE,
        implementorMessage |-> FALSE,
        submittedImplementorMessage |-> FALSE
        ]
    /\ request = [
        active |-> FALSE,
        decisionCount |-> 0,
        submittedImplementorMessagePresent |-> FALSE,
        feedbackKind |-> "none"
        ]
    /\ faults = [lockLossAvailable |-> EnableLockLoss]

\* Startup removes one stale file at a time. The completion marker is removed
\* only after every other working file is absent.
StartupCleanupStep ==
    /\ impl = "starting"
    /\ \/
        /\ files.reviewLock
        /\ files' = [files EXCEPT !.reviewLock = FALSE]
       \/ /\
            files.reviewerToImplementorTmp
          /\ files' = [
              files EXCEPT !.reviewerToImplementorTmp = FALSE
              ]
       \/ /\
            files.reviewerToImplementorTxt
          /\ files' = [
              files EXCEPT !.reviewerToImplementorTxt = FALSE
              ]
       \/ /\
            files.implementorToReviewerTmp
          /\ files' = [
              files EXCEPT !.implementorToReviewerTmp = FALSE
              ]
       \/ /\
            files.implementorToReviewerTxt
          /\ files' = [
              files EXCEPT !.implementorToReviewerTxt = FALSE
              ]
       \/ /\
            files.roundComplete
          /\ FilesExceptCompletionAbsent
          /\ files' = [files EXCEPT !.roundComplete = FALSE]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request,
        faults
        >>

FinishStartupCleanup ==
    /\ impl = "starting"
    /\ AllFilesAbsent
    /\ impl' = "editing"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

\* This transition represents the external caller launching the passive
\* reviewer only after the implementor reports startup cleanup complete.
StartReviewer ==
    /\ reviewer = "offline"
    /\ ProtocolStarted
    /\ reviewer' = "pollingFresh"
    /\ UNCHANGED <<
        impl,
        files,
        content,
        request,
        faults
        >>

FinishImplementationPhase ==
    /\ impl = "editing"
    /\ ~files.reviewLock
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ ~files.implementorToReviewerTmp
    /\ ~files.roundComplete
    /\ impl' = "readyToMessage"
    /\ \E newCode \in BOOLEAN:
        content' = [content EXCEPT !.code = newCode]
    /\ UNCHANGED <<
        reviewer,
        files,
        request,
        faults
        >>

ClearImplementorMessage ==
    /\ impl = "readyToMessage"
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.implementorToReviewerTmp
    /\ files.implementorToReviewerTxt
    /\ files' = [
        files EXCEPT !.implementorToReviewerTxt = FALSE
        ]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request,
        faults
        >>

\* A later request may reuse the complete published context unchanged. The
\* inbound reviewer final is acknowledged separately.
ReuseImplementorMessage ==
    /\ impl = "readyToMessage"
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.implementorToReviewerTmp
    /\ files.implementorToReviewerTxt
    /\ impl' = "acknowledging"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

StartImplementorMessage ==
    /\ impl = "readyToMessage"
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.implementorToReviewerTmp
    /\ ~files.implementorToReviewerTxt
    /\ impl' = "writingMessage"
    /\ files' = [files EXCEPT !.implementorToReviewerTmp = TRUE]
    /\ UNCHANGED <<
        reviewer,
        content,
        request,
        faults
        >>

PublishImplementorMessage ==
    /\ impl = "writingMessage"
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ files.implementorToReviewerTmp
    /\ ~files.implementorToReviewerTxt
    /\ impl' = "messagePublished"
    /\ files' = [
        files EXCEPT
            !.implementorToReviewerTmp = FALSE,
            !.implementorToReviewerTxt = TRUE
        ]
    /\ \E newMessage \in BOOLEAN:
        content' = [content EXCEPT !.implementorMessage = newMessage]
    /\ UNCHANGED <<
        reviewer,
        request,
        faults
        >>

FinishImplementorMessage ==
    /\ impl = "messagePublished"
    /\ ~files.reviewLock
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.implementorToReviewerTmp
    /\ files.implementorToReviewerTxt
    /\ impl' = "acknowledging"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

FinishInitialPreparation ==
    /\ impl = "acknowledging"
    /\ ~request.active
    /\ ~files.reviewerToImplementorTxt
    /\ impl' = "ready"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

AcknowledgeReviewerMessage ==
    /\ impl = "acknowledging"
    /\ request.active
    /\ request.decisionCount = 1
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.reviewerToImplementorTmp
    /\ files.reviewerToImplementorTxt
    /\ impl' = IF request.feedbackKind = "noFindings"
        THEN "editing"
        ELSE "readyToMessage"
    /\ files' = [files EXCEPT !.reviewerToImplementorTxt = FALSE]
    /\ request' = [
        request EXCEPT
            !.active = FALSE,
            !.decisionCount = 0,
            !.feedbackKind = "none"
        ]
    /\ UNCHANGED <<
        reviewer,
        content,
        faults
        >>

RequestReview ==
    /\ impl = "ready"
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ ~files.implementorToReviewerTmp
    /\ files.implementorToReviewerTxt
    /\ impl' = "waiting"
    /\ files' = [files EXCEPT !.reviewLock = TRUE]
    /\ content' = [
        content EXCEPT
            !.submittedCode = content.code,
            !.submittedImplementorMessage = content.implementorMessage
        ]
    /\ request' = [
        request EXCEPT
            !.active = TRUE,
            !.decisionCount = 0,
            !.submittedImplementorMessagePresent =
                files.implementorToReviewerTxt,
            !.feedbackKind = "none"
        ]
    /\ UNCHANGED <<
        reviewer,
        faults
        >>

LosePollingLock ==
    /\ EnableLockLoss
    /\ faults.lockLossAvailable
    /\ impl = "waiting"
    /\ ReviewerPolling
    /\ files.reviewLock
    /\ request.active
    /\ request.decisionCount = 0
    /\ files' = [files EXCEPT !.reviewLock = FALSE]
    /\ faults' = [faults EXCEPT !.lockLossAvailable = FALSE]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request
        >>

\* A re-created marker is the same logical request. The submitted
\* implementation and implementor message stay frozen across this gap.
LoseActiveReviewLock ==
    /\ EnableLockLoss
    /\ faults.lockLossAvailable
    /\ impl = "waiting"
    /\ reviewer \in {"reviewing", "publishingFeedback"}
    /\ files.reviewLock
    /\ request.active
    /\ request.decisionCount = 0
    /\ files' = [files EXCEPT !.reviewLock = FALSE]
    /\ faults' = [faults EXCEPT !.lockLossAvailable = FALSE]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request
        >>

RetryMissingRequest ==
    /\ impl = "waiting"
    /\ request.active
    /\ request.decisionCount = 0
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ ~files.implementorToReviewerTmp
    /\ files' = [files EXCEPT !.reviewLock = TRUE]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request,
        faults
        >>

\* Entering reviewing represents the mandatory read of the frozen implementor
\* context before the review decision can be produced.
BeginReview ==
    /\ ReviewerPolling
    /\ files.reviewLock
    /\ files.implementorToReviewerTxt
    /\ ~files.implementorToReviewerTmp
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ ~files.roundComplete
    /\ reviewer' = "reviewing"
    /\ content' = [
        content EXCEPT !.reviewedCode = content.submittedCode
        ]
    /\ UNCHANGED <<
        impl,
        files,
        request,
        faults
        >>

AbortReviewAfterLockLoss ==
    /\ reviewer \in {"reviewing", "publishingFeedback"}
    /\ ~files.reviewLock
    /\ reviewer' = "pollingParticipated"
    /\ files' = [
        files EXCEPT !.reviewerToImplementorTmp = FALSE
        ]
    /\ UNCHANGED <<
        impl,
        content,
        request,
        faults
        >>

StartPublishingFeedback ==
    /\ reviewer = "reviewing"
    /\ files.reviewLock
    /\ ~files.roundComplete
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ reviewer' = "publishingFeedback"
    /\ files' = [files EXCEPT !.reviewerToImplementorTmp = TRUE]
    /\ UNCHANGED <<
        impl,
        content,
        request,
        faults
        >>

PublishFeedback ==
    /\ reviewer = "publishingFeedback"
    /\ files.reviewLock
    /\ files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ reviewer' = "releasing"
    /\ files' = [
        files EXCEPT
            !.reviewerToImplementorTmp = FALSE,
            !.reviewerToImplementorTxt = TRUE
        ]
    /\ \E newMessage \in BOOLEAN:
        \E newKind \in ReviewerFeedbackKinds:
            /\ content' = [
                content EXCEPT !.reviewerMessage = newMessage
                ]
            /\ request' = [
                request EXCEPT
                    !.decisionCount = request.decisionCount + 1,
                    !.feedbackKind = newKind
                ]
    /\ UNCHANGED <<
        impl,
        faults
        >>

ReleaseFeedback ==
    /\ reviewer = "releasing"
    /\ files.reviewLock
    /\ files.reviewerToImplementorTxt
    /\ reviewer' = "pollingParticipated"
    /\ files' = [files EXCEPT !.reviewLock = FALSE]
    /\ UNCHANGED <<
        impl,
        content,
        request,
        faults
        >>

EarlyUnlockBeforePublishing ==
    /\ EnableEarlyUnlock
    /\ reviewer = "reviewing"
    /\ files.reviewLock
    /\ ~files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ reviewer' = "pollingParticipated"
    /\ files' = [files EXCEPT !.reviewLock = FALSE]
    /\ UNCHANGED <<
        impl,
        content,
        request,
        faults
        >>

EarlyUnlockWithFeedbackTemp ==
    /\ EnableTempFileEarlyUnlock
    /\ reviewer = "publishingFeedback"
    /\ files.reviewLock
    /\ files.reviewerToImplementorTmp
    /\ ~files.reviewerToImplementorTxt
    /\ reviewer' = "pollingParticipated"
    /\ files' = [files EXCEPT !.reviewLock = FALSE]
    /\ UNCHANGED <<
        impl,
        content,
        request,
        faults
        >>

\* This transition is the implementor's mandatory full read before editing.
ObserveReviewerFeedback ==
    /\ impl = "waiting"
    /\ request.active
    /\ request.decisionCount = 1
    /\ ~files.reviewLock
    /\ files.reviewerToImplementorTxt
    /\ ~files.roundComplete
    /\ impl' = "handling"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

ApplyReviewerFeedback ==
    /\ impl = "handling"
    /\ ~files.reviewLock
    /\ files.reviewerToImplementorTxt
    /\ request.feedbackKind = "findings"
    /\ impl' = "acknowledging"
    /\ \E newCode \in BOOLEAN:
        content' = [content EXCEPT !.code = newCode]
    /\ UNCHANGED <<
        reviewer,
        files,
        request,
        faults
        >>

\* NO_FINDINGS closes only the submitted snapshot. Another planned phase may
\* be implemented before the next request.
ContinueAfterNoFindings ==
    /\ impl = "handling"
    /\ ~files.reviewLock
    /\ files.reviewerToImplementorTxt
    /\ request.feedbackKind = "noFindings"
    /\ impl' = "acknowledging"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

BeginCompletionCleanup ==
    /\ impl = "handling"
    /\ ~files.reviewLock
    /\ ~files.roundComplete
    /\ files.reviewerToImplementorTxt
    /\ request.active
    /\ request.decisionCount = 1
    /\ request.feedbackKind = "noFindings"
    /\ impl' = "cleaning"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

RemoveCleanupReviewerTmp ==
    /\ impl = "cleaning"
    /\ ~files.roundComplete
    /\ files.reviewerToImplementorTmp
    /\ files' = [
        files EXCEPT !.reviewerToImplementorTmp = FALSE
        ]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request,
        faults
        >>

RemoveCleanupImplementorTmp ==
    /\ impl = "cleaning"
    /\ ~files.roundComplete
    /\ files.implementorToReviewerTmp
    /\ files' = [
        files EXCEPT !.implementorToReviewerTmp = FALSE
        ]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request,
        faults
        >>

RemoveCleanupImplementorTxt ==
    /\ impl = "cleaning"
    /\ ~files.roundComplete
    /\ files.implementorToReviewerTxt
    /\ files' = [
        files EXCEPT !.implementorToReviewerTxt = FALSE
        ]
    /\ UNCHANGED <<
        impl,
        reviewer,
        content,
        request,
        faults
        >>

\* The concrete CLI empties the retained reviewer final and atomically renames
\* that same entry to the completion marker. This action models that promotion.
PublishCompletion ==
    /\ impl = "cleaning"
    /\ ~files.roundComplete
    /\ ~files.reviewLock
    /\ ~files.reviewerToImplementorTmp
    /\ files.reviewerToImplementorTxt
    /\ ~files.implementorToReviewerTmp
    /\ ~files.implementorToReviewerTxt
    /\ request.active
    /\ request.decisionCount = 1
    /\ request.feedbackKind = "noFindings"
    /\ impl' = "awaitingShutdownAck"
    /\ files' = [
        files EXCEPT
            !.reviewerToImplementorTxt = FALSE,
            !.roundComplete = TRUE
        ]
    /\ request' = [
        request EXCEPT
            !.active = FALSE,
            !.decisionCount = 0,
            !.submittedImplementorMessagePresent = FALSE
        ]
    /\ UNCHANGED <<
        reviewer,
        content,
        faults
        >>

\* Negative mutation: completion is published while another file remains.
EarlyPublishCompletionMarker ==
    /\ EnableEarlyCompletionPublication
    /\ impl = "cleaning"
    /\ ~files.roundComplete
    /\ ~FilesExceptCompletionAbsent
    /\ impl' = "awaitingShutdownAck"
    /\ files' = [files EXCEPT !.roundComplete = TRUE]
    /\ UNCHANGED <<
        reviewer,
        content,
        request,
        faults
        >>

\* The reviewer uses only its own participation state and the observable
\* completion marker; it does not read private implementor control state.
AcknowledgeCompletion ==
    /\ reviewer = "pollingParticipated"
    /\ files.roundComplete
    /\ reviewer' = "done"
    /\ files' = [files EXCEPT !.roundComplete = FALSE]
    /\ UNCHANGED <<
        impl,
        content,
        request,
        faults
        >>

ObserveCompletionAcknowledged ==
    /\ impl = "awaitingShutdownAck"
    /\ reviewer = "done"
    /\ AllFilesAbsent
    /\ impl' = "done"
    /\ UNCHANGED <<
        reviewer,
        files,
        content,
        request,
        faults
        >>

\* This self-loop keeps deadlock checking enabled at valid termination.
TerminalStutter ==
    /\ impl = "done"
    /\ reviewer = "done"
    /\ UNCHANGED <<
        impl,
        reviewer,
        files,
        content,
        request,
        faults
        >>

Next ==
    \/ StartupCleanupStep
    \/ FinishStartupCleanup
    \/ StartReviewer
    \/ FinishImplementationPhase
    \/ ClearImplementorMessage
    \/ ReuseImplementorMessage
    \/ StartImplementorMessage
    \/ PublishImplementorMessage
    \/ FinishImplementorMessage
    \/ FinishInitialPreparation
    \/ AcknowledgeReviewerMessage
    \/ RequestReview
    \/ LosePollingLock
    \/ LoseActiveReviewLock
    \/ RetryMissingRequest
    \/ BeginReview
    \/ AbortReviewAfterLockLoss
    \/ StartPublishingFeedback
    \/ PublishFeedback
    \/ ReleaseFeedback
    \/ EarlyUnlockBeforePublishing
    \/ EarlyUnlockWithFeedbackTemp
    \/ ObserveReviewerFeedback
    \/ ApplyReviewerFeedback
    \/ ContinueAfterNoFindings
    \/ BeginCompletionCleanup
    \/ RemoveCleanupReviewerTmp
    \/ RemoveCleanupImplementorTmp
    \/ RemoveCleanupImplementorTxt
    \/ PublishCompletion
    \/ EarlyPublishCompletionMarker
    \/ AcknowledgeCompletion
    \/ ObserveCompletionAcknowledged
    \/ TerminalStutter

Fairness ==
    /\ WF_vars(StartupCleanupStep)
    /\ WF_vars(FinishStartupCleanup)
    /\ WF_vars(StartReviewer)
    /\ WF_vars(FinishImplementationPhase)
    /\ WF_vars(ClearImplementorMessage)
    /\ WF_vars(ReuseImplementorMessage)
    /\ WF_vars(StartImplementorMessage)
    /\ WF_vars(PublishImplementorMessage)
    /\ WF_vars(FinishImplementorMessage)
    /\ WF_vars(FinishInitialPreparation)
    /\ WF_vars(AcknowledgeReviewerMessage)
    /\ WF_vars(RequestReview)
    /\ WF_vars(RetryMissingRequest)
    /\ WF_vars(BeginReview)
    /\ WF_vars(AbortReviewAfterLockLoss)
    /\ WF_vars(StartPublishingFeedback)
    /\ WF_vars(PublishFeedback)
    /\ WF_vars(ReleaseFeedback)
    /\ WF_vars(ObserveReviewerFeedback)
    /\ WF_vars(ApplyReviewerFeedback)
    /\ WF_vars(ContinueAfterNoFindings)
    /\ WF_vars(BeginCompletionCleanup)
    /\ WF_vars(RemoveCleanupReviewerTmp)
    /\ WF_vars(RemoveCleanupImplementorTmp)
    /\ WF_vars(RemoveCleanupImplementorTxt)
    /\ WF_vars(PublishCompletion)
    /\ WF_vars(AcknowledgeCompletion)
    /\ WF_vars(ObserveCompletionAcknowledged)

Spec == Init /\ [][Next]_vars /\ Fairness

TypeOK ==
    /\ impl \in ImplStates
    /\ reviewer \in ReviewerStates
    /\ files \in FileStates
    /\ content \in ContentStates
    /\ request \in RequestStates
    /\ faults \in FaultStates

ReviewerStartsAfterStartupCleanup ==
    (reviewer # "offline") => ProtocolStarted

\* The snapshot remains frozen while its lock exists and across a missing-lock
\* retry gap for the same logical request.
ImplementationFrozenThroughReview ==
    (ProtocolStarted
        /\ (files.reviewLock \/
            (request.active
                /\ request.decisionCount = 0
                /\ ~files.roundComplete))) =>
        content.code = content.submittedCode

ImplementorMessageFrozenThroughReview ==
    (ProtocolStarted
        /\ ~files.roundComplete
        /\ (files.reviewLock \/
            (request.active /\ request.decisionCount = 0))) =>
        /\ files.implementorToReviewerTxt =
            request.submittedImplementorMessagePresent
        /\ (~files.implementorToReviewerTxt \/
            content.implementorMessage =
                content.submittedImplementorMessage)

ReviewRequestsIncludeImplementorContext ==
    (ProtocolStarted
        /\ request.active
        /\ request.decisionCount = 0) =>
        /\ request.submittedImplementorMessagePresent
        /\ files.implementorToReviewerTxt

ImplementorMessagePublicationIsAtomic ==
    ProtocolStarted =>
        /\ ~(files.implementorToReviewerTmp /\
             files.implementorToReviewerTxt)
        /\ (files.implementorToReviewerTmp =>
            /\ ~files.reviewLock
            /\ impl = "writingMessage")

ReviewerMessagePublicationIsAtomic ==
    ProtocolStarted =>
        /\ ~(files.reviewerToImplementorTmp /\
             files.reviewerToImplementorTxt)
        /\ (files.reviewerToImplementorTmp =>
            reviewer = "publishingFeedback")

ReviewerMessagePublicationStartsWhileLocked ==
    [][~files.reviewerToImplementorTmp
        /\ files.reviewerToImplementorTmp' =>
            files.reviewLock]_vars

ReviewerMessageFrozenUntilConsumed ==
    [][ProtocolStarted
        /\ request.active
        /\ request.decisionCount = 1
        /\ impl # "cleaning"
        /\ ~files.roundComplete
        /\ request.active' =>
            /\ files.reviewerToImplementorTxt'
            /\ content.reviewerMessage' = content.reviewerMessage]_vars

ReviewerUsesFrozenSnapshot ==
    (ProtocolStarted /\ ReviewerActive /\ files.reviewLock) =>
        /\ request.active
        /\ content.reviewedCode = content.submittedCode
        /\ request.submittedImplementorMessagePresent
        /\ files.implementorToReviewerTxt
        /\ content.implementorMessage =
            content.submittedImplementorMessage

ReviewerMessagePublishedBeforeUnlock ==
    [][files.reviewLock
        /\ ~files.reviewLock'
        /\ reviewer' # reviewer =>
            files.reviewerToImplementorTxt]_vars

DecisionAccounting ==
    ProtocolStarted =>
        /\ (~request.active => request.decisionCount = 0)
        /\ (files.roundComplete =>
            /\ ~request.active
            /\ request.decisionCount = 0
            /\ request.feedbackKind = "noFindings"
            /\ ~files.reviewerToImplementorTmp
            /\ ~files.reviewerToImplementorTxt)
        /\ (request.active /\ request.decisionCount = 1 =>
            /\ request.feedbackKind \in ReviewerFeedbackKinds
            /\ (impl # "cleaning" =>
                files.reviewerToImplementorTxt))
        /\ (request.active /\ request.decisionCount = 0 =>
            /\ request.feedbackKind = "none"
            /\ ~files.roundComplete
            /\ ~files.reviewerToImplementorTxt)
        /\ (~request.active
            /\ impl # "awaitingShutdownAck"
            /\ impl # "done" =>
                request.feedbackKind = "none")

RequestStateIsConsistent ==
    ProtocolStarted =>
        /\ (files.reviewLock => request.active)
        /\ ((files.reviewerToImplementorTmp \/
             files.reviewerToImplementorTxt) => request.active)
        /\ (~request.active =>
            /\ ~files.reviewLock
            /\ ~files.reviewerToImplementorTmp
            /\ ~files.reviewerToImplementorTxt)

HandlingRequiresReviewerMessage ==
    /\ (impl = "handling" =>
        /\ ~files.reviewLock
        /\ request.active
        /\ request.decisionCount = 1
        /\ files.reviewerToImplementorTxt)
    /\ ((request.active /\
            impl \in {
                "readyToMessage",
                "writingMessage",
                "messagePublished",
                "acknowledging"
                }) =>
            /\ ~files.reviewLock
            /\ request.decisionCount = 1
            /\ files.reviewerToImplementorTxt)
    /\ (impl = "cleaning" =>
        /\ ~files.reviewLock
        /\ request.active
        /\ request.decisionCount = 1
        /\ request.feedbackKind = "noFindings")

CompletionHasPriority ==
    (ProtocolStarted /\ files.roundComplete) =>
        /\ impl = "awaitingShutdownAck"
        /\ reviewer = "pollingParticipated"
        /\ FilesExceptCompletionAbsent
        /\ request.feedbackKind = "noFindings"

CompletionRequiresNoFindings ==
    (impl \in {"cleaning", "awaitingShutdownAck", "done"}) =>
        request.feedbackKind = "noFindings"

ReviewerTerminatesOnlyAfterCompletion ==
    (reviewer = "done") =>
        /\ impl \in {"awaitingShutdownAck", "done"}
        /\ AllFilesAbsent
        /\ ~request.active
        /\ request.feedbackKind = "noFindings"

SuccessfulTerminationIsClean ==
    (impl = "done") =>
        /\ reviewer = "done"
        /\ AllFilesAbsent
        /\ ~request.active
        /\ request.decisionCount = 0
        /\ request.feedbackKind = "noFindings"

CompletionMarkerPublishedLast ==
    [][~files.roundComplete /\ files.roundComplete' =>
        /\ ~files.reviewLock
        /\ ~files.reviewerToImplementorTmp
        /\ files.reviewerToImplementorTxt
        /\ ~files.implementorToReviewerTmp
        /\ ~files.implementorToReviewerTxt
        /\ FilesExceptCompletionAbsent'
        /\ impl = "cleaning"
        /\ impl' = "awaitingShutdownAck"
        /\ request.feedbackKind = "noFindings"]_vars

CompletionMarkerRemovedLast ==
    [][files.roundComplete /\ ~files.roundComplete' =>
        FilesExceptCompletionAbsent]_vars

CompletionAcknowledgedByParticipatingReviewer ==
    [][files.roundComplete
        /\ ~files.roundComplete'
        /\ impl # "starting" =>
            /\ impl = "awaitingShutdownAck"
            /\ reviewer = "pollingParticipated"
            /\ reviewer' = "done"]_vars

ExactlyOneDecisionPerLogicalRequest ==
    /\ ((request.active /\ request.decisionCount = 0)
        ~> (request.decisionCount = 1))
    /\ [][request.active
        /\ request.active'
        /\ request.decisionCount = 1 =>
            request.decisionCount' = 1]_vars
    /\ [][request.active /\ ~request.active' =>
        /\ request.decisionCount = 1
        /\ request.decisionCount' = 0]_vars

StartupCleanupEventuallyFinishes ==
    (impl = "starting") ~> (impl = "editing" /\ AllFilesAbsent)

ReviewerEventuallyStarts ==
    (reviewer = "offline" /\ ProtocolStarted) ~>
        (reviewer # "offline")

ReviewRequestEventuallyReleased ==
    (ProtocolStarted /\ files.reviewLock) ~> ~files.reviewLock

NoFindingsEventuallyContinuesOrShutsDown ==
    (impl = "handling" /\ request.feedbackKind = "noFindings") ~>
        (impl # "handling")

ReviewerMessageEventuallyConsumed ==
    (ProtocolStarted /\ files.reviewerToImplementorTxt) ~>
        ~files.reviewerToImplementorTxt

ImplementorContextEventuallyAvailable ==
    (ProtocolStarted
        /\ impl = "readyToMessage"
        /\ ~files.implementorToReviewerTxt) ~>
            files.implementorToReviewerTxt

ReviewerMessageTempEventuallyPublished ==
    (ProtocolStarted
        /\ files.reviewerToImplementorTmp
        /\ reviewer = "publishingFeedback"
        /\ files.reviewLock) ~>
            files.reviewerToImplementorTxt

ImplementorMessageTempEventuallyPublished ==
    (ProtocolStarted
        /\ files.implementorToReviewerTmp
        /\ impl = "writingMessage") ~>
            files.implementorToReviewerTxt

CompletionEventuallyAcknowledged ==
    (impl = "awaitingShutdownAck" /\ files.roundComplete) ~>
        (reviewer = "done" /\ ~files.roundComplete)

ShutdownEventuallyFinishes ==
    (impl = "awaitingShutdownAck") ~> (impl = "done")

=============================================================================
