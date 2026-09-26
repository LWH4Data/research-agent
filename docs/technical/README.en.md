# Research Agent Technical Design

[한국어](./README.md) | [English](./README.en.md)

Start with the topic relevant to the change. Each topic explains behavior, design
choices, and implementation responsibilities. [ROADMAP](./en/ROADMAP.md) owns
current status and next work; the experiment records below own dated evidence.

<a id="contents"></a>

## Topic Index

1. [Protecting Original User Directories and Managing Permissions](./en/permissions.md)
2. [PDF Conversion and Result Reliability](./en/pdf-conversion.md)
3. [Storage and Incremental Synchronization](./en/storage-sync.md)
4. [Skill Invocation, Retrieval, and Evidence Assembly](./en/search.md)
5. [Conversation Storage and the Research Memory Lifecycle](./en/conversation-memory.md)
6. [Progress in the Codex Task and Interrupted-Run Recovery](./en/progress-recovery.md)

## 1. Protecting Original User Directories and Managing Permissions

<a id="design-goal"></a> <a id="usage-policy-and-permission-flow"></a> <a id="protection-layers"></a> <a id="relationship-to-the-parent-codex-session"></a> <a id="allowed-work-by-role"></a> <a id="isolating-the-storage-commands-configuration-stack"></a> <a id="scope-of-the-guarantee"></a> <a id="verification-criteria"></a> <a id="uninstallation-and-source-protection"></a> <a id="implementation-responsibilities"></a>

Explains source read-only boundaries, parent Codex and launcher permissions, and safe uninstallation.

→ [Read this topic](./en/permissions.md)

## 2. PDF Conversion and Result Reliability

<a id="design-goal-1"></a> <a id="conversion-flow"></a> <a id="base-text-extraction"></a> <a id="selecting-pages-for-visual-review"></a> <a id="sol-high-visual-review"></a> <a id="visual-review-storage-schema-and-the-current-queue"></a> <a id="roles-of-the-primary-codex-session-and-background-reviewer"></a> <a id="meaning-of-review-states"></a> <a id="reliability-by-use-case"></a> <a id="implementation-responsibilities-1"></a>

Explains text extraction, review selection, Sol high review, per-page notes, and the guarantee provided by `verified`.

→ [Read this topic](./en/pdf-conversion.md)

## 3. Storage and Incremental Synchronization

<a id="design-goal-2"></a> <a id="responsibilities-of-each-storage-area"></a> <a id="document-identity"></a> <a id="synchronization-flow"></a> <a id="change-detection-order"></a> <a id="detecting-changes-during-processing"></a> <a id="missing-documents-and-unavailable-sources"></a> <a id="representative-behavior"></a> <a id="current-scope-and-limitations"></a> <a id="implementation-responsibilities-2"></a>

Explains storage areas, document identity, change detection, and missing-source behavior.

→ [Read this topic](./en/storage-sync.md)

## 4. Skill Invocation, Retrieval, and Evidence Assembly

<a id="design-goal-3"></a> <a id="relationship-between-projects-and-research-agent"></a> <a id="search-targets"></a> <a id="retrieval-flow"></a> <a id="building-search-terms-from-a-question"></a> <a id="current-retrieval-method"></a> <a id="continuation-and-change-detection"></a> <a id="ongoing-retrieval-evaluation"></a> <a id="boundary-between-local-search-and-model-tokens"></a> <a id="next-retrieval-index-candidate-sqlite-fts5"></a> <a id="pdf-pages-and-visual-review-evidence"></a> <a id="distinguishing-information-types"></a> <a id="boundary-between-document-content-and-instructions"></a> <a id="data-from-multiple-codex-projects"></a> <a id="current-scope-and-limitations-1"></a> <a id="verification-criteria-1"></a> <a id="implementation-responsibilities-3"></a>

Explains skill invocation, combined PDF/conversation retrieval, and evidence rules. FTS5 remains a future candidate, not the current implementation.

→ [Read this topic](./en/search.md)

## 5. Conversation Storage and the Research Memory Lifecycle

<a id="design-goal-4"></a> <a id="user-requests-and-internal-commands"></a> <a id="record-identity-and-revision-history"></a> <a id="editable-content"></a> <a id="deletion-boundary"></a> <a id="conversation-operation-journal-and-interrupted-run-recovery"></a> <a id="current-scope-and-limitations-2"></a> <a id="verification-criteria-2"></a> <a id="implementation-responsibilities-4"></a>

Explains save-scope selection, conversation retrieval, updates and deletion, revisions, and the operation journal.

→ [Read this topic](./en/conversation-memory.md)

## 6. Progress in the Codex Task and Interrupted-Run Recovery

<a id="design-goal-5"></a> <a id="display-flow"></a> <a id="keeping-the-conversation-compact"></a> <a id="interruption-and-the-next-run"></a> <a id="implementation-responsibilities-5"></a>

Explains in-task progress, background-review status, and the next run after interruption.

→ [Read this topic](./en/progress-recovery.md)

## Related Designs and Validation Records

- [Attachment import and installation](./en/attachment-import.md)
- [Versioning and runtime releases](./en/releases.md)
- [Safety and agent-routing validation](./en/experiments/safety-routing-validation.md)
- [Retrieval evaluation](./en/experiments/search-evaluation.md)
- [Subscription usage and processing efficiency](./en/experiments/subscription-usage.md)

Existing README topic and subsection links land at the corresponding topic entry.
New links point directly to the relevant section in its topic document.
