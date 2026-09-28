from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Callable
import uuid

from .config import Config
from .locking import conversation_lock as project_write_lock
from .safety import (
    atomic_text,
    is_within,
    reject_linked_file,
    require_owned_path,
    unlink_owned_file,
)
from .state import LibraryState


StateMutation = Callable[[LibraryState], None]


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _output_from_operation(config: Config, operation: dict[str, object]) -> Path:
    raw = operation.get("output_path")
    if not isinstance(raw, str) or not raw:
        raise RuntimeError("문서 복구 기록의 Markdown 경로가 올바르지 않습니다")
    relative = Path(raw)
    if relative.is_absolute():
        raise RuntimeError("문서 복구 기록에는 프로젝트 상대 경로가 필요합니다")
    output = require_owned_path(
        config.root / relative,
        config.root,
        label="문서 복구 Markdown 경로",
    )
    documents = require_owned_path(
        config.documents,
        config.root,
        label="문서 저장 폴더",
    )
    if output == documents or not is_within(output, documents):
        raise RuntimeError("문서 복구 Markdown 경로가 문서 저장 폴더 밖을 가리킵니다")
    return reject_linked_file(output, config.root, label="문서 복구 Markdown")


def _validate_operation_snapshots(
    operation: dict[str, object],
) -> tuple[str, dict[str, object] | None, dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    document_key = operation.get("document_key")
    base_document = operation.get("base_document")
    target_document = operation.get("target_document")
    base_reviews = operation.get("base_reviews")
    target_reviews = operation.get("target_reviews")
    if not isinstance(document_key, str) or not document_key:
        raise RuntimeError("문서 복구 기록의 문서 키가 올바르지 않습니다")
    if base_document is not None and not isinstance(base_document, dict):
        raise RuntimeError("문서 복구 기록의 기존 문서 상태가 올바르지 않습니다")
    if not isinstance(target_document, dict):
        raise RuntimeError("문서 복구 기록의 목표 문서 상태가 올바르지 않습니다")
    if not isinstance(base_reviews, list) or not all(
        isinstance(item, dict) for item in base_reviews
    ):
        raise RuntimeError("문서 복구 기록의 기존 검토 상태가 올바르지 않습니다")
    if not isinstance(target_reviews, list) or not all(
        isinstance(item, dict) for item in target_reviews
    ):
        raise RuntimeError("문서 복구 기록의 목표 검토 상태가 올바르지 않습니다")
    for document in (base_document, target_document):
        if document is not None and document.get("document_key") != document_key:
            raise RuntimeError("문서 복구 기록의 문서 키가 서로 일치하지 않습니다")
    if target_document.get("output_path") != operation.get("output_path"):
        raise RuntimeError("문서 복구 기록의 Markdown 경로가 서로 일치하지 않습니다")
    for review in [*base_reviews, *target_reviews]:
        if review.get("document_key") != document_key:
            raise RuntimeError("문서 복구 기록의 페이지 문서 키가 일치하지 않습니다")
    return (
        document_key,
        base_document,
        target_document,
        base_reviews,
        target_reviews,
    )


def _apply_target_snapshot(
    state: LibraryState,
    *,
    document_key: str,
    target_document: dict[str, object],
    target_reviews: list[dict[str, object]],
) -> None:
    state.upsert_document(target_document)
    state.replace_review_records(document_key, target_reviews)


def journaled_document_replace(
    config: Config,
    state: LibraryState,
    *,
    operation: str,
    document_key: str,
    output: Path,
    base_document: dict[str, object] | None,
    target_document: dict[str, object],
    base_reviews: list[dict[str, object]],
    target_reviews: list[dict[str, object]],
    target_markdown: str,
    after_state_update: StateMutation | None = None,
    review_fence: dict[str, object] | None = None,
    intake_receipt: dict[str, object] | None = None,
) -> None:
    """Replace one generated Markdown/SQLite snapshot with SIGKILL recovery."""

    output = reject_linked_file(output, config.root, label="문서 Markdown 출력")
    relative_output = output.relative_to(config.root).as_posix()
    if target_document.get("output_path") != relative_output:
        raise ValueError("목표 문서 레코드와 Markdown 경로가 일치하지 않습니다")
    output_existed = output.is_file()
    base_markdown = output.read_bytes() if output_existed else None
    base_hash = None if base_markdown is None else _bytes_sha256(base_markdown)
    operation_id = uuid.uuid4().hex
    if intake_receipt is not None:
        state.validate_intake_receipt(intake_receipt)
    if operation == "review-page":
        # The caller holds the storage lock. Authority changes take control then
        # storage; validation must never try to acquire control in this direction.
        from .review_lifecycle import validate_result
        validate_result(config.root, review_fence, base_document)
    prepared_operation = state.prepare_document_operation(
        operation_id=operation_id,
        operation=operation,
        document_key=document_key,
        output_path=relative_output,
        base_document=base_document,
        target_document=target_document,
        base_reviews=base_reviews,
        target_reviews=target_reviews,
        base_markdown_sha256=base_hash,
        target_markdown=target_markdown,
        intake_receipt=intake_receipt,
    )
    target_hash = str(prepared_operation["target_markdown_sha256"])

    try:
        atomic_text(output, target_markdown, config.root)
        state.begin_immediate()
        _apply_target_snapshot(
            state,
            document_key=document_key,
            target_document=target_document,
            target_reviews=target_reviews,
        )
        if after_state_update is not None:
            after_state_update(state)
        if intake_receipt is not None:
            state.record_intake_receipt(intake_receipt)
        state.finish_document_operation(operation_id)
        state.commit()
    except BaseException:
        if state.connection.in_transaction:
            state.connection.rollback()
        restore_error: BaseException | None = None
        try:
            checked_output = reject_linked_file(
                output,
                config.root,
                label="실패 후 Markdown 출력",
            )
            current_hash = (
                _bytes_sha256(checked_output.read_bytes())
                if checked_output.exists()
                else None
            )
        except BaseException as error:
            current_hash = None
            restore_error = error

        if restore_error is None and current_hash == target_hash:
            try:
                if base_markdown is None:
                    unlink_owned_file(
                        output,
                        config.root,
                        label="실패한 Markdown 출력",
                        missing_ok=True,
                    )
                else:
                    atomic_text(
                        output,
                        base_markdown.decode("utf-8"),
                        config.root,
                    )
            except BaseException as error:
                restore_error = error
        elif restore_error is None and current_hash != base_hash:
            restore_error = RuntimeError(
                "문서 쓰기 실패 후 Markdown 상태가 기존 또는 목표 내용과 "
                f"일치하지 않습니다: {output}"
            )
        if restore_error is None:
            try:
                state.begin_immediate()
                pending = state.get_pending_document_operation()
                if pending is not None:
                    state.finish_document_operation(operation_id)
                state.commit()
            except BaseException as error:
                if state.connection.in_transaction:
                    state.connection.rollback()
                restore_error = error
        if restore_error is not None:
            raise RuntimeError(
                f"문서 상태 저장 실패 후 안전하게 복구하지 못했습니다: {output}"
            ) from restore_error
        raise


def _recover_document_operation_locked(config: Config) -> bool:
    # Keep ordinary status/search/review reads byte-for-byte read-only when no
    # interrupted operation exists. Open a writer only for actual recovery.
    with LibraryState(config.state, config.root, read_only=True) as read_state:
        if read_state.get_pending_document_operation() is None:
            return False
    with LibraryState(config.state, config.root) as state:
        operation = state.get_pending_document_operation()
        if operation is None:
            return False
        output = _output_from_operation(config, operation)
        (
            document_key,
            base_document,
            target_document,
            base_reviews,
            target_reviews,
        ) = _validate_operation_snapshots(operation)
        current_document = state.get_document(document_key)
        current_reviews = state.document_reviews(document_key)
        database_is_base = (
            current_document == base_document and current_reviews == base_reviews
        )
        database_is_target = (
            current_document == target_document and current_reviews == target_reviews
        )
        if not database_is_base and not database_is_target:
            raise RuntimeError(
                "중단된 문서 작업을 복구할 수 없습니다. SQLite 상태가 예상과 다릅니다"
            )

        current_hash: str | None
        if output.exists():
            current_hash = _bytes_sha256(output.read_bytes())
        else:
            current_hash = None
        base_hash = operation.get("base_markdown_sha256")
        target_hash = operation.get("target_markdown_sha256")
        if current_hash not in {base_hash, target_hash}:
            raise RuntimeError(
                "중단된 문서 작업을 복구할 수 없습니다. Markdown 내용이 예상과 다릅니다"
            )
        target_bytes = operation.get("target_markdown")
        if not isinstance(target_bytes, bytes):
            raise RuntimeError("문서 복구 Markdown 기록이 올바르지 않습니다")
        if current_hash != target_hash:
            try:
                target_text = target_bytes.decode("utf-8")
            except UnicodeDecodeError as error:
                raise RuntimeError("문서 복구 Markdown이 UTF-8이 아닙니다") from error
            atomic_text(output, target_text, config.root)

        state.begin_immediate()
        _apply_target_snapshot(
            state,
            document_key=document_key,
            target_document=target_document,
            target_reviews=target_reviews,
        )
        if operation.get("intake_receipt") is not None:
            state.record_intake_receipt(operation["intake_receipt"])
        state.finish_document_operation(str(operation["operation_id"]))
        state.commit()
        return True


def recover_document_operation(
    config: Config, *, lock_held: bool = False
) -> bool:
    """Roll forward one generated-document operation left by an interruption."""

    if lock_held:
        recovered = _recover_document_operation_locked(config)
        return _recover_document_deletions_locked(config) or recovered
    with project_write_lock(config.root):
        recovered = _recover_document_operation_locked(config)
        return _recover_document_deletions_locked(config) or recovered


def _recover_document_deletions_locked(config: Config) -> bool:
    """Finish only recorded owned files; lifecycle already revoked authority."""
    with LibraryState(config.state, config.root, read_only=True) as state:
        if not state.pending_document_deletions():
            return False
    with LibraryState(config.state, config.root) as state:
        for deletion in state.pending_document_deletions():
            document = state.get_document(str(deletion["document_key"]))
            if document is None:
                raise RuntimeError("삭제 복구 문서 기록이 없습니다")
            if any(other["document_key"] != document["document_key"] and other["output_path"] == document["output_path"] for other in state.documents()):
                raise ValueError("다른 문서도 사용하는 Markdown은 삭제 복구할 수 없습니다")
            allowed_files = {str(document["output_path"])}
            allowed_directories: set[str] = set()
            source_id = str(document["source_id"])
            if source_id.startswith("import-") and len(source_id) == 71 and source_id not in {source.id for source in config.sources}:
                import_directory = Path(".research-store/imports") / source_id[7:]
                allowed_files.update((import_directory / name).as_posix() for name in ("document.pdf", "metadata.json"))
                allowed_directories.add(import_directory.as_posix())
            if set(deletion["files"]) != allowed_files or set(deletion["directories"]) != allowed_directories:
                raise RuntimeError("삭제 복구 경로가 문서 소유 범위와 다릅니다")
            output = require_owned_path(config.root / str(document["output_path"]), config.root, label="삭제할 Markdown")
            if not is_within(output, config.documents) or output == config.documents:
                raise ValueError("삭제할 Markdown이 문서 폴더 밖에 있습니다")
            # Validate the entire set before removing any file. Recheck each
            # unlink too; replacing a file with a symlink/hard link fails closed.
            files = [reject_linked_file(config.root / path, config.root, label="삭제할 문서 파일") for path in deletion["files"]]
            directories = [require_owned_path(config.root / path, config.root, label="삭제할 첨부 폴더") for path in deletion["directories"]]
            for directory in directories:
                if directory.exists() and set(child.name for child in directory.iterdir()) - {"document.pdf", "metadata.json"}:
                    raise ValueError("삭제할 첨부 폴더에 소유하지 않은 파일이 있습니다")
            for path in files:
                unlink_owned_file(path, config.root, label="삭제할 문서 파일", missing_ok=True)
            for directory in directories:
                if directory.exists():
                    directory.rmdir()
                    descriptor = os.open(directory.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            state.finish_document_deletion(str(deletion["document_key"]))
    return True
